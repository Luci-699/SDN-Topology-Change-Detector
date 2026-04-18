"""
SDN Topology Change Detector - Controller Application
======================================================
OpenFlow 1.3 controller with MAC learning + topology detection + event logging
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
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub

LOG_FILE = 'logs/topology_events.log'


class TopologyDetector(app_manager.OSKenApp):
    """SDN controller: MAC learning switch + event logging."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switch_info = {}
        self.hosts = {}
        self.events = []
        self.datapaths = {}
        self._setup_logger()
        self._log_event("SYSTEM", "Topology Detector controller initialized")
        self.logger.info("=== Topology Detector Controller Initialized ===")

    def _setup_logger(self):
        import os
        os.makedirs('logs', exist_ok=True)
        self.file_logger = logging.getLogger('topology_events')
        self.file_logger.setLevel(logging.INFO)
        if not self.file_logger.handlers:
            fh = logging.FileHandler(LOG_FILE, mode='a')
            fmt = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            fh.setFormatter(fmt)
            self.file_logger.addHandler(fh)

    def _log_event(self, event_type, details, **extra):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.file_logger.info(f"{event_type}: {details}")
        self.events.append({
            'timestamp': timestamp, 'event_type': event_type,
            'details': details, **extra
        })
        if len(self.events) > 500:
            self.events = self.events[-500:]
        self.logger.info(f"[{event_type}] {details}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        o = dp.ofproto
        p = dp.ofproto_parser
        dpid = dp.id

        # Table-miss flow
        dp.send_msg(p.OFPFlowMod(
            datapath=dp, priority=0, match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(
                o.OFPIT_APPLY_ACTIONS,
                [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])]))

        self.mac_to_port.setdefault(dpid, {})
        self.datapaths[dpid] = dp
        self.switch_info[dpid] = {
            'dpid': dpid,
            'connected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._log_event("SWITCH_CONNECTED", f"Switch s{dpid} connected", dpid=dpid)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        o = dp.ofproto
        p = dp.ofproto_parser
        pin = msg.match['in_port']
        dpid = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        if eth.dst.startswith('33:33:'):
            return

        dst, src = eth.dst, eth.src
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = pin

        # Host discovery
        if src not in self.hosts:
            ip = None
            a = pkt.get_protocol(arp.arp)
            if a: ip = a.src_ip
            v = pkt.get_protocol(ipv4.ipv4)
            if v: ip = v.src
            if ip:
                self.hosts[src] = {'mac': src, 'ip': ip, 'dpid': dpid, 'port': pin}
                self._log_event("HOST_DISCOVERED", f"Host {ip} ({src}) on s{dpid}:{pin}")

        out = self.mac_to_port[dpid].get(dst, o.OFPP_FLOOD)
        acts = [p.OFPActionOutput(out)]

        if out != o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(
                datapath=dp, priority=1,
                match=p.OFPMatch(in_port=pin, eth_dst=dst, eth_src=src),
                instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, acts)],
                idle_timeout=60, hard_timeout=120))

        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=pin, actions=acts, data=data))

    # REST API data methods
    def get_topology_data(self):
        return {
            'switches': [{'dpid': d, 'connected_at': i.get('connected_at', '')}
                         for d, i in self.switch_info.items()],
            'links': [], 'hosts': list(self.hosts.values()),
        }

    def get_events_data(self):
        return self.events[-100:]

    def get_flow_data(self, dpid=None):
        return {}
