#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
"""
import sys
import os
import importlib.util
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_app_module(app_path):
    module_name = os.path.splitext(os.path.basename(app_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module_name


def main():
    from os_ken.base.app_manager import AppManager, OSKenApp
    from os_ken.lib import hub

    # Load our app module
    app_file = os.path.join(os.path.dirname(__file__),
                            'controller', 'topology_detector.py')
    app_module_name = load_app_module(app_file)

    # Debug: check what classes are in our module
    mod = sys.modules[app_module_name]
    print(f"[DEBUG] Module name: {mod.__name__}")
    for name, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, OSKenApp):
            print(f"[DEBUG] Found OSKenApp subclass: {name}, __module__={obj.__module__}")

    app_lists = [app_module_name]
    app_lists.append('os_ken.controller.ofp_handler')
    app_lists.append('os_ken.topology.switches')

    print("=" * 60)
    print("  SDN Topology Detector - Controller Launcher")
    print(f"  Loading apps: {app_lists}")
    print("=" * 60)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)

    # Debug: what did load_apps find?
    print(f"[DEBUG] Registered app classes: {list(app_mgr.applications_cls.keys())}")
    for name, cls in app_mgr.applications_cls.items():
        print(f"[DEBUG]   {name} -> {cls}")

    # Parse config AFTER loading
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

    print(f"[INFO] Controller running with {len(services)} services.")

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
