#!/usr/bin/env python3
"""
SDN Topology Change Detector
Run: python3 topo_detect.py
Then: sudo mn --topo tree,depth=2,fanout=2 --controller remote
"""
import eventlet
eventlet.monkey_patch()

import os, sys, logging
from datetime import datetime
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub
from os_ken.base.app_manager import AppManager
from os_ken import cfg

os.makedirs('logs', exist_ok=True)

# ============================================================
#  TopologyDetector Controller
# ============================================================
class TopologyDetector(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.mac_to_port = {}
        self.switches = {}
        self.hosts = {}
        self.events = []
        self.datapaths = {}
        # File logger
        self.flog = logging.getLogger('topo_events')
        self.flog.setLevel(logging.INFO)
        if not self.flog.handlers:
            fh = logging.FileHandler('logs/topology_events.log')
            fh.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
            self.flog.addHandler(fh)
        self._event("SYSTEM", "Controller initialized")

    def _event(self, etype, detail, **kw):
        ts = datetime.now().strftime('%H:%M:%S')
        self.flog.info(f"{etype}: {detail}")
        self.events.append({'time': ts, 'type': etype, 'detail': detail, **kw})
        print(f"  [{ts}] {etype}: {detail}", flush=True)

    # --- Switch Connect ---
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        o, p = dp.ofproto, dp.ofproto_parser
        dpid = dp.id
        # Table-miss: send to controller
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0,
            match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,
                [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])]))
        self.mac_to_port[dpid] = {}
        self.datapaths[dpid] = dp
        self.switches[dpid] = datetime.now().strftime('%H:%M:%S')
        self._event("SWITCH_UP", f"Switch s{dpid} connected")

    # --- Packet In (MAC Learning) ---
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        o, p = dp.ofproto, dp.ofproto_parser
        pin = msg.match['in_port']
        dpid = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        if eth.dst.startswith('33:33:'):
            return

        src, dst = eth.src, eth.dst
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = pin

        # Discover hosts
        if src not in self.hosts:
            ip = None
            a = pkt.get_protocol(arp.arp)
            if a: ip = a.src_ip
            v = pkt.get_protocol(ipv4.ipv4)
            if v: ip = v.src
            if ip:
                self.hosts[src] = {'mac': src, 'ip': ip, 'switch': dpid, 'port': pin}
                self._event("HOST_FOUND", f"{ip} ({src}) on s{dpid}:{pin}")

        out = self.mac_to_port[dpid].get(dst, o.OFPP_FLOOD)
        acts = [p.OFPActionOutput(out)]

        if out != o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=1,
                match=p.OFPMatch(in_port=pin, eth_dst=dst, eth_src=src),
                instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, acts)],
                idle_timeout=60, hard_timeout=120))

        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
            in_port=pin, actions=acts, data=data))

    # --- Switch Disconnect ---
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER])
    def switch_state_change(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            pass  # handled in switch_features
        # Dead state = disconnected (handled by EventOFPStateChange with dead dispatcher)

    # --- Print Topology ---
    def print_topology(self):
        print("\n" + "=" * 40)
        print("  CURRENT TOPOLOGY")
        print("=" * 40)
        for dpid, ts in self.switches.items():
            print(f"  Switch s{dpid} (since {ts})")
        for mac, h in self.hosts.items():
            print(f"  Host {h.get('ip','?')} on s{h['switch']}:{h['port']}")
        print("=" * 40 + "\n")


# ============================================================
#  Main - Launch Controller
# ============================================================
if __name__ == '__main__':
    print("=" * 50)
    print("  SDN Topology Change Detector")
    print("  Port: 6653 (default)")
    print("=" * 50)
    print()
    print("  After this starts, run in another terminal:")
    print("  sudo mn --topo tree,depth=2,fanout=2 --controller remote")
    print()

    mgr = AppManager.get_instance()
    mgr.load_apps(['os_ken.controller.ofp_handler'])
    mgr.applications_cls['TopologyDetector'] = TopologyDetector

    # Use DEFAULT port 6653 - no cfg.CONF issues!
    try:
        cfg.CONF(args=[], project='os_ken', version='1.0')
    except SystemExit:
        pass

    services = mgr.instantiate_apps(**mgr.create_contexts())
    print("[READY] Waiting for switches on port 6653...\n", flush=True)

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nStopped.")
