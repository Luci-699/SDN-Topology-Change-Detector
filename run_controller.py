#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
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

    # Parse config AFTER loading
    from os_ken import cfg
    try:
        cfg.CONF(args=['--observe-links'], project='os_ken', version='1.0')
    except SystemExit:
        pass

    # Try to manually instantiate EACH app to see errors
    for app_name, cls in app_mgr.applications_cls.items():
        print(f"\n[DEBUG] Trying to instantiate: {app_name} ({cls.__name__})")
        try:
            app = cls()
            print(f"[DEBUG] SUCCESS: {cls.__name__}")
        except Exception as e:
            print(f"[DEBUG] FAILED: {cls.__name__} -> {type(e).__name__}: {e}")

    # Now use the normal flow
    print("\n[DEBUG] Running normal instantiate_apps flow...")
    contexts = app_mgr.create_contexts()
    services = []

    for app in app_mgr.instantiate_apps(**contexts):
        print(f"[DEBUG] Got from instantiate_apps: {app.__class__.__name__}")
        try:
            t = app.start()
            if t is not None:
                services.append(t)
        except RuntimeError:
            pass

    # Also check what's in app_mgr.applications
    print(f"\n[DEBUG] app_mgr.applications: {list(app_mgr.applications.keys())}")

    print(f"\n[INFO] Controller running. Waiting for switches on port 6633...")

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
