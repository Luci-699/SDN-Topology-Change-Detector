#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
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

    app_lists = [
        'controller.topology_detector',
        'os_ken.controller.ofp_handler',
    ]

    print("=" * 60)
    print("  SDN Topology Detector - Controller Launcher")
    print("=" * 60)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)

    from os_ken import cfg
    try:
        cfg.CONF(args=['--ofp-tcp-listen-port=6633'],
                 project='os_ken', version='1.0')
    except SystemExit:
        pass

    contexts = app_mgr.create_contexts()
    services = app_mgr.instantiate_apps(**contexts)

    print(f"[INFO] Apps: {list(app_mgr.applications.keys())}")
    print(f"[INFO] Services: {len(services)}")
    print("[INFO] Controller running on port 6633...")

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()
