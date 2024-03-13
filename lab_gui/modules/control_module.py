from pyqtgraph.dockarea.DockArea import DockArea

from .module import Menu, ClientWrapper, FigureModule

#  * import due to just being things from Qt
from ..utils.qt_helper import *

from ..widgets.base_control_widgets import getLocalStyleSheet

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

        self.module_source = make_modules

        self.init_menu_naming(menu_name="Modules", key="open_control_module", name="Control Module", help="Opens Control Module")

    def on_stop(self):
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

        self.module_source(self)

        for mod in self._modules:
            mod.on_init()
