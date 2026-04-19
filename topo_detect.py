"""
SDN Topology Change Detector
Run:   python3 topo_detect.py
Then:  sudo mn --topo tree,depth=2,fanout=2 --controller remote,port=6633
"""
import eventlet
eventlet.monkey_patch()

import os
from datetime import datetime
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub
from os_ken.base.app_manager import AppManager
from os_ken import cfg


class TopologyDetector(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(s, *a, **kw):
        super().__init__(*a, **kw)
        s.mac = {}
        s.switches = {}
        s.hosts = {}
        s.events = []
        s.datapaths = {}
        # Log to file (append)
        os.makedirs('logs', exist_ok=True)
        s.logfile = open('logs/topology_events.log', 'a')
        s._evt("SYSTEM", "Controller initialized")

    def _evt(s, etype, detail):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {etype}: {detail}"
        s.logfile.write(line + "\n")
        s.logfile.flush()
        s.events.append({'time': ts, 'type': etype, 'detail': detail})
        if len(s.events) > 500:
            s.events = s.events[-500:]
        print(f"  {line}", flush=True)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(s, ev):
        dp = ev.msg.datapath
        o, p = dp.ofproto, dp.ofproto_parser
        dpid = dp.id
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,
                [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])]))
        s.mac[dpid] = {}
        s.datapaths[dpid] = dp
        s.switches[dpid] = datetime.now().strftime('%H:%M:%S')
        s._evt("SWITCH_UP", f"Switch s{dpid} connected")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(s, ev):
        msg = ev.msg; dp = msg.datapath; o = dp.ofproto; p = dp.ofproto_parser
        pin = msg.match['in_port']; dpid = dp.id
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP: return
        if eth.dst.startswith('33:33:'): return
        src, dst = eth.src, eth.dst
        s.mac.setdefault(dpid, {}); s.mac[dpid][src] = pin
        # Host discovery
        if src not in s.hosts:
            ip = None
            a = pkt.get_protocol(arp.arp)
            if a: ip = a.src_ip
            v = pkt.get_protocol(ipv4.ipv4)
            if v: ip = v.src
            if ip:
                s.hosts[src] = {'mac': src, 'ip': ip, 'switch': dpid, 'port': pin}
                s._evt("HOST_FOUND", f"{ip} ({src}) on s{dpid}:{pin}")
        out = s.mac[dpid].get(dst, o.OFPP_FLOOD)
        acts = [p.OFPActionOutput(out)]
        if out != o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=1,
                match=p.OFPMatch(in_port=pin, eth_dst=dst, eth_src=src),
                instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, acts)],
                idle_timeout=60, hard_timeout=120))
        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
            in_port=pin, actions=acts, data=data))

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status(s, ev):
        msg = ev.msg; dp = msg.datapath; o = dp.ofproto; port = msg.desc
        dpid = dp.id
        if msg.reason == o.OFPPR_ADD:
            s._evt("PORT_ADD", f"Port {port.port_no} added on s{dpid}")
        elif msg.reason == o.OFPPR_DELETE:
            s._evt("PORT_DEL", f"Port {port.port_no} deleted on s{dpid}")
        elif msg.reason == o.OFPPR_MODIFY:
            if port.state & o.OFPPS_LINK_DOWN:
                s._evt("LINK_DOWN", f"Link DOWN on s{dpid} port {port.port_no}")
            else:
                s._evt("LINK_UP", f"Link UP on s{dpid} port {port.port_no}")


print("=" * 50)
print("  SDN Topology Change Detector")
print("=" * 50)
print("  Run: sudo mn --topo tree,depth=2,fanout=2 --controller remote,port=6633")
print()
mgr = AppManager.get_instance()
mgr.load_apps(['os_ken.controller.ofp_handler'])
mgr.applications_cls['TopologyDetector'] = TopologyDetector
try:cfg.CONF(args=['--ofp-tcp-listen-port=6633'],project='os_ken',version='1.0')
except:pass
services = mgr.instantiate_apps(**mgr.create_contexts())
print("[READY] Port 6633 - waiting for switches...\n", flush=True)
hub.joinall(services)
