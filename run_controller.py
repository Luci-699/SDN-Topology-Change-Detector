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
    print("[DEBUG] Loading app module...")
    app_module_name = load_app_module(app_file)
    print(f"[DEBUG] Loaded module: {app_module_name}")

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
    print("[DEBUG] Loading apps into manager...")
    app_mgr.load_apps(app_lists)

    print(f"[DEBUG] Apps loaded. Creating contexts...")
    contexts = app_mgr.create_contexts()
    print(f"[DEBUG] Contexts: {list(contexts.keys())}")

    services = []
    print("[DEBUG] Instantiating apps...")

    for app in app_mgr.instantiate_apps(**contexts):
        print(f"[DEBUG] Instantiated: {app.__class__.__name__}")
        try:
            t = app.start()
            if t is not None:
                services.append(t)
                print(f"[DEBUG] Started: {app.__class__.__name__}")
        except RuntimeError as e:
            print(f"[DEBUG] RuntimeError on {app.__class__.__name__}: {e}")

    print(f"[DEBUG] Total services to join: {len(services)}")
    print("[INFO] Controller is running. Waiting for switch connections...")

    try:
        if services:
            hub.joinall(services)
        else:
            # Keep alive even if no greenlet services
            print("[DEBUG] No greenlet services, entering keep-alive loop...")
            while True:
                hub.sleep(1)
    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == '__main__':
    main()
