#!/usr/bin/env python3

#  * import due to just being things from Qt
from utils.qt_helper import *

from pyqtgraph.dockarea.DockArea import DockArea

from widgets.base_control_widgets import FrameDock
from widgets.base_control_widgets import getGlobalStyleSheet
from widgets.base_control_widgets import getLocalStyleSheet

import modules.module as module
from modules.module import Menu, __values__, SettingOption, update_values, Module

__modules__ = []

instances = []

# Constructs and starts an instance of the gui
def spawn_gui_proc(spawner=None):
    gui = MasterGui(parent=spawner)
    root = None

    instances.append(gui)
    gui.start(root=root)

# Starts an instance of the gui as a new process
def spawn_gui(spawner=None):
    spawn_gui_proc(spawner=spawner)

class GuiName:

    ranks = {
        "General" : None,
        "Colonel": "General",
        "Major": "Colonel",
        "Captain": "Major",
        "Lieutenant": "Captain",
        "Sergeant": "Lieutenant",
        "Corporal": "Sergeant",
        "Private": "Corporal",
    }

    rank_counts = {}

    def __init__(self, rank, parent, index):
        self.rank = rank
        self.parent = parent
        self.index = index

        self.name = f'{self.rank} Gui' if (parent is None or self.index == 1) else f'{self.rank} Gui {self.index}'

    def get_name(self):
        return self.name

    def get_next_subordinate(self):
        parent = self.rank
        rank = "Private"
        for new_rank, new_parent in GuiName.ranks.items():
            if parent == new_parent:
                rank = new_rank
        if not rank in GuiName.rank_counts:
            GuiName.rank_counts[rank] = 0
        index = GuiName.rank_counts[rank] + 1
        GuiName.rank_counts[rank] = index
        sub = GuiName(rank, parent, index)
        return sub

