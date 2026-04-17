#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
Directly bootstraps the os_ken AppManager without needing osken-manager CLI.

Usage:
    python3 run_controller.py
"""
import sys
import os
import importlib.util

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_app_module(app_path):
    """Load a Python module from a file path."""
    module_name = os.path.splitext(os.path.basename(app_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module_name


def main():
    from os_ken.base.app_manager import AppManager
    from os_ken.lib import hub

    # The app to load
    app_file = os.path.join(os.path.dirname(__file__),
                            'controller', 'topology_detector.py')

    # Load the controller app module
    app_module_name = load_app_module(app_file)

    # Build list of apps to load
    app_lists = [app_module_name]

    # Add the OpenFlow handler (listens on port 6633 for switch connections)
    app_lists.append('os_ken.controller.ofp_handler')

    # Add topology discovery module (equivalent to --observe-links)
    app_lists.append('os_ken.topology.switches')

    print("=" * 60)
    print("  SDN Topology Detector - Controller Launcher")
    print(f"  Loading apps: {app_lists}")
    print("=" * 60)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)
    contexts = app_mgr.create_contexts()
    services = []

    for app in app_mgr.instantiate_apps(**contexts):
        try:
            t = app.start()
            if t is not None:
                services.append(t)
        except RuntimeError:
            # Thread already started during __init__, that's fine
            pass

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == '__main__':
    main()
