#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.

Usage:
    python3 run_controller.py
"""
import sys
import os

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

    # Parse config AFTER all modules register CLI options
    from os_ken import cfg
    try:
        cfg.CONF(args=['--observe-links'], project='os_ken', version='1.0')
    except SystemExit:
        pass

    contexts = app_mgr.create_contexts()

    # Let instantiate_apps create and register the apps
    for app in app_mgr.instantiate_apps(**contexts):
        pass  # Apps are registered internally

    # Now manually start ALL registered apps
    services = []
    for app_name, app in app_mgr.applications.items():
        print(f"[INFO] Starting app: {app_name} ({app.__class__.__name__})")
        try:
            t = app.start()
            if t is not None:
                services.append(t)
                print(f"[INFO]   -> started with service thread")
        except RuntimeError as e:
            print(f"[INFO]   -> already running ({e})")

    print(f"\n[INFO] Controller running with {len(services)} services.")
    print("[INFO] Waiting for switches on port 6633...")

    try:
        if services:
            hub.joinall(services)
        else:
            while True:
                hub.sleep(1)
    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == '__main__':
    main()
