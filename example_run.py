#!/usr/bin/env python3

### If running a server manually, uncomment below and replace this ADDR accordingly
# import utils.data_client as data_client
# data_client.ADDR = ("host", 20002) 

import main_gui
from utils.qt_helper import QApplication

def make_modules(main):
    """Here we add a few of our own modules.

    We add 2 test devices, which report random values, and then a SaveModule for saving settings.

    Args:
        main (MainModule): module having sub modules added
    """
    from widgets.test_device import TestDevice

    module = TestDevice(main, id=27)
    main.plot_widget.addDock(module.dock)
    main._modules.append(module)
    _module = module

    module = TestDevice(main, id=25)
    # This test device we manually place to the left of the previous
    main.plot_widget.addDock(module.dock, 'left', _module.dock)
    main._modules.append(module)
    _module = module

    from widgets.base_control_widgets import SaveModule

    module = SaveModule(main)
    # By not specifying location, it goes below the rest.
    main.plot_widget.addDock(module.dock)
    main._modules.append(module)
    _module = module

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)

    # Add some modules to run
    import modules.control_module as control_module
    control_module.make_modules = make_modules
    main_gui.__modules__.append(control_module.MainModule)
    
    import modules.live_plot as live_plot
    main_gui.__modules__.append(live_plot.PlotModule)

    import modules.module as module
    # This makes the first supported module open automatically
    module.__open__ = True

    # Start the gui
    main_gui.start()
    sys.exit(app.exec())
