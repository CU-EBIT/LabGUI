from .module import Menu, ClientWrapper, FigureModule

from PyQt5.QtWidgets import QHBoxLayout
from pyqtgraph.dockarea.DockArea import DockArea
from widgets.base_control_widgets import getLocalStyleSheet

def make_modules(main):
        '''
        Here is an example setup of a controller, Replace this with your own setup for the controller 
        via control_module.make_modules = <your function here>
        '''
        from widgets.ke617_widget import KE617

        module = KE617(main, addr=27)
        main.plot_widget.addDock(module.dock)
        main._modules.append(module)
        _module = module

        module = KE617(main, addr=25)
        main.plot_widget.addDock(module.dock, position='left')
        main._modules.append(module)
        _module = module

        from widgets.glassman_controller import DualGlassman

        module = DualGlassman(main)
        main.plot_widget.addDock(module.dock)
        main._modules.append(module)
        _module = module

        from widgets.base_control_widgets import SaveModule

        module = SaveModule(main)
        main.plot_widget.addDock(module.dock, 'right', _module.dock)
        main._modules.append(module)
        _module = module

class MainModule(FigureModule):
    def __init__(self, root):
        super().__init__(root)

        if root.init_call is None:
            root.init_call = self.start_plotting

        self._layouts = []
        self._modules = []

        self.data_client = ClientWrapper()
        self.update_rate = 500
        self.routine = None

        self._running_ = False

    def get_menus(self):
        
        _menu = Menu()
        # Add some options, the value is the function to run on click
        _menu._options["open_module"] = self.start_plotting
        _menu._opts_order.append("open_module")
        # Adds some help menu text for these as well
        _menu._helps["open_module"] = 'Opens Control Module'
        # Adds labels for the non-separator values
        _menu._labels["open_module"] = "Control Module"
        self.set_name("Control Module")
        # Specify a label for the menu
        _menu._label = "Modules"

        # Returns an array of menus (only 1 in this case)
        return [_menu]

    def on_stop(self):
        if self._stopped:
            return
        for mod in self._modules:
            mod.close()
        self._modules.clear()
        self.initialised = False
        return super().on_stop()    

    def clear_fig(self):
        for layout in self._layouts:
            self.delete_layout(layout)
        self._layouts.clear()
        return super().clear_fig()

    def update_values(self, _):
        for module in self._modules:
            module.on_update()

    def make_plot(self):
        self._running_ = True
        self.anim = self.update_values
        self.plot_widget = DockArea()
        self.plot_widget.setStyleSheet(getLocalStyleSheet())

    def post_figure(self):
        self._modules.clear()
        # Here is where you should add things that you want to have on after the main plot has been added to the canvas
        self.core_layout = QHBoxLayout()
        self._layouts.append(self.core_layout)

        make_modules(self)

        for mod in self._modules:
            mod.on_init()
