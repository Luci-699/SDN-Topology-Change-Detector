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

# Set sys.argv for oslo.config parsing
sys.argv = [sys.argv[0], '--observe-links']


def main():
    # Register the 'app' positional CLI argument that ryu-manager used
    from oslo_config import cfg as oslo_cfg
    from os_ken import cfg

    cfg.CONF.register_cli_opts([
        oslo_cfg.MultiOpt('app', positional=True, default=[],
                          help='application module name to run'),
        oslo_cfg.ListOpt('app-lists', default=[],
                         help='application module name to run'),
    ])

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

    # Parse config with --observe-links
    cfg.CONF(args=['--observe-links'], project='os_ken', version='1.0')

    contexts = app_mgr.create_contexts()
    services = []

    for app in app_mgr.instantiate_apps(**contexts):
        t = app.start()
        if t is not None:
            services.append(t)

    # Ensure all registered apps are started
    for app_name, app in app_mgr.applications.items():
        try:
            t = app.start()
            if t is not None:
                services.append(t)
        except RuntimeError:
            pass  # Already started

    print(f"[INFO] Apps: {list(app_mgr.applications.keys())}")
    print(f"[INFO] Services: {len(services)}")
    print("[INFO] Controller running on port 6633. Waiting for switches...")

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == '__main__':
    main()
