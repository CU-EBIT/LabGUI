#!/usr/bin/env python3

### If running a server manually, uncomment below and replace this ADDR accordingly
# import utils.data_client as data_client
# data_client.ADDR = ("host", 20002) 

def make_modules(main):
    """Here we add a few of our own modules.

    We add 2 test devices, which report random values, and then a SaveModule for saving settings.

    Args:
        main (MainModule): module having sub modules added
    """
    from lab_gui.examples.widgets.test_device import TestDevice

    module = TestDevice(main, id=27)
    main.plot_widget.addDock(module.dock)
    main._modules.append(module)
    _module = module

    module = TestDevice(main, id=25)
    # This test device we manually place to the left of the previous
    main.plot_widget.addDock(module.dock, 'left', _module.dock)
    main._modules.append(module)
    _module = module

    from lab_gui.widgets.base_control_widgets import SaveModule

    module = SaveModule(main)
    # By not specifying location, it goes below the rest.
    main.plot_widget.addDock(module.dock)
    main._modules.append(module)
    _module = module

if __name__ == '__main__':
    from lab_gui import main_gui

    # Add some modules to run

    from lab_gui.examples.modules import test_module
    # Add our ExampleModule first, this makes it open by default
    main_gui.__modules__.append(test_module.ExampleModule)
    
    # Add our custom module that allows opening many times
    main_gui.__modules__.append(test_module.ExampleMultiple)

    from lab_gui.modules import control_module
    # Next do a MainModule from control_module. This uses the make_modules
    # which makes for a somewhat simplified way to add simple widgets
    control_module.make_modules = make_modules
    main_gui.__modules__.append(control_module.MainModule)
    
    from lab_gui.modules import live_plot
    # Finally add a live_plot, as an example of a different type of
    main_gui.__modules__.append(live_plot.PlotModule)

    # Start the gui
    main_gui.start()
