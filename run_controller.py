#!/usr/bin/env python3
"""
Launcher script for the SDN Topology Detector controller.
Replaces 'ryu-manager' / 'osken-manager' which may not be available
in newer os-ken versions.

Usage:
    python3 run_controller.py controller/topology_detector.py --observe-links --verbose
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try os_ken.cmd.manager first (some versions have it)
try:
    from os_ken.cmd.manager import main
    main()
except ImportError:
    # Fallback: manually bootstrap the app manager
    from os_ken import cfg
    from os_ken.base.app_manager import AppManager
    from os_ken.topology import switches  # needed for --observe-links

    CONF = cfg.CONF
    CONF(sys.argv[1:])

    app_lists = CONF.app_lists + CONF.app
    # Always include topology switches module for --observe-links
    if '--observe-links' in sys.argv:
        topo_module = 'os_ken.topology.switches'
        if topo_module not in app_lists:
            app_lists.append(topo_module)

    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)
    contexts = app_mgr.create_contexts()
    services = []

    for app in app_mgr.instantiate_apps(**contexts):
        t = app.start()
        if t is not None:
            services.append(t)

    try:
        from os_ken.lib import hub
        hub.joinall(services)
    except KeyboardInterrupt:
        print("\nController stopped.")
