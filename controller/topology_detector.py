"""
SDN Topology Change Detector - Ryu Controller Application
==========================================================
A Ryu OpenFlow 1.3 controller that implements:
1. MAC Learning Switch - learns source MACs, installs flow rules
2. Topology Change Detection - detects switch/link up/down via LLDP
3. Event Logging - logs all topology changes with timestamps
4. REST API - exposes topology state for the web dashboard

Usage:
    ryu-manager controller/topology_detector.py --observe-links
"""

import json
import time
import logging
from datetime import datetime
from functools import partial

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub
from os_ken.topology import event as topo_event
from os_ken.topology.api import get_switch, get_link, get_host


# Name for the WSGI application
TOPOLOGY_APP_NAME = 'topology_detector_api'

# Log file path
LOG_FILE = 'logs/topology_events.log'


class TopologyDetector(app_manager.OSKenApp):
    """
    Main Ryu application for SDN-based topology change detection.

    This controller implements:
    - OpenFlow 1.3 learning switch (packet_in -> flow_mod)
    - Topology discovery using Ryu's topology module (LLDP)
    - Real-time event logging for all topology changes
    - REST API for external dashboard integration
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)

        # MAC address table: {dpid: {mac: port}}
        self.mac_to_port = {}

        # Topology state
        self.switches = {}      # {dpid: switch_info}
        self.links = []         # [{src_dpid, src_port, dst_dpid, dst_port}]
        self.hosts = {}         # {mac: {ip, dpid, port}}

        # Event history
        self.events = []

        # Flow statistics
        self.flow_stats = {}    # {dpid: [flow_entries]}

        # Setup logger
        self._setup_logger()

        self.logger.info("=== Topology Detector Controller Initialized ===")

    def start(self):
        """Start the app: spawn event loop and REST API."""
        super(TopologyDetector, self).start()

        # Start REST API as a green thread
        hub.spawn(self._run_rest_api, 8080)

        self._log_event("SYSTEM", "Topology Detector controller started")
        self.logger.info("=== Topology Detector Controller Started ===")

    # =========================================================================
    # Logging
    # =========================================================================

    def _setup_logger(self):
        """Configure file logging for topology events."""
        import os
        os.makedirs('logs', exist_ok=True)

        self.file_logger = logging.getLogger('topology_events')
        self.file_logger.setLevel(logging.INFO)

        # File handler
        fh = logging.FileHandler(LOG_FILE, mode='a')
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        self.file_logger.addHandler(fh)

        # Write session header
        self.file_logger.info("=" * 60)
        self.file_logger.info("  SDN Topology Detector - Session Started")
        self.file_logger.info("=" * 60)

    def _log_event(self, event_type, details, **extra):
        """
        Log a topology event to file and store in memory.

        Args:
            event_type: Event category (NODE_ADDED, LINK_REMOVED, etc.)
            details: Human-readable description
            **extra: Additional metadata
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"{event_type}: {details}"

        # Log to file
        self.file_logger.info(log_line)

        # Store in memory for REST API
        event_record = {
            'timestamp': timestamp,
            'event_type': event_type,
            'details': details,
        }
        event_record.update(extra)
        self.events.append(event_record)

        # Keep only last 500 events in memory
        if len(self.events) > 500:
            self.events = self.events[-500:]

        # Console output
        self.logger.info(f"[{event_type}] {details}")

    # =========================================================================
    # OpenFlow: Switch Connection & Table-Miss Entry
    # =========================================================================

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Handle switch connection (OFPSwitchFeatures).

        When a new switch connects:
        1. Install a table-miss flow entry (priority=0) that sends
           unmatched packets to the controller via OFPP_CONTROLLER.
        2. This is the foundation of reactive flow installation.
        """
        try:
            datapath = ev.msg.datapath
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            dpid = datapath.id

            self.logger.info(f"Switch connected: dpid={dpid}")

            # Install table-miss flow entry
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                              ofproto.OFPCML_NO_BUFFER)]
            self._add_flow(datapath, priority=0, match=match, actions=actions,
                           idle_timeout=0, hard_timeout=0)

            # Initialize MAC table for this switch
            self.mac_to_port.setdefault(dpid, {})

            # Record switch
            self.switches[dpid] = {
                'dpid': dpid,
                'dpid_str': f"{dpid}" if dpid else "unknown",
                'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

            self._log_event(
                "SWITCH_CONNECTED",
                f"Switch s{dpid} connected to controller",
                dpid=dpid,
            )
        except Exception as e:
            self.logger.error(f"switch_features_handler CRASH: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    # =========================================================================
    # OpenFlow: Packet-In Handler (MAC Learning Switch)
    # =========================================================================

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Handle packet_in events - the core of the learning switch.

        Process:
        1. Extract source MAC, destination MAC, and ingress port
        2. Learn: store source MAC -> ingress port mapping
        3. Lookup: check if we know the port for destination MAC
        4. If known: install a flow rule and forward to that port
        5. If unknown: flood the packet to all ports
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        dpid = datapath.id

        # Parse the packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets (used by topology discovery)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # Ignore IPv6 multicast (reduces noise)
        if eth.ethertype == ether_types.ETH_TYPE_IPV6:
            return

        src_mac = eth.src
        dst_mac = eth.dst

        self.logger.debug(f"PacketIn: s{dpid} port={in_port} "
                          f"src={src_mac} dst={dst_mac}")

        # --- Step 1: LEARN ---
        # Store the source MAC address and its ingress port
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        # --- Step 2: LOOKUP ---
        # Check if we know the output port for the destination MAC
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            # Unknown destination - FLOOD to all ports
            out_port = ofproto.OFPP_FLOOD

        # Build actions list
        actions = [parser.OFPActionOutput(out_port)]

        # --- Step 3: INSTALL FLOW RULE ---
        # If we know the destination, install a flow rule so future packets
        # matching this dst_mac go directly to the output port without
        # coming to the controller again.
        if out_port != ofproto.OFPP_FLOOD:
            # Match: incoming port + destination MAC address
            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst_mac,
                eth_src=src_mac,
            )

            # Install with:
            #   priority=1 (higher than table-miss at priority=0)
            #   idle_timeout=300 (remove after 5 min of inactivity)
            #   hard_timeout=600 (absolute max lifetime of 10 min)
            self._add_flow(datapath, priority=1, match=match,
                           actions=actions, idle_timeout=300,
                           hard_timeout=600)

            self.logger.info(
                f"Flow installed: s{dpid} "
                f"match(in_port={in_port}, eth_dst={dst_mac}) "
                f"-> output:{out_port} "
                f"[priority=1, idle=300s, hard=600s]"
            )

        # --- Step 4: FORWARD THE CURRENT PACKET ---
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

        # Track host discovery
        self._check_host_discovery(dpid, in_port, src_mac, pkt)

    # =========================================================================
    # Flow Rule Installation Helper
    # =========================================================================

    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        """
        Install a flow rule on a switch using OFPFlowMod.

        Args:
            datapath: Switch datapath object
            priority: Rule priority (0=lowest, higher=more specific)
            match: OFPMatch object defining what packets to match
            actions: List of OFPAction objects defining what to do
            idle_timeout: Remove rule after N seconds of no matching packets
            hard_timeout: Remove rule after N seconds regardless of activity
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Wrap actions in an instruction (Apply-Actions)
        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions
        )]

        # Build FlowMod message
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        )

        # Send to switch
        datapath.send_msg(mod)

    # =========================================================================
    # Host Discovery
    # =========================================================================

    def _check_host_discovery(self, dpid, port, mac, pkt):
        """Check if this is a new host and log its discovery."""
        if mac not in self.hosts:
            # Try to get IP from ARP packet
            arp_pkt = pkt.get_protocol(arp.arp)
            ip_addr = arp_pkt.src_ip if arp_pkt else None

            if ip_addr is None:
                ip_pkt = pkt.get_protocol(ipv4.ipv4)
                ip_addr = ip_pkt.src if ip_pkt else 'unknown'

            self.hosts[mac] = {
                'mac': mac,
                'ip': ip_addr,
                'dpid': dpid,
                'port': port,
            }

            self._log_event(
                "HOST_DISCOVERED",
                f"Host {ip_addr} (MAC: {mac}) found on s{dpid} port {port}",
                mac=mac, ip=ip_addr, dpid=dpid, port=port,
            )

    # =========================================================================
    # Topology Change Detection (LLDP-based via Ryu topology module)
    # =========================================================================

    @set_ev_cls(topo_event.EventSwitchEnter)
    def switch_enter_handler(self, ev):
        """Handle new switch joining the network."""
        dpid = ev.switch.dp.id
        self.switches[dpid] = {
            'dpid': dpid,
            'dpid_str': f"{dpid:#018x}",
            'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._log_event(
            "SWITCH_ENTER",
            f"Switch s{dpid} joined the topology",
            dpid=dpid,
        )
        self._update_topology()

    @set_ev_cls(topo_event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        """Handle switch leaving the network."""
        dpid = ev.switch.dp.id
        if dpid in self.switches:
            del self.switches[dpid]
        if dpid in self.mac_to_port:
            del self.mac_to_port[dpid]

        self._log_event(
            "SWITCH_LEAVE",
            f"Switch s{dpid} left the topology",
            dpid=dpid,
        )
        self._update_topology()

    @set_ev_cls(topo_event.EventLinkAdd)
    def link_add_handler(self, ev):
        """Handle new link discovered between switches."""
        link = ev.link
        src_dpid = link.src.dpid
        src_port = link.src.port_no
        dst_dpid = link.dst.dpid
        dst_port = link.dst.port_no

        self._log_event(
            "LINK_ADD",
            f"Link UP: s{src_dpid}(port {src_port}) <-> "
            f"s{dst_dpid}(port {dst_port})",
            src_dpid=src_dpid, src_port=src_port,
            dst_dpid=dst_dpid, dst_port=dst_port,
        )
        self._update_topology()

    @set_ev_cls(topo_event.EventLinkDelete)
    def link_delete_handler(self, ev):
        """Handle link removal (link failure) between switches."""
        link = ev.link
        src_dpid = link.src.dpid
        src_port = link.src.port_no
        dst_dpid = link.dst.dpid
        dst_port = link.dst.port_no

        self._log_event(
            "LINK_DELETE",
            f"Link DOWN: s{src_dpid}(port {src_port}) <-> "
            f"s{dst_dpid}(port {dst_port})",
            src_dpid=src_dpid, src_port=src_port,
            dst_dpid=dst_dpid, dst_port=dst_port,
        )
        self._update_topology()

    def _update_topology(self):
        """Refresh the current view of switches and links."""
        try:
            switch_list = get_switch(self, None)
            link_list = get_link(self, None)

            self.links = []
            for link in link_list:
                self.links.append({
                    'src_dpid': link.src.dpid,
                    'src_port': link.src.port_no,
                    'dst_dpid': link.dst.dpid,
                    'dst_port': link.dst.port_no,
                })
        except Exception as e:
            self.logger.error(f"Error updating topology: {e}")

    # =========================================================================
    # Periodic Flow Stats Monitoring
    # =========================================================================

    def _monitor_loop(self):
        """Periodically request flow statistics from all switches."""
        while True:
            for dpid, switch_info in list(self.switches.items()):
                try:
                    self._request_flow_stats(dpid)
                except Exception:
                    pass
            hub.sleep(10)

    def _request_flow_stats(self, dpid):
        """Send a flow stats request to a specific switch."""
        # Find the datapath for this dpid
        switch_list = get_switch(self, dpid)
        if not switch_list:
            return

        datapath = switch_list[0].dp
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """Process flow stats reply from a switch."""
        dpid = ev.msg.datapath.id
        body = ev.msg.body

        flows = []
        for stat in sorted(body, key=lambda s: s.priority, reverse=True):
            flow_entry = {
                'priority': stat.priority,
                'idle_timeout': stat.idle_timeout,
                'hard_timeout': stat.hard_timeout,
                'match': str(stat.match),
                'actions': str(stat.instructions),
                'packet_count': stat.packet_count,
                'byte_count': stat.byte_count,
                'duration_sec': stat.duration_sec,
            }
            flows.append(flow_entry)

        self.flow_stats[dpid] = flows

    # =========================================================================
    # REST API Data Access Methods
    # =========================================================================

    def get_topology_data(self):
        """Return current topology state as a dictionary."""
        switches_list = []
        for dpid, info in self.switches.items():
            switches_list.append({
                'dpid': dpid,
                'dpid_str': f"s{dpid}",
                'connected_at': info.get('connected_at', ''),
            })

        links_list = []
        seen = set()
        for link in self.links:
            key = tuple(sorted([link['src_dpid'], link['dst_dpid']]))
            if key not in seen:
                links_list.append({
                    'src': f"s{link['src_dpid']}",
                    'dst': f"s{link['dst_dpid']}",
                    'src_port': link['src_port'],
                    'dst_port': link['dst_port'],
                })
                seen.add(key)

        hosts_list = []
        for mac, info in self.hosts.items():
            hosts_list.append({
                'mac': mac,
                'ip': info['ip'],
                'switch': f"s{info['dpid']}",
                'port': info['port'],
            })

        return {
            'switches': switches_list,
            'links': links_list,
            'hosts': hosts_list,
            'switch_count': len(switches_list),
            'link_count': len(links_list),
            'host_count': len(hosts_list),
        }

    def get_events_data(self):
        """Return recent topology events."""
        return list(reversed(self.events[-100:]))

    def get_flow_data(self, dpid=None):
        """Return flow table data for a specific switch or all switches."""
        if dpid is not None:
            return self.flow_stats.get(dpid, [])
        return self.flow_stats


    def _run_rest_api(self, port):
        """Run REST API server using eventlet WSGI (fully green-compatible)."""
        import eventlet
        from eventlet import wsgi

        app_ref = self

        def wsgi_app(environ, start_response):
            path = environ.get('PATH_INFO', '/').rstrip('/')

            if path == '/topology':
                data = app_ref.get_topology_data()
            elif path == '/events':
                data = app_ref.get_events_data()
            elif path == '/flows':
                raw = app_ref.get_flow_data()
                data = {str(k): v for k, v in raw.items()}
            elif path.startswith('/flows/'):
                dpid_str = path.split('/flows/')[-1]
                try:
                    dpid_int = int(dpid_str)
                except ValueError:
                    dpid_int = int(dpid_str, 16)
                data = app_ref.get_flow_data(dpid_int)
            else:
                start_response('404 Not Found',
                               [('Content-Type', 'application/json')])
                return [b'{"error": "not found"}']

            body = json.dumps(data, indent=2).encode()
            start_response('200 OK', [
                ('Content-Type', 'application/json'),
                ('Access-Control-Allow-Origin', '*'),
            ])
            return [body]

        sock = eventlet.listen(('0.0.0.0', port), reuse_addr=True)
        self.logger.info(f"REST API server started on port {port}")
        wsgi.server(sock, wsgi_app, log_output=False)

