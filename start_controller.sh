#!/bin/bash
# SDN Topology Change Detector - Controller Launcher
# Usage: bash start_controller.sh
# Then:  sudo mn --topo tree,depth=2,fanout=2 --controller remote,port=6633

cd "$(dirname "$0")"
source ~/sdn-env/bin/activate

python3 -c "
import eventlet; eventlet.monkey_patch()
import os
os.makedirs('logs', exist_ok=True)
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types, arp, ipv4
from os_ken.lib import hub
from os_ken.base.app_manager import AppManager
from os_ken import cfg
from datetime import datetime

class TopologyDetector(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(s,*a,**k):
        super().__init__(*a,**k);s.mac={};s.switches={};s.hosts={};s.events=[];s.datapaths={}
        s.logf=open('logs/topology_events.log','a')
        s._e('SYSTEM','Controller initialized')
    def _e(s,t,d):
        ts=datetime.now().strftime('%H:%M:%S');line=f'[{ts}] {t}: {d}'
        s.logf.write(line+chr(10));s.logf.flush()
        s.events.append({'time':ts,'type':t,'detail':d})
        print(f'  {line}',flush=True)
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def sf(s,ev):
        dp=ev.msg.datapath;o=dp.ofproto;p=dp.ofproto_parser;dpid=dp.id
        dp.send_msg(p.OFPFlowMod(datapath=dp,priority=0,match=p.OFPMatch(),instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,[p.OFPActionOutput(o.OFPP_CONTROLLER,o.OFPCML_NO_BUFFER)])]))
        s.mac[dpid]={};s.datapaths[dpid]=dp;s.switches[dpid]=datetime.now().strftime('%H:%M:%S')
        s._e('SWITCH_UP',f'Switch s{dpid} connected')
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def pi(s,ev):
        msg=ev.msg;dp=msg.datapath;o=dp.ofproto;p=dp.ofproto_parser;pin=msg.match['in_port'];dpid=dp.id
        pkt=packet.Packet(msg.data);eth=pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype==ether_types.ETH_TYPE_LLDP:return
        if eth.dst.startswith('33:33:'):return
        src,dst=eth.src,eth.dst;s.mac.setdefault(dpid,{});s.mac[dpid][src]=pin
        if src not in s.hosts:
            ip=None;a=pkt.get_protocol(arp.arp)
            if a:ip=a.src_ip
            v=pkt.get_protocol(ipv4.ipv4)
            if v:ip=v.src
            if ip:s.hosts[src]={'mac':src,'ip':ip,'sw':dpid,'port':pin};s._e('HOST_FOUND',f'{ip} on s{dpid}:{pin}')
        out=s.mac[dpid].get(dst,o.OFPP_FLOOD);acts=[p.OFPActionOutput(out)]
        if out!=o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(datapath=dp,priority=1,match=p.OFPMatch(in_port=pin,eth_dst=dst,eth_src=src),instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,acts)],idle_timeout=60,hard_timeout=120))
        dp.send_msg(p.OFPPacketOut(datapath=dp,buffer_id=msg.buffer_id,in_port=pin,actions=acts,data=msg.data if msg.buffer_id==o.OFP_NO_BUFFER else None))
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def ps(s,ev):
        msg=ev.msg;dp=msg.datapath;o=dp.ofproto;port=msg.desc
        if msg.reason==o.OFPPR_MODIFY:
            if port.state&o.OFPPS_LINK_DOWN:s._e('LINK_DOWN',f'Link DOWN s{dp.id} port {port.port_no}')
            else:s._e('LINK_UP',f'Link UP s{dp.id} port {port.port_no}')

print('='*50)
print('  SDN Topology Change Detector')
print('='*50)
print('  Run: sudo mn --topo tree,depth=2,fanout=2 --controller remote,port=6633')
print()
mgr=AppManager.get_instance()
mgr.load_apps(['os_ken.controller.ofp_handler'])
mgr.applications_cls['TopologyDetector']=TopologyDetector
try:cfg.CONF(args=['--ofp-tcp-listen-port=6633'],project='os_ken',version='1.0')
except:pass
services=mgr.instantiate_apps(**mgr.create_contexts())
print('[READY] Port 6633 - waiting for switches...',flush=True)
print()
hub.joinall(services)
"
