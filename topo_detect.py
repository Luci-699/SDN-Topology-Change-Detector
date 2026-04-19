import eventlet
eventlet.monkey_patch()
import os
from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types
from os_ken.lib import hub
from os_ken.base.app_manager import AppManager
from os_ken import cfg

class T(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(s,*a,**k):
        super().__init__(*a,**k); s.mac={}
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def f(s,ev):
        dp=ev.msg.datapath;o=dp.ofproto;p=dp.ofproto_parser
        dp.send_msg(p.OFPFlowMod(datapath=dp,priority=0,match=p.OFPMatch(),instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,[p.OFPActionOutput(o.OFPP_CONTROLLER,o.OFPCML_NO_BUFFER)])]))
        print(f'SWITCH {dp.id} UP',flush=True)
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def pi(s,ev):
        msg=ev.msg;dp=msg.datapath;o=dp.ofproto;p=dp.ofproto_parser;pin=msg.match['in_port']
        pkt=packet.Packet(msg.data);eth=pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype==ether_types.ETH_TYPE_LLDP:return
        s.mac.setdefault(dp.id,{});s.mac[dp.id][eth.src]=pin
        out=s.mac[dp.id].get(eth.dst,o.OFPP_FLOOD);acts=[p.OFPActionOutput(out)]
        if out!=o.OFPP_FLOOD:
            dp.send_msg(p.OFPFlowMod(datapath=dp,priority=1,match=p.OFPMatch(in_port=pin,eth_dst=eth.dst,eth_src=eth.src),instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,acts)],idle_timeout=60,hard_timeout=120))
        dp.send_msg(p.OFPPacketOut(datapath=dp,buffer_id=msg.buffer_id,in_port=pin,actions=acts,data=msg.data if msg.buffer_id==o.OFP_NO_BUFFER else None))

mgr=AppManager.get_instance()
mgr.load_apps(['os_ken.controller.ofp_handler'])
mgr.applications_cls['T']=T
try:cfg.CONF(args=['--ofp-tcp-listen-port=6633'],project='os_ken',version='1.0')
except:pass
services=mgr.instantiate_apps(**mgr.create_contexts())
print('READY on 6633',flush=True)
hub.joinall(services)
