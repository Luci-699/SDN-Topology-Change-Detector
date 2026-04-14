"""
Web Dashboard for SDN Topology Detector
=========================================
Flask web application that fetches topology data from the
Ryu controller's REST API and displays it in an interactive UI.

Usage:
    python dashboard/web_app.py

Access at http://<vm-ip>:8080
"""

import json
import requests
from flask import Flask, render_template, jsonify

app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static',
)

# Ryu controller REST API base URL
RYU_API_URL = 'http://127.0.0.1:8080'


@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('index.html')


@app.route('/api/topology')
def api_topology():
    """Proxy topology data from Ryu REST API."""
    try:
        resp = requests.get(f'{RYU_API_URL}/topology', timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e), 'switches': [], 'links': [], 'hosts': []})


@app.route('/api/events')
def api_events():
    """Proxy event data from Ryu REST API."""
    try:
        resp = requests.get(f'{RYU_API_URL}/events', timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify([])


@app.route('/api/flows')
def api_flows():
    """Proxy flow table data from Ryu REST API."""
    try:
        resp = requests.get(f'{RYU_API_URL}/flows', timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    print("=" * 50)
    print("  SDN Topology Detector - Web Dashboard")
    print("  Open: http://localhost:9090")
    print("=" * 50)
    app.run(host='0.0.0.0', port=9090, debug=False)
