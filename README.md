# SDN Topology Change Detector

## Problem Statement
In Software-Defined Networks (SDN), topology changes such as switch failures and link disconnections must be detected and handled in real time. This project implements an **OsKen-based SDN controller** that monitors the network topology, detects changes (link up/down, switch connect/disconnect), and dynamically updates forwarding behavior using OpenFlow 1.3.

## Architecture

```
┌─────────────────────────────────────────┐
│           OsKen Controller              │
│  ┌─────────────────────────────────┐    │
│  │   TopologyDetector App          │    │
│  │  - MAC Learning (L2 Switch)     │    │
│  │  - Switch Connect Detection     │    │
│  │  - Host Discovery (ARP/IP)      │    │
│  │  - Event Logging                │    │
│  └─────────────────────────────────┘    │
│           Port 6633 (OpenFlow 1.3)      │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───┴──┐  ┌───┴──┐  ┌───┴──┐
│  s1  │──│  s2  │  │  s3  │
│(root)│  │      │  │      │
└──┬───┘  └──┬───┘  └──┬───┘
   │      ┌──┴──┐   ┌──┴──┐
   │      │h1 h2│   │h3 h4│
   │      └─────┘   └─────┘
   └──────────────────────┘
       Tree Topology (depth=2, fanout=2)
```

## Features
- **MAC Learning Switch**: Learns source MAC addresses and installs flow rules for known destinations
- **Switch Detection**: Detects when switches connect to the controller
- **Topology Change Detection**: Demonstrates network behavior changes when links fail/recover
- **Flow Rule Management**: Installs OpenFlow 1.3 flow rules with idle/hard timeouts
- **Event Logging**: Logs all topology events to `logs/topology_events.log`

## Requirements
- **OS**: Linux (Kali Linux / Ubuntu)
- **Python**: 3.10+
- **Mininet**: 2.3+
- **OsKen**: SDN framework (`pip install os-ken`)
- **Open vSwitch**: 2.x+

## Setup

### 1. Install Dependencies
```bash
sudo apt update
sudo apt install mininet openvswitch-switch -y
python3 -m venv ~/sdn-env
source ~/sdn-env/bin/activate
pip install os-ken
```

### 2. Verify Installation
```bash
mn --version
python3 -c "import os_ken; print('OsKen OK')"
```

## Running the Project

### Terminal 1 — Start Controller
```bash
source ~/sdn-env/bin/activate
cd ~/orange-project
bash start_controller.sh
```
Wait for: `[READY] Port 6633 - waiting for switches...`

### Terminal 2 — Start Network
```bash
sudo service openvswitch-switch start
sudo mn -c
sudo mn --topo tree,depth=2,fanout=2 --controller remote,port=6633
```

## Demo Scenarios

### Scenario 1: Normal Network (Full Connectivity)
```
mininet> pingall
*** Results: 0% dropped (12/12 received)
```
All hosts can communicate through the SDN controller.

### Scenario 2: Link Failure Detection
```
mininet> link s1 s2 down
mininet> pingall
*** Results: 66% dropped (4/12 received)
```
When the link between s1 and s2 goes down:
- h1 ↔ h2 can still communicate (same switch s2)
- h3 ↔ h4 can still communicate (same switch s3)
- Cross-switch communication fails (no path between s2 and s3)

### Scenario 3: Link Recovery
```
mininet> link s1 s2 up
mininet> pingall
*** Results: 0% dropped (12/12 received)
```
Full connectivity is restored when the link comes back up.

### Additional Commands
```
mininet> h1 ping h4                              # Ping specific hosts
mininet> h1 iperf h4                             # Test throughput
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1  # View flow rules
```

## Controller Output
When running, the controller displays:
```
SWITCH 1 UP      ← Switch s1 connected
SWITCH 2 UP      ← Switch s2 connected
SWITCH 3 UP      ← Switch s3 connected
```

## Project Structure
```
orange-project/
├── start_controller.sh          # Main launcher script
├── topo_detect.py               # Controller source code
├── controller/
│   ├── __init__.py
│   ├── topology_detector.py     # Full controller module
│   └── simple_switch.py         # Basic L2 switch
├── topology/
│   ├── __init__.py
│   └── custom_topo.py           # Custom ring topology
├── logs/
│   └── topology_events.log      # Event log file
├── tests/
│   ├── test_connectivity.sh     # Connectivity test
│   └── test_topo_change.sh      # Topology change test
├── screenshots/                 # Demo screenshots
├── requirements.txt
└── README.md
```

## How It Works

1. **Controller starts** and listens on port 6633 (OpenFlow 1.3)
2. **Switches connect** and controller installs table-miss flow rules
3. **Packet-In events**: Unknown packets are sent to controller
4. **MAC Learning**: Controller learns source MAC → port mappings
5. **Flow Installation**: Known destinations get direct flow rules (bypassing controller)
6. **Topology Changes**: When links fail, affected flow rules expire and traffic is re-routed

## Key Code Explanation

### Table-Miss Flow Rule
```python
dp.send_msg(p.OFPFlowMod(datapath=dp, priority=0, match=p.OFPMatch(),
    instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,
        [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])]))
```
This rule sends all unmatched packets to the controller for processing.

### MAC Learning
```python
self.mac[dpid][src] = pin          # Learn: source MAC → input port
out = self.mac[dpid].get(dst, FLOOD)  # Lookup: destination MAC → output port
```

### Flow Rule Installation
```python
dp.send_msg(p.OFPFlowMod(datapath=dp, priority=1,
    match=p.OFPMatch(in_port=pin, eth_dst=dst, eth_src=src),
    instructions=[...], idle_timeout=60, hard_timeout=120))
```

## Viva Explanation

> "This project uses the OsKen SDN controller framework to detect topology changes in real time. The controller listens for OpenFlow switch connections and implements MAC-based learning to forward packets. When a link goes down, affected hosts lose connectivity, demonstrating dynamic topology change detection. When the link is restored, the controller re-learns paths and connectivity is restored. All events are logged for monitoring."

## Technologies Used
- **OsKen** (os-ken): OpenFlow controller framework (Python)
- **Mininet**: Network emulator for SDN
- **Open vSwitch**: Software-defined switch
- **OpenFlow 1.3**: Protocol for controller-switch communication

## Author
SDN Topology Change Detector — Computer Networks Project
