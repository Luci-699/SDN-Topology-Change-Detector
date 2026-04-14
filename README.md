# SDN Topology Change Detector

**Real-Time Topology Monitoring & Change Detection using Ryu OpenFlow Controller + Mininet**

An SDN-based system that detects network topology changes (switch/link up/down) in real-time, implements a MAC learning switch with OpenFlow flow rules, and provides monitoring with event logging.

---

## Problem Statement

In Software-Defined Networks (SDN), the controller needs to maintain an accurate view of the network topology. Network changes such as link failures, switch disconnections, or new device additions must be detected and responded to in real-time to ensure network reliability.

This project implements an **OpenFlow 1.3 controller** using the **Ryu framework** that:
1. Discovers the network topology using **LLDP** (Link Layer Discovery Protocol)
2. Detects topology changes (switch join/leave, link add/delete) in **real-time**
3. Implements a **MAC learning switch** with proper flow rule installation
4. Logs all topology events with timestamps
5. Provides a **web dashboard** for visualization

### Why This Design?

- **Ring topology (3 switches)**: Provides path redundancy, enabling meaningful topology change testing. When one link fails, traffic can still reach destinations via alternate paths.
- **Ryu controller**: Lightweight, well-documented Python framework with built-in topology discovery.
- **OpenFlow 1.3**: Industry standard for SDN switch-controller communication.

---

## Architecture

```
+---------------------------------------------+
|              Ryu Controller                  |
|  +----------------+  +--------------------+ |
|  | Learning Switch |  | Topology Detector  | |
|  | (packet_in)     |  | (LLDP events)      | |
|  +----------------+  +--------------------+ |
|  +----------------+  +--------------------+ |
|  | Flow Monitor   |  | REST API           | |
|  | (flow stats)   |  | (/topology /events)| |
|  +----------------+  +--------------------+ |
+-----------------------+---------------------+
                        | OpenFlow 1.3
          +-------------+-------------+
          |             |             |
     +----+----+  +----+----+  +----+----+
     |   s1    |--|   s2    |--|   s3    |
     | (OVS)   |  | (OVS)   |  | (OVS)   |
     +--+---+--+  +--+---+--+  +--+---+--+
        |   |        |   |        |   |
       h1  h2       h3  h4       h5  h6

     Ring: s1--s2, s2--s3, s3--s1
```

### Key SDN Concepts

| Concept | Description |
|---------|-------------|
| **OpenFlow** | Protocol for controller-switch communication. Controller installs flow rules on switches. |
| **Table-miss entry** | Default flow rule (priority=0) that sends unmatched packets to the controller. |
| **packet_in** | Event triggered when a switch receives a packet matching the table-miss entry. |
| **Flow Rule** | match(fields) -> action(output port). Installed via `OFPFlowMod`. |
| **LLDP** | Link Layer Discovery Protocol used by Ryu to discover switch-to-switch links. |
| **MAC Learning** | Controller learns which port a MAC address is on by observing packet_in source MACs. |

---

## Project Structure

```
orange-project/
+-- controller/
|   +-- topology_detector.py      # Main Ryu app (learning switch + topology detection)
+-- topology/
|   +-- custom_topo.py            # Custom Mininet ring topology (3 switches, 6 hosts)
+-- dashboard/
|   +-- web_app.py                # Flask web dashboard
|   +-- templates/index.html      # Dashboard UI
|   +-- static/style.css          # Dark theme styles
+-- tests/
|   +-- test_connectivity.sh      # Ping tests
|   +-- test_throughput.sh        # iperf tests
|   +-- test_topo_change.sh       # Topology change simulation
|   +-- dump_flows.sh             # Flow table dump script
+-- logs/
|   +-- topology_events.log       # Event log file (generated at runtime)
+-- screenshots/                  # Proof of execution screenshots
+-- requirements.txt
+-- README.md
```

---

## Setup Instructions (Ubuntu VM)

### 1. Install Mininet

```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch
```

Verify installation:
```bash
sudo mn --test pingall
```

### 2. Install Ryu Controller

```bash
sudo apt-get install -y python3-pip python3-dev
pip3 install ryu
```

Verify installation:
```bash
ryu-manager --version
```

### 3. Install Project Dependencies

```bash
cd orange-project
pip3 install -r requirements.txt
```

### 4. Install Additional Tools (for testing)

```bash
sudo apt-get install -y iperf net-tools
```

---

## Execution Steps

You need **3 terminal windows** on your Linux VM:

### Terminal 1: Start Ryu Controller

```bash
cd orange-project
ryu-manager controller/topology_detector.py --observe-links --verbose
```

The `--observe-links` flag enables LLDP-based topology discovery.

Expected output:
```
loading app controller/topology_detector.py
loading app ryu.topology.switches
=== Topology Detector Controller Started ===
```

### Terminal 2: Start Mininet

```bash
cd orange-project
sudo python3 topology/custom_topo.py
```

Expected output:
```
*** Creating Topology Detector Network
*** Creating switches
*** Creating hosts
*** Starting network
============================================================
  SDN Topology Change Detector - Mininet Network
  Controller: Ryu at 127.0.0.1:6633
  Switches: s1, s2, s3 (ring topology)
  Hosts: h1-h6 (2 per switch)
============================================================
mininet>
```

In the Ryu terminal, you should see:
```
[SWITCH_CONNECTED] Switch s1 connected to controller
[SWITCH_CONNECTED] Switch s2 connected to controller
[SWITCH_CONNECTED] Switch s3 connected to controller
[LINK_ADD] Link UP: s1(port 3) <-> s2(port 3)
[LINK_ADD] Link UP: s2(port 4) <-> s3(port 3)
[LINK_ADD] Link UP: s3(port 4) <-> s1(port 4)
```