class MasterGui(QMainWindow):

    def __init__(self, name="General", parent=None, index=0):
        super().__init__()
        self.init_call = None
        self.dialog = None

        self._parent_window = parent
        if parent is not None:
            self._rank = parent._rank.get_next_subordinate()
        else:
            self._rank = GuiName(name, parent, index)
        self.base_name = self._rank.get_name()
        
        self.init_menus()

    def remove_module(self, module):
        if self._parent_window is not None:
            self._parent_window.remove_module(module)
        if module in self._modules:
            self._modules.remove(module)

    def init_menus(self):
        if self._parent_window is not None:
            self._modules = self._parent_window._modules
        else:
            self._modules = [x(self) for x in __modules__]

        # Three initial menus
        _file_menu = Menu()
        self.settings_menu = Menu()
        self.help_menu = Menu()

        dummy = Module(self)
        _file_menu.set_owner(dummy)
        self.settings_menu.set_owner(dummy)
        self.help_menu.set_owner(dummy)

        _file_menu._label = "File"
        self.help_menu._label = "Help"

        _file_menu._options["new_instance"] = self.new_gui
        _file_menu._labels["new_instance"] = "New Instance"
        _file_menu._helps["new_instance"] = 'Opens another copy of this window'

        _file_menu._opts_order.append("new_instance")

        all_menus = []
        
        self._settings = []
        
        for mod in self._modules:
            menus = mod.get_menus()
            for menu in menus:
                menu.set_owner(mod)
            all_menus.extend(menus)
            settings = mod.get_settings()
            for setting in settings:
                setting._owner = mod
            self._settings.extend(settings)

        self._menus = []

        self._menus.append(_file_menu)

        for menu in all_menus:
            shouldAdd = not self.help_menu.is_same(menu)
            
            if not shouldAdd:
                self.help_menu.merge_in(menu)
                continue

            for old in self._menus:
                same = old.is_same(menu)
                if same:
                    shouldAdd = False
                    old.merge_in(menu)
                    break

            if not shouldAdd:
                continue
            self._menus.append(menu)

        self._menus.append(self.help_menu)

        self.aboutMessage = 'LabGUI for interacting with lab equipment'

        _file_menu._options["exit"] = self.close

        _file_menu._opts_order.append("sep")
        _file_menu._opts_order.append("exit")

        _file_menu._labels["exit"] = "Exit"
        _file_menu._helps["exit"] = 'Exits this window (exits all if this was first window opened)'

    def new_gui(self):
        spawn_gui(spawner=self)

    # Starts the tk application, adds the file menus, etc
    def start(self, root=None):
        if root == None:
            self._rank
            self.first = True
            
        main_menu = self.menuBar()
        self.setStyleSheet(getGlobalStyleSheet())

        self.resize(400, 240)
        self.setWindowTitle(self.base_name)
        self.setWindowIcon(QIcon("icon.jpg"))

        # Here we actually make/add the menus
        for menu in self._menus:
            # Help menu is handled differently.
            if menu == self.help_menu:
                continue
            _new_menu = QMenu(menu._label, self)
            if len(menu._opts_order) > 0:
                main_menu.addMenu(_new_menu)
            # Add options in specified order
            for opt in menu._opts_order:
                if opt == 'sp' or opt == 'sep':
                    _new_menu.addSeparator()
                    continue
                label = menu._labels[opt]
                cmd = menu._options[opt]
                _action = QAction(label, self)
                _action.triggered.connect(self.wrap_cmd(cmd, opt, menu))
                _new_menu.addAction(_action)

        # Now add the help menus
        _new_menu = QMenu(self.help_menu._label, self)
        main_menu.addMenu(_new_menu)
        for menu in self._menus:
            if menu == self.help_menu:
                continue
            self.make_help_submenu(menu._opts_order, menu, _new_menu)
            
        # TODO about menu
        # _new_menu.add_command(label='About', command=self.about)

        for mod in self._modules:
            mod.on_start()

        self._main = DockArea()
        self._main.setStyleSheet(getLocalStyleSheet())
        self.setCentralWidget(self._main)
        self._layout = self._main.layout
        print('Showing!')

        self.show()

        if module.__open__ and self.init_call is not None:
            self.init_call()

    def wrap_cmd(self, cmd, opt, menu):
        def wrap():
            # Check if the other modules allow this option to be clicked
            owner = menu.get_owner(opt)
            allowed = True
            for module in self._modules:
                allowed = module.on_option_clicked(opt, owner) or allowed
            # If not, just say something happened
            if not allowed:
                print("Option Selection denied!")
            # Otherwise execute the command
            else:
                old = owner._root
                owner._root = self
                cmd()
                owner._root = old
        return wrap

    #Opens About Window with description of software
    def about(self):
        # TODO about menu
        # t = tk.Toplevel(self.root)
        # t.wm_title("About")
        # l = tk.Label(t, text = self.aboutMessage, font = font_14)
        # l.pack(side="top", fill="both", expand=True, padx=100, pady=100)
        # messageVar = tk.Message(t, text = self.copyrightMessage, fg='black', font = font_14, width = 600)
        # messageVar.place(relx = 0.5, rely = 1, anchor = tk.S)
        pass

    # Wrapper for making a submenu, so that the keys and the submenu are in new scope.
    def make_help_submenu(self, keys, menu, helpmenu):
        submenu = QMenu(menu._label, self)
        helpmenu.addMenu(submenu)
        for key in keys:
            if not key in menu._helps:
                continue
            if key == 'sp' or key == 'sep':
                submenu.addSeparator()
                continue
            label = menu._labels[key]
            msg = menu._helps[key]
            _action = QAction(label, self)
            _action.triggered.connect(self.make_help_settings(label, msg))
            submenu.addAction(_action)
        return submenu

    # Wrapper for the help_settings so that label and msg are in new scope.
    def make_help_settings(self, label, msg):
        return lambda: self.help_settings(label, msg)

    # Actually makes the setting option
    def help_settings(self, title, msg):
        if self.dialog is not None:
            self.dialog.close()
        dialog = FrameDock(title, closable=True)
        dialog.sigClosed.connect(self.dock_closed)
        self.dialog = dialog
        label = QLabel(msg)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.addWidget(label)
        self._main.addDock(dialog, 'top')

    def dock_closed(self, *_):
        self.dialog = None

    def closeEvent(self, _):
        self.__finished__ = True
        if self._parent_window is None:
            for mod in self._modules:
                mod.on_stop()
        else:
            for mod in self._modules:
                if mod._active == self:
                    mod.on_stop()
        instances.remove(self)
        if len(instances) == 0:
            global ended
            ended = True
            print('closed!')

    # Generates a window with options for editing floating point fields for thing
    # thing must have a _names_ attribute which is a map of <attr> to <name>, where
    # <name> is what the box will be labelled. These values should all be floats!
    def edit_options(self, dock, thing, name, callback, custom_owner=None):
        if self.dialog is not None:
            self.dialog.close()
        dialog = FrameDock(name, closable=True)
        dialog.sigClosed.connect(self.dock_closed)
        self.dialog = dialog

        widget = QWidget()
        dialog.addWidget(widget)

        layout = QVBoxLayout(widget)
        options = QVBoxLayout()
        buttons = QHBoxLayout()
        layout.addLayout(options)
        layout.addLayout(buttons)

        thing.on_window_created(dialog)

        variables = {}

        def update():
            # First check with the other modules if we are ok to change this setting
            owner = thing._owner
            if custom_owner is not None:
                owner = custom_owner
            allowed = True
            for module in self._modules:
                allowed = module.pre_setting_changed(name, owner) or allowed
            if not allowed:
                print("Setting change denied!")
                return

            # then actually apply the changes
            for key,value in variables.items():
                var = value.get_value()
                setattr(thing, key, var)

            if callback is not None:
                callback()
            
        for key,value in thing._names_.items():
            opt_obj = SettingOption(value, key, thing, options, update)
            variables[key] = opt_obj
            thing._entries_[key] = opt_obj

        for button in thing._buttons_:
            btn = QPushButton(button[0])
            btn.clicked.connect(button[1])
            buttons.addWidget(btn)
        
        update_button = QPushButton("Update")
        update_button.clicked.connect(update)
        buttons.addWidget(update_button)

        cancel_button = QPushButton("Close")
        cancel_button.clicked.connect(lambda: [dialog.close()])
        buttons.addWidget(cancel_button)

        self._main.addDock(dialog, 'top', dock)

def start():
    import sys
    app =  QApplication(sys.argv)
    update_values()
    if len(instances) == 0:
        spawn_gui_proc()
    sys.exit(app.exec())

if __name__ == '__main__':

    import modules.control_module as control_module
    __modules__.append(control_module.MainModule)
    
    import modules.live_plot as live_plot
    __modules__.append(live_plot.PlotModule)

    start()
