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

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    from os_ken.base.app_manager import AppManager
    from os_ken.lib import hub

    app_lists = [
        'controller.topology_detector',
        'os_ken.controller.ofp_handler',
        'os_ken.topology.switches',
    ]

    print("=" * 60)
    print("  SDN Topology Detector - Controller Launcher")
    print("=" * 60)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)

    from os_ken import cfg
    try:
        cfg.CONF(args=['--observe-links'], project='os_ken', version='1.0')
    except SystemExit:
        pass

    contexts = app_mgr.create_contexts()
    services = app_mgr.instantiate_apps(**contexts)

    print(f"[INFO] Apps: {list(app_mgr.applications.keys())}")
    print(f"[INFO] Services: {len(services)}")

    # Check if any service died immediately
    for i, s in enumerate(services):
        if hasattr(s, 'dead') and s.dead:
            print(f"[ERROR] Service {i} is already dead!")
            try:
                s.wait()
            except Exception as e:
                import traceback
                traceback.print_exc()

    print("[INFO] Controller running on port 6633...")

    try:
        hub.joinall(services)
        print("[WARN] All services exited! Checking errors...")
        for i, s in enumerate(services):
            try:
                s.wait()
            except Exception as e:
                import traceback
                traceback.print_exc()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()
