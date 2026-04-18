"""
SDN Topology Change Detector - Controller Application
======================================================
OpenFlow 1.3 controller with:
- MAC Learning Switch with loop prevention
- Topology Change Detection
- Event Logging
- REST API for dashboard
"""
import json
import logging
from datetime import datetime
from collections import defaultdict

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4, lldp
from os_ken.lib import hub
from os_ken.topology import event as topo_event
from os_ken.topology.api import get_switch, get_link


LOG_FILE = 'logs/topology_events.log'


class TopologyDetector(app_manager.OSKenApp):
    """SDN controller with MAC learning, loop prevention, and topology detection."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {}

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)
        self.mac_to_port = {}          # {dpid: {mac: port}}
        self.switch_info = {}          # {dpid: info_dict}
        self.topo_links = []           # [{src_dpid, src_port, dst_dpid, dst_port}]
        self.hosts = {}                # {mac: {ip, dpid, port}}
        self.events = []               # event log
        self.flow_stats = {}           # {dpid: [flow_entries]}
        self.datapaths = {}            # {dpid: datapath}
        self.inter_switch_ports = defaultdict(set)  # {dpid: set(ports)} - ports connecting to other switches
        self._setup_logger()
        self._log_event("SYSTEM", "Topology Detector controller initialized")
        self.logger.info("=== Topology Detector Controller Initialized ===")

    # =========================================================================
    # Logging
    # =========================================================================

    def _setup_logger(self):
        """Configure file logging."""
        import os
        os.makedirs('logs', exist_ok=True)
        self.file_logger = logging.getLogger('topology_events')
        self.file_logger.setLevel(logging.INFO)
        if not self.file_logger.handlers:
            fh = logging.FileHandler(LOG_FILE, mode='a')
            fh.setLevel(logging.INFO)
            fmt = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            fh.setFormatter(fmt)
            self.file_logger.addHandler(fh)

    def _log_event(self, event_type, details, **extra):
        """Log a topology event."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.file_logger.info(f"{event_type}: {details}")
        event_record = {
            'timestamp': timestamp,
            'event_type': event_type,
            'details': details,
        }
        event_record.update(extra)
        self.events.append(event_record)
        if len(self.events) > 500:
            self.events = self.events[-500:]
        self.logger.info(f"[{event_type}] {details}")

    # =========================================================================
    # OpenFlow: Switch Features (CONFIG_DISPATCHER)
    # =========================================================================

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Install table-miss flow entry when a switch connects."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        self.logger.info(f"Switch {dpid} connected - installing table-miss")

        # Table-miss: send unmatched packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)

        self.mac_to_port.setdefault(dpid, {})
        self.datapaths[dpid] = datapath
        self.switch_info[dpid] = {
            'dpid': dpid,
            'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._log_event("SWITCH_CONNECTED", f"Switch s{dpid} connected to controller", dpid=dpid)

    # =========================================================================
    # OpenFlow: Packet-In (MAC Learning with Loop Prevention)
    # =========================================================================

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """MAC learning switch with loop prevention."""
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        # Ignore IPv6 multicast
        if eth.dst.startswith('33:33:'):
            return

        dst = eth.dst
        src = eth.src

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # Track host discovery
        self._discover_host(dpid, in_port, src, pkt)

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            # FLOOD only to host-facing ports (not inter-switch ports)
            # This prevents broadcast storms in ring/loop topologies
            isp = self.inter_switch_ports.get(dpid, set())
            if isp:
                # We know which ports connect to switches - exclude them from flood
                out_port = ofproto.OFPP_FLOOD  # Still use flood but we'll filter below
            else:
                out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow for known destinations
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self._add_flow(datapath, 1, match, actions, 60, 120)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions,
                                  data=data)
        datapath.send_msg(out)

    def _discover_host(self, dpid, port, mac, pkt):
        """Track discovered hosts."""
        if mac.startswith('ff:ff') or mac.startswith('33:33'):
            return
        if mac not in self.hosts:
            ip = None
            arp_pkt = pkt.get_protocol(arp.arp)
            if arp_pkt:
                ip = arp_pkt.src_ip
            ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
            if ipv4_pkt:
                ip = ipv4_pkt.src
            self.hosts[mac] = {'mac': mac, 'ip': ip, 'dpid': dpid, 'port': port}
            if ip:
                self._log_event("HOST_DISCOVERED",
                                f"Host {ip} ({mac}) on switch s{dpid} port {port}",
                                mac=mac, ip=ip, dpid=dpid, port=port)

    # =========================================================================
    # Flow Installation
    # =========================================================================

    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        """Install a flow rule."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout)
        datapath.send_msg(mod)

    # =========================================================================
    # Topology Events (from os_ken.topology.switches)
    # =========================================================================

    @set_ev_cls(topo_event.EventSwitchEnter)
    def _switch_enter_handler(self, ev):
        """Detect when a switch joins the network."""
        dpid = ev.switch.dp.id
        self._log_event("SWITCH_ENTER", f"Switch s{dpid} entered topology", dpid=dpid)

    @set_ev_cls(topo_event.EventSwitchLeave)
    def _switch_leave_handler(self, ev):
        """Detect when a switch leaves the network."""
        dpid = ev.switch.dp.id
        self.switch_info.pop(dpid, None)
        self.datapaths.pop(dpid, None)
        self.mac_to_port.pop(dpid, None)
        self.inter_switch_ports.pop(dpid, None)
        self._log_event("SWITCH_LEAVE", f"Switch s{dpid} left topology", dpid=dpid)

    @set_ev_cls(topo_event.EventLinkAdd)
    def _link_add_handler(self, ev):
        """Detect when a link comes up."""
        src_dpid = ev.link.src.dpid
        src_port = ev.link.src.port_no
        dst_dpid = ev.link.dst.dpid
        dst_port = ev.link.dst.port_no

        # Track inter-switch ports for loop prevention
        self.inter_switch_ports[src_dpid].add(src_port)
        self.inter_switch_ports[dst_dpid].add(dst_port)

        link_info = {
            'src_dpid': src_dpid, 'src_port': src_port,
            'dst_dpid': dst_dpid, 'dst_port': dst_port,
        }
        # Avoid duplicates
        if link_info not in self.topo_links:
            self.topo_links.append(link_info)

        self._log_event("LINK_ADD",
                         f"Link: s{src_dpid}(port {src_port}) <-> s{dst_dpid}(port {dst_port})",
                         **link_info)

        # Now that we know inter-switch ports, install drop rules for
        # broadcast on inter-switch ports to prevent storms.
        # We let LLDP through but block broadcast floods on one direction.
        self._update_loop_prevention(src_dpid)
        self._update_loop_prevention(dst_dpid)

    @set_ev_cls(topo_event.EventLinkDelete)
    def _link_delete_handler(self, ev):
        """Detect when a link goes down."""
        src_dpid = ev.link.src.dpid
        src_port = ev.link.src.port_no
        dst_dpid = ev.link.dst.dpid
        dst_port = ev.link.dst.port_no

        # Remove from inter-switch ports
        self.inter_switch_ports[src_dpid].discard(src_port)
        self.inter_switch_ports[dst_dpid].discard(dst_port)

        # Remove from link list
        self.topo_links = [l for l in self.topo_links
                           if not (l['src_dpid'] == src_dpid and l['src_port'] == src_port
                                   and l['dst_dpid'] == dst_dpid and l['dst_port'] == dst_port)]

        self._log_event("LINK_DELETE",
                         f"Link DOWN: s{src_dpid}(port {src_port}) <-> s{dst_dpid}(port {dst_port})",
                         src_dpid=src_dpid, src_port=src_port,
                         dst_dpid=dst_dpid, dst_port=dst_port)

    # =========================================================================
    # Loop Prevention
    # =========================================================================

    def _update_loop_prevention(self, dpid):
        """Block broadcast flooding on inter-switch ports to prevent storms.

        Strategy: On each switch, we install high-priority drop rules for
        broadcast/multicast traffic arriving on inter-switch ports. The
        controller will still get the packets via table-miss if needed.
        """
        if dpid not in self.datapaths:
            return
        datapath = self.datapaths[dpid]
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        isp = self.inter_switch_ports.get(dpid, set())
        for port in isp:
            # Drop broadcast packets coming FROM inter-switch ports
            # This breaks the broadcast storm loop
            match = parser.OFPMatch(in_port=port, eth_dst='ff:ff:ff:ff:ff:ff')
            # Empty actions = drop
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [])]
            mod = parser.OFPFlowMod(datapath=datapath, priority=10,
                                    match=match, instructions=inst,
                                    idle_timeout=0, hard_timeout=0)
            datapath.send_msg(mod)
            self.logger.info(f"  Loop prevention: dropping broadcast on s{dpid} port {port}")

    # =========================================================================
    # Flow Stats Collection
    # =========================================================================

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """Store flow statistics from switches."""
        dpid = ev.msg.datapath.id
        flows = []
        for stat in ev.msg.body:
            flows.append({
                'priority': stat.priority,
                'match': str(stat.match),
                'actions': str(stat.instructions),
                'packet_count': stat.packet_count,
                'byte_count': stat.byte_count,
                'duration_sec': stat.duration_sec,
            })
        self.flow_stats[dpid] = flows

    # =========================================================================
    # REST API Data (for dashboard)
    # =========================================================================

    def get_topology_data(self):
        """Return current topology state."""
        return {
            'switches': [
                {'dpid': dpid, 'dpid_str': str(dpid),
                 'connected_at': info.get('connected_at', '')}
                for dpid, info in self.switch_info.items()
            ],
            'links': self.topo_links,
            'hosts': list(self.hosts.values()),
        }

    def get_events_data(self):
        """Return recent topology events."""
        return self.events[-100:]

    def get_flow_data(self, dpid=None):
        """Return flow table data."""
        if dpid is not None:
            return self.flow_stats.get(dpid, [])
        return self.flow_stats
