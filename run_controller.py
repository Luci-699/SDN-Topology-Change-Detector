#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
"""
import sys
import os

# Add project root to sys.path so 'controller.topology_detector' is importable
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def main():
    from os_ken.base.app_manager import AppManager
    from os_ken.lib import hub

    # Use proper module paths — no manual loading needed
    app_lists = [
        'controller.topology_detector',     # Our app
        'os_ken.controller.ofp_handler',     # OpenFlow handler (port 6633)
        'os_ken.topology.switches',          # Topology discovery (LLDP)
    ]

    print("=" * 60)
    print("  SDN Topology Detector - Controller Launcher")
    print(f"  Loading apps: {app_lists}")
    print("=" * 60)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)

    # Parse config AFTER all modules register their CLI options
    from os_ken import cfg
    try:
        cfg.CONF(args=['--observe-links'], project='os_ken', version='1.0')
    except SystemExit:
        pass

    contexts = app_mgr.create_contexts()
    print(f"[DEBUG] Contexts: {list(contexts.keys())}")

    services = []
    for app in app_mgr.instantiate_apps(**contexts):
        print(f"[DEBUG] Instantiated: {app.__class__.__name__}")
        try:
            t = app.start()
            if t is not None:
                services.append(t)
        except RuntimeError as e:
            print(f"[DEBUG] RuntimeError on {app.__class__.__name__}: {e}")

    print(f"[INFO] Controller running with {len(services)} services. Waiting for switches...")

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
