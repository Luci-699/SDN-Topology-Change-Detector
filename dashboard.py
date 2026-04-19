#!/usr/bin/env python3
"""
SDN Topology Dashboard - Standalone web monitor
Reads logs/topology_events.log and serves a live dashboard.
Run:  python3 dashboard.py
Open: http://127.0.0.1:9090
"""
import http.server
import json
import os
import re
from datetime import datetime

PORT = 9090
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'topology_events.log')

HTML_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SDN Topology Change Detector</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family:'Inter',sans-serif;
    background:#0f1923;
    color:#e0e6ed;
    min-height:100vh;
  }
  .header {
    background:linear-gradient(135deg,#1a2332 0%,#0d1b2a 100%);
    padding:20px 30px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    border-bottom:1px solid #1e3a5f;
    box-shadow:0 2px 20px rgba(0,0,0,0.3);
  }
  .header .logo {
    display:flex; align-items:center; gap:14px;
  }
  .header .logo-icon {
    width:42px; height:42px;
    background:linear-gradient(135deg,#3b82f6,#06b6d4);
    border-radius:12px;
    display:flex; align-items:center; justify-content:center;
    font-size:20px;
  }
  .header h1 { font-size:1.3rem; font-weight:700; color:#3b82f6; }
  .header p { font-size:0.75rem; color:#64748b; text-transform:uppercase; letter-spacing:1px; }
  .btn-refresh {
    background:linear-gradient(135deg,#3b82f6,#2563eb);
    color:#fff; border:none; padding:10px 22px;
    border-radius:8px; cursor:pointer; font-weight:600;
    font-size:0.85rem; transition:all 0.2s;
  }
  .btn-refresh:hover { transform:translateY(-1px); box-shadow:0 4px 15px rgba(59,130,246,0.4); }
  .container { max-width:1200px; margin:0 auto; padding:24px; }
  .stats {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:16px;
    margin-bottom:24px;
  }
  .stat-card {
    background:linear-gradient(135deg,#1a2332,#162032);
    border:1px solid #1e3a5f;
    border-radius:14px;
    padding:20px;
    display:flex; align-items:center; gap:16px;
    transition:all 0.3s;
  }
  .stat-card:hover { border-color:#3b82f6; transform:translateY(-2px); }
  .stat-icon {
    width:48px; height:48px;
    border-radius:12px;
    display:flex; align-items:center; justify-content:center;
    font-size:22px;
  }
  .stat-icon.switches { background:rgba(59,130,246,0.15); color:#3b82f6; }
  .stat-icon.links { background:rgba(239,68,68,0.15); color:#ef4444; }
  .stat-icon.hosts { background:rgba(16,185,129,0.15); color:#10b981; }
  .stat-icon.events { background:rgba(245,158,11,0.15); color:#f59e0b; }
  .stat-value { font-size:1.8rem; font-weight:700; }
  .stat-label { font-size:0.75rem; color:#64748b; text-transform:uppercase; letter-spacing:1px; }
  .grid {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:20px;
  }
  .card {
    background:linear-gradient(135deg,#1a2332,#162032);
    border:1px solid #1e3a5f;
    border-radius:14px;
    padding:24px;
  }
  .card h2 {
    font-size:0.85rem; text-transform:uppercase;
    letter-spacing:1.5px; color:#64748b;
    margin-bottom:18px; font-weight:600;
  }
  .topo-visual {
    display:flex; flex-direction:column; align-items:center;
    gap:8px; padding:20px 0;
  }
  .switch-node {
    background:linear-gradient(135deg,#3b82f6,#2563eb);
    padding:8px 20px; border-radius:8px;
    font-weight:600; font-size:0.85rem;
    box-shadow:0 2px 10px rgba(59,130,246,0.3);
  }
  .host-node {
    background:linear-gradient(135deg,#10b981,#059669);
    padding:6px 14px; border-radius:6px;
    font-size:0.8rem; font-weight:500;
  }
  .link-line {
    width:2px; height:20px;
    background:linear-gradient(to bottom,#3b82f6,#06b6d4);
  }
  .link-h { height:2px; width:60px; background:#3b82f6; }
  .tree-row { display:flex; gap:20px; align-items:center; }
  .tree-branch { display:flex; flex-direction:column; align-items:center; gap:6px; }
  .event-list {
    max-height:380px;
    overflow-y:auto;
    scrollbar-width:thin;
    scrollbar-color:#1e3a5f transparent;
  }
  .event-item {
    display:flex; align-items:center; gap:12px;
    padding:10px 14px;
    border-bottom:1px solid #1e3a5f22;
    transition:background 0.2s;
  }
  .event-item:hover { background:rgba(59,130,246,0.05); }
  .event-dot {
    width:10px; height:10px; border-radius:50%; flex-shrink:0;
  }
  .event-dot.SWITCH_UP { background:#3b82f6; }
  .event-dot.HOST_FOUND { background:#10b981; }
  .event-dot.LINK_DOWN { background:#ef4444; }
  .event-dot.LINK_UP { background:#22c55e; }
  .event-dot.SYSTEM { background:#64748b; }
  .event-dot.PORT_ADD, .event-dot.PORT_DEL { background:#f59e0b; }
  .event-type { font-weight:600; font-size:0.82rem; min-width:100px; }
  .event-detail { font-size:0.82rem; color:#94a3b8; flex:1; }
  .event-time { font-size:0.75rem; color:#475569; }
  .status-bar {
    margin-top:20px; padding:12px 20px;
    background:#1a2332; border:1px solid #1e3a5f;
    border-radius:10px;
    display:flex; justify-content:space-between;
    font-size:0.8rem; color:#64748b;
  }
  .status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .status-dot.online { background:#22c55e; }
  .status-dot.offline { background:#ef4444; }
  .no-events { color:#475569; text-align:center; padding:40px; font-size:0.9rem; }
  @media (max-width:768px) {
    .stats { grid-template-columns:repeat(2,1fr); }
    .grid { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
<div class="header">
  <div class="logo">
    <div class="logo-icon">&#9878;</div>
    <div>
      <h1>SDN Topology Change Detector</h1>
      <p>OsKen OpenFlow Controller + Mininet</p>
    </div>
  </div>
  <button class="btn-refresh" onclick="fetchData()">Refresh</button>
</div>

<div class="container">
  <div class="stats">
    <div class="stat-card">
      <div class="stat-icon switches">&#9634;</div>
      <div><div class="stat-value" id="sw-count">0</div><div class="stat-label">Switches</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon links">&#10005;</div>
      <div><div class="stat-value" id="link-count">0</div><div class="stat-label">Links</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon hosts">&#9899;</div>
      <div><div class="stat-value" id="host-count">0</div><div class="stat-label">Hosts</div></div>
    </div>
    <div class="stat-card">
      <div class="stat-icon events">&#9889;</div>
      <div><div class="stat-value" id="event-count">0</div><div class="stat-label">Events</div></div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Network Topology</h2>
      <div class="topo-visual" id="topo-viz">
        <div class="switch-node">s1 (root)</div>
        <div class="tree-row">
          <div class="link-line"></div>
          <div class="link-line"></div>
        </div>
        <div class="tree-row">
          <div class="tree-branch">
            <div class="switch-node">s2</div>
            <div class="tree-row">
              <div class="host-node">h1</div>
              <div class="host-node">h2</div>
            </div>
          </div>
          <div class="tree-branch">
            <div class="switch-node">s3</div>
            <div class="tree-row">
              <div class="host-node">h3</div>
              <div class="host-node">h4</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Topology Events</h2>
      <div class="event-list" id="event-list">
        <div class="no-events">Waiting for events... Start the controller first.</div>
      </div>
    </div>
  </div>

  <div class="status-bar">
    <div><span class="status-dot" id="status-dot"></span><span id="status-text">Checking...</span></div>
    <div>Auto-refresh: 3s | Port: 9090</div>
  </div>
</div>

<script>
async function fetchData() {
  try {
    const res = await fetch('/api/events');
    const data = await res.json();
    document.getElementById('sw-count').textContent = data.switches;
    document.getElementById('link-count').textContent = data.links;
    document.getElementById('host-count').textContent = data.hosts;
    document.getElementById('event-count').textContent = data.total;
    document.getElementById('status-dot').className = 'status-dot online';
    document.getElementById('status-text').textContent = 'Controller Active';

    const el = document.getElementById('event-list');
    if (data.events.length === 0) {
      el.innerHTML = '<div class="no-events">No events yet. Start Mininet and run pingall.</div>';
    } else {
      el.innerHTML = data.events.reverse().map(e =>
        `<div class="event-item">
          <div class="event-dot ${e.type}"></div>
          <div class="event-type">${e.type}</div>
          <div class="event-detail">${e.detail}</div>
          <div class="event-time">${e.time}</div>
        </div>`
      ).join('');
    }
  } catch(err) {
    document.getElementById('status-dot').className = 'status-dot offline';
    document.getElementById('status-text').textContent = 'Dashboard Error';
  }
}
fetchData();
setInterval(fetchData, 3000);
</script>
</body>
</html>'''


def parse_log():
    events = []
    switches = set()
    hosts = set()
    link_downs = set()

    if not os.path.exists(LOG_FILE):
        return {'events': [], 'switches': 0, 'hosts': 0, 'links': 0, 'total': 0}

    with open(LOG_FILE, 'r') as f:
        for line in f:
            m = re.match(r'\[.*?\]\s*(\w+):\s*(.*)', line.strip())
            if not m:
                continue
            etype, detail = m.group(1), m.group(2)

            # Extract time from log
            tm = re.match(r'\[([\d:, -]+)\]', line)
            time_str = tm.group(1).strip().split(' ')[-1] if tm else ''

            events.append({'type': etype, 'detail': detail, 'time': time_str})

            if etype == 'SWITCH_UP':
                sm = re.search(r's(\d+)', detail)
                if sm:
                    switches.add(sm.group(1))
            elif etype == 'HOST_FOUND':
                hosts.add(detail.split('(')[0].strip() if '(' in detail else detail)
            elif etype == 'LINK_DOWN':
                link_downs.add(detail)
            elif etype == 'LINK_UP':
                link_downs.discard(detail)

    # Tree topo: links = switches - 1 (tree), minus downs
    n_switches = len(switches)
    tree_links = max(0, n_switches - 1)
    active_links = max(0, tree_links - len(link_downs))

    return {
        'events': events[-100:],
        'switches': n_switches,
        'hosts': len(hosts),
        'links': active_links,
        'total': len(events)
    }


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/events':
            data = parse_log()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

    def log_message(self, format, *args):
        pass  # Suppress request logs


if __name__ == '__main__':
    print(f'Dashboard running at http://127.0.0.1:{PORT}')
    print(f'Reading logs from: {LOG_FILE}')
    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nDashboard stopped.')
