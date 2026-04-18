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

    # instantiate_apps creates, wires up observers, starts all apps,
    # and returns a list of service threads
    services = app_mgr.instantiate_apps(**contexts)

    print(f"[INFO] Apps: {list(app_mgr.applications.keys())}")
    print(f"[INFO] Services: {len(services)}")
    print("[INFO] Controller running on port 6633. Waiting for switches...")

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == '__main__':
    main()
