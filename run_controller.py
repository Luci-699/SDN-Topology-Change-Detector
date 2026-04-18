#!/usr/bin/env python3
"""
SDN Topology Detector - All-in-one launcher + controller.
"""
import sys, os, warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import eventlet
eventlet.monkey_patch()

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s %(message)s')

from datetime import datetime
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub
from os_ken.base.app_manager import AppManager
from os_ken import cfg

LOG_FILE = 'logs/topology_events.log'


class TopologyDetector(app_manager.OSKenApp):
    """SDN controller: MAC learning + topology event logging."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopologyDetector, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.switch_info = {}
        self.hosts = {}
        self.events_log = []
        self.datapaths = {}
        self._setup_file_logger()
        self._log("SYSTEM", "Topology Detector controller initialized")

    def _setup_file_logger(self):
        os.makedirs('logs', exist_ok=True)
        self.file_logger = logging.getLogger('topology_events')
        self.file_logger.setLevel(logging.INFO)
        if not self.file_logger.handlers:
            fh = logging.FileHandler(LOG_FILE, mode='a')
            fmt = logging.Formatter('[%(asctime)s] %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S')
            fh.setFormatter(fmt)
            self.file_logger.addHandler(fh)

    def _log(self, event_type, details, **extra):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.file_logger.info(f"{event_type}: {details}")
        self.events_log.append({
            'timestamp': ts, 'event_type': event_type,
            'details': details, **extra
        })
        if len(self.events_log) > 500:
            self.events_log = self.events_log[-500:]
        self.logger.info(f"[{event_type}] {details}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        o = dp.ofproto
        p = dp.ofproto_parser
        dpid = dp.id

        # Install table-miss flow
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
        self._log("SWITCH_CONNECTED", f"Switch s{dpid} connected", dpid=dpid)
        print(f"*** SWITCH {dpid} CONNECTED ***", flush=True)

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
            if a:
                ip = a.src_ip
            v = pkt.get_protocol(ipv4.ipv4)
            if v:
                ip = v.src
            if ip:
                self.hosts[src] = {'mac': src, 'ip': ip, 'dpid': dpid, 'port': pin}
                self._log("HOST_DISCOVERED",
                          f"Host {ip} ({src}) on s{dpid}:{pin}")

        out = self.mac_to_port[dpid].get(dst, o.OFPP_FLOOD)
        acts = [p.OFPActionOutput(out)]

        if out != o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(
                datapath=dp, priority=1,
                match=p.OFPMatch(in_port=pin, eth_dst=dst, eth_src=src),
                instructions=[p.OFPInstructionActions(
                    o.OFPIT_APPLY_ACTIONS, acts)],
                idle_timeout=60, hard_timeout=120))

        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=pin, actions=acts, data=data))

    # Data methods for dashboard
    def get_topology_data(self):
        return {
            'switches': [{'dpid': d, 'connected_at': i.get('connected_at', '')}
                         for d, i in self.switch_info.items()],
            'links': [], 'hosts': list(self.hosts.values()),
        }

    def get_events_data(self):
        return self.events_log[-100:]


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  SDN Topology Detector - Controller")
    print("=" * 60)

    mgr = AppManager.get_instance()
    mgr.load_apps(['os_ken.controller.ofp_handler'])
    mgr.applications_cls['TopologyDetector'] = TopologyDetector

    try:
        cfg.CONF(args=['--ofp-tcp-listen-port=6633'],
                 project='os_ken', version='1.0')
    except SystemExit:
        pass

    services = mgr.instantiate_apps(**mgr.create_contexts())

    print("[INFO] Controller running on port 6633...")
    print("[INFO] Waiting for switches...", flush=True)

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()
