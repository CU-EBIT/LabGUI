# Here we have an example of a custom module. It will act similarly to the ControlModule

from ...modules.control_module import MainModule

class ExampleModule(MainModule):

    def __init__(self, root):
        super().__init__(root)

        # Adds the menu dropdown to select to open a copy of this module
        self.init_menu_naming(menu_name="Modules", key="open_example_module", name="Example Module", help="Opens Example Module")

        # Override the default module source to be the one we implement below
        self.module_source = self.make_modules

    def make_modules(self, *_):
        """Here we add a few of our own modules.

        We add 2 test devices, which report random values, and then a SaveModule for saving settings.

        Args:
            main (MainModule): module having sub modules added
        """
        from ..widgets.test_device import TestDevice
        from lab_gui.utils.qt_helper import QtGui

        module = TestDevice(self, id=27)
        self.plot_widget.addDock(module.dock)
        self._modules.append(module)
        _module = module

        font = QtGui.QFont()
        font.setPixelSize(16)
        module.plot_widget.font_size(axis='x,y', tick_size=18, title_size=20)
        module.plot_tooltip.setFont(font)

        module = TestDevice(self, id=25)
        # This test device we manually place to the left of the previous
        self.plot_widget.addDock(module.dock, 'left', _module.dock)
        self._modules.append(module)
        _module = module

        font = QtGui.QFont()
        font.setPixelSize(10)
        module.plot_widget.font_size(axis='x,y', tick_size=8, title_size=10, line_width=5.0)
        module.plot_tooltip.setFont(font)

        from lab_gui.modules.live_plot import PlotModule
        # Here we have an example of adding a module instead of a widget
        # The module's constructor took the same as ours, ie the _root
        module = PlotModule.make_dummy_plotter(self._root)
        # The module then has a function to start plotting it, this is
        # what is in the menu action for it
        module.menu_action()
        # Then add it to the dock. Note that we do not add it to our _modules
        self.plot_widget.addDock(module._dock, 'top')

        from lab_gui.widgets.base_control_widgets import SaveModule

        module = SaveModule()
        # By not specifying location, it goes below the rest.
        self.plot_widget.addDock(module.dock)
        self._modules.append(module)
        _module = module

        from ..widgets.test_table import TableDisplay, ColourTableDisplay

        module = TableDisplay(self)
        self.plot_widget.addDock(module.dock, 'right', _module.dock)
        self._modules.append(module)
        _module = module

        module = ColourTableDisplay(self)
        self.plot_widget.addDock(module.dock, 'right', _module.dock)
        self._modules.append(module)
        _module = module

class ExampleMultiple(ExampleModule):
    def __init__(self, root):
        super().__init__(root)

        # Adds the menu dropdown to select to open a copy of this module
        self.init_menu_naming(menu_name="Modules", key="open_example_multi_module", name="Example Multiple Module", help="Opens Example Multiple Module")

        self.menu_action = self.new_module

    def make_dummy(root):
        plotter = ExampleMultiple(root)
        plotter.dummy = True
        root._modules.append(plotter)
        plotter.get_menus() # Init menus
        plotter.on_start()
        return plotter

    def new_module(self):
        plotter = ExampleMultiple.make_dummy(self._root)
        plotter.start_plotting()