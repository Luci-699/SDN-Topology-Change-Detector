"""
Custom Mininet Topology for SDN Topology Change Detection
===========================================================
Creates a ring topology with 3 OpenFlow switches and 6 hosts.

Topology:
            h1        h2
             \       /
              s1----s2
             / |    | \
            /  |    |  \
           h3  |    |  h4
               |    |
               s3---+
              / \
             h5  h6

Switches s1, s2, s3 form a ring. Each switch has 2 hosts.
This provides path redundancy for topology change testing.

Usage:
    sudo python topology/custom_topo.py
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class TopologyDetectorTopo(Topo):
    """
    Custom ring topology for topology change detection testing.

    - 3 OpenFlow switches (s1, s2, s3) in a ring
    - 6 hosts (h1-h6), 2 connected to each switch
    - Ring links provide redundancy for failover testing
    """

    def build(self):
        """Build the network topology."""

        # =====================================================================
        # Create switches (OpenFlow 1.3)
        # =====================================================================
        info('*** Creating switches\n')
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')

        # =====================================================================
        # Create hosts with specific IP addresses
        # =====================================================================
        info('*** Creating hosts\n')
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06')

        # =====================================================================
        # Create links between switches (ring topology)
        # Using TCLink for bandwidth/delay control if needed
        # =====================================================================
        info('*** Creating switch-to-switch links (ring)\n')
        self.addLink(s1, s2, port1=3, port2=3)  # s1:port3 <-> s2:port3
        self.addLink(s2, s3, port1=4, port2=3)  # s2:port4 <-> s3:port3
        self.addLink(s3, s1, port1=4, port2=4)  # s3:port4 <-> s1:port4

        # =====================================================================
        # Connect hosts to switches
        # =====================================================================
        info('*** Connecting hosts to switches\n')
        # Switch s1: h1 and h2
        self.addLink(h1, s1, port1=1, port2=1)  # h1 <-> s1:port1
        self.addLink(h2, s1, port1=1, port2=2)  # h2 <-> s1:port2

        # Switch s2: h3 and h4
        self.addLink(h3, s2, port1=1, port2=1)  # h3 <-> s2:port1
        self.addLink(h4, s2, port1=1, port2=2)  # h4 <-> s2:port2

        # Switch s3: h5 and h6
        self.addLink(h5, s3, port1=1, port2=1)  # h5 <-> s3:port1
        self.addLink(h6, s3, port1=1, port2=2)  # h6 <-> s3:port2


def run_topology():
    """Create and start the network with a remote Ryu controller."""
    setLogLevel('info')

    info('*** Creating Topology Detector Network\n')

    # Create topology
    topo = TopologyDetectorTopo()

    # Create network with remote controller (Ryu at 127.0.0.1:6633)
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(
            name,
            ip='127.0.0.1',
            port=6633,
        ),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False,  # We set MACs manually
    )

    # Start the network
    info('*** Starting network\n')
    net.start()

    # Print useful info
    info('\n')
    info('=' * 60 + '\n')
    info('  SDN Topology Change Detector - Mininet Network\n')
    info('  Controller: Ryu at 127.0.0.1:6633\n')
    info('  Switches: s1, s2, s3 (ring topology)\n')
    info('  Hosts: h1-h6 (2 per switch)\n')
    info('=' * 60 + '\n')
    info('\n')
    info('Useful commands:\n')
    info('  pingall              - Test all-to-all connectivity\n')
    info('  h1 ping h6           - Ping between specific hosts\n')
    info('  h1 iperf h6          - Test throughput\n')
    info('  link s1 s2 down      - Simulate link failure\n')
    info('  link s1 s2 up        - Restore link\n')
    info('  sh ovs-ofctl -O OpenFlow13 dump-flows s1  - View flow table\n')
    info('\n')

    # Start CLI
    CLI(net)

    # Cleanup
    info('*** Stopping network\n')
    net.stop()


# Allow running both as module (topos dict) and as script
topos = {'topology_detector': TopologyDetectorTopo}

if __name__ == '__main__':
    run_topology()