### Terminal 3: Start Dashboard (optional)

```bash
cd orange-project
python3 dashboard/web_app.py
```

Open browser: `http://<vm-ip>:9090`

---

## Testing & Expected Output

### Test 1: Connectivity (pingall)

In Mininet CLI:
```
mininet> pingall
```

Expected output:
```
*** Ping: testing ping reachability
h1 -> h2 h3 h4 h5 h6
h2 -> h1 h3 h4 h5 h6
h3 -> h1 h2 h4 h5 h6
h4 -> h1 h2 h3 h5 h6
h5 -> h1 h2 h3 h4 h6
h6 -> h1 h2 h3 h4 h5
*** Results: 0% dropped (30/30 received)
```

### Test 2: Flow Tables

```
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

Expected output (after pingall):
```
 cookie=0x0, duration=X.Xs, table=0, n_packets=X, n_bytes=X,
   priority=1,in_port=1,dl_src=00:00:00:00:00:01,dl_dst=00:00:00:00:00:02
   actions=output:2
 cookie=0x0, duration=X.Xs, table=0, n_packets=X, n_bytes=X,
   priority=0 actions=CONTROLLER:65535
```

This shows:
- **priority=1** flow rules: Learned MAC-to-port mappings with specific match/action
- **priority=0** table-miss entry: Catches unmatched packets and sends to controller

### Test 3: Latency (ping)

```
mininet> h1 ping -c 10 h6
```

Expected: Shows round-trip time (RTT) in milliseconds.

### Test 4: Throughput (iperf)

```
mininet> iperf h1 h6
```

Expected: Shows throughput in Mbits/sec or Gbits/sec.

### Test 5: Topology Change Detection

```
mininet> link s1 s2 down
```

In Ryu terminal, you should see:
```
[LINK_DELETE] Link DOWN: s1(port 3) <-> s2(port 3)
```

Then restore:
```
mininet> link s1 s2 up
```

In Ryu terminal:
```
[LINK_ADD] Link UP: s1(port 3) <-> s2(port 3)
```

### Test 6: View Event Log

```bash
cat logs/topology_events.log
```

Expected format:
```
[2026-04-14 19:30:00] ============================================================
[2026-04-14 19:30:00]   SDN Topology Detector - Session Started
[2026-04-14 19:30:00] ============================================================
[2026-04-14 19:30:01] SWITCH_CONNECTED: Switch s1 connected to controller
[2026-04-14 19:30:01] SWITCH_CONNECTED: Switch s2 connected to controller
[2026-04-14 19:30:01] SWITCH_CONNECTED: Switch s3 connected to controller
[2026-04-14 19:30:02] LINK_ADD: Link UP: s1(port 3) <-> s2(port 3)
[2026-04-14 19:30:10] HOST_DISCOVERED: Host 10.0.0.1 (MAC: 00:00:00:00:00:01) found on s1 port 1
[2026-04-14 19:32:00] LINK_DELETE: Link DOWN: s1(port 3) <-> s2(port 3)
[2026-04-14 19:33:00] LINK_ADD: Link UP: s1(port 3) <-> s2(port 3)
```

---

## Screenshots / Proof of Execution

> Add your screenshots here after running the demo on your VM.

### 1. Controller Starting & Switch Connections
<!-- ![Controller Output](screenshots/controller_start.png) -->

### 2. Mininet Topology Created
<!-- ![Mininet Start](screenshots/mininet_start.png) -->

### 3. Pingall Results (0% dropped)
<!-- ![Pingall](screenshots/pingall_results.png) -->

### 4. Flow Tables (ovs-ofctl dump-flows)
<!-- ![Flow Tables](screenshots/flow_tables.png) -->

### 5. Topology Change Detection (link down/up)
<!-- ![Topology Change](screenshots/topo_change.png) -->

### 6. iperf Throughput Results
<!-- ![iperf](screenshots/iperf_results.png) -->

### 7. Event Log File
<!-- ![Event Log](screenshots/event_log.png) -->

### 8. Web Dashboard
<!-- ![Dashboard](screenshots/dashboard.png) -->

---

## Flow Rule Details

### Table-Miss Entry (installed on switch connection)
```
Match:   * (wildcard - matches all packets)
Action:  output:CONTROLLER
Priority: 0 (lowest)
Timeout: none (permanent)
```

### Learned MAC Flow Rules (installed on packet_in)
```
Match:   in_port=X, eth_src=SRC_MAC, eth_dst=DST_MAC
Action:  output:Y
Priority: 1 (higher than table-miss)
idle_timeout: 300 seconds (removed after 5 min inactivity)
hard_timeout: 600 seconds (absolute max 10 min lifetime)
```

### Why These Parameters?
- **priority=1**: Higher than table-miss (0), so specific rules take precedence
- **idle_timeout=300**: Stale entries are cleaned up automatically
- **hard_timeout=600**: Prevents permanent stale entries even with periodic traffic
- **Match on eth_src + eth_dst + in_port**: Most specific match for L2 forwarding

---

## References

1. Ryu SDN Framework Documentation - https://ryu.readthedocs.io/
2. OpenFlow 1.3 Specification - https://opennetworking.org/
3. Mininet Walkthrough - http://mininet.org/walkthrough/
4. Open vSwitch Documentation - https://docs.openvswitch.org/
5. "Software-Defined Networking: A Comprehensive Survey" - D. Kreutz et al., IEEE 2015
#   S D N - T o p o l o g y - C h a n g e - D e t e c t o r  
 