#!/usr/bin/env python3
"""
Launcher for SDN Topology Detector controller.
Uses manual app registration (proven to work vs load_apps bug).
"""
import sys
import os
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import eventlet
eventlet.monkey_patch()

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s %(message)s')

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    from os_ken.base.app_manager import AppManager
    from os_ken.lib import hub
    from os_ken import cfg

    # Import our controller class directly
    from controller.topology_detector import TopologyDetector

    print("=" * 60)
    print("  SDN Topology Detector - Controller")
    print("=" * 60)

    mgr = AppManager.get_instance()

    # Load framework apps via load_apps
    mgr.load_apps(['os_ken.controller.ofp_handler'])

    # Register our app manually (bypasses load_apps bug)
    mgr.applications_cls['TopologyDetector'] = TopologyDetector

    # Configure port
    try:
        cfg.CONF(args=['--observe-links', '--ofp-tcp-listen-port=6633'],
                 project='os_ken', version='1.0')
    except SystemExit:
        pass

    contexts = mgr.create_contexts()
    services = mgr.instantiate_apps(**contexts)

    print(f"[INFO] Apps: {list(mgr.applications.keys())}")
    print("[INFO] Controller running on port 6633...")
    print("[INFO] Waiting for switches to connect...")

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()
