#!/usr/bin/env python3

import utils.data_client as data_client
data_client.ADDR = ("localhost", 20002)

import main_gui
from PyQt6.QtWidgets import QApplication

def make_modules(main):
        from widgets.test_device import TestDevice

        module = TestDevice(main, id=27)
        main.plot_widget.addDock(module.dock)
        main._modules.append(module)
        _module = module

        module = TestDevice(main, id=25)
        main.plot_widget.addDock(module.dock, position='left')
        main._modules.append(module)
        _module = module

        from widgets.base_control_widgets import SaveModule

        module = SaveModule(main)
        main.plot_widget.addDock(module.dock)
        main._modules.append(module)
        _module = module

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)

    import modules.control_module as control_module
    control_module.make_modules = make_modules
    main_gui.__modules__.append(control_module.MainModule)
    
    import modules.live_plot as live_plot
    main_gui.__modules__.append(live_plot.PlotModule)

    import modules.module as module
    module.__open__ = True

    main_gui.start()
    sys.exit(app.exec())
