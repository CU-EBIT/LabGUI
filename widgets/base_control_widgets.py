import time
import os
import json

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QWidget, QFrame, QLabel, QLineEdit,\
      QPushButton, QHBoxLayout, QTableWidget, QFileDialog, QVBoxLayout, QCheckBox

from pyqtgraph.dockarea.DockArea import Dock
from pyqtgraph.dockarea.Dock import DockLabel

_red_ = '#B94700'
_green_ = '#546223'
_blue_ = '#005EB8'
_orange_ = '#F56600'
_light_grey_ = '#C8C9C7'
_grey_ = '#888B8D'
_dark_grey_ = '#333333'
_purple_ = '#522D80'
_dark_purple_ = '#2E1A47'
_dark_blue_ = '#00205B'
_black_ = '#000000'
_tan_ = '#EFDBB2'

def getLocalStyleSheet():
    """Generates our default style local sheet

    Returns:
        str: stylesheet containing background-color and color
    """    
    return f"""
background-color: {_light_grey_};
color: {_black_};
"""

def getGlobalStyleSheet():
    """Generates our default style global sheet

    Returns:
        str: stylesheet containing background-color and color for a variety of QWidgets
    """    
    return f"""
QWidget
{{
    background-color: {_light_grey_};
    color: {_black_};
}}
QMenuBar::item::selected
{{
    background-color: {_grey_};
    color: {_black_};
}}
QMenu::item::selected
{{
    background-color: {_grey_};
    color: {_black_};
}}
QLineEdit
{{
    background-color: {_tan_};
    color: {_black_};
}}
QPushButton
{{
    background-color: {_grey_};
    color: {_dark_grey_};
}}
QTableWidget::item::selected
{{
    background-color: {_grey_};
    color: {_orange_};
}}
QHeaderView::section 
{{
    background-color: {_light_grey_};
    color: {_black_};
}}
"""

def widget_dpi(widget):
    """Retrieves the logicalDotsPerInch for the screen of the widget

    Args:
        widget (QWidget): the widget on screen

    Returns:
        float: logicalDotsPerInch of the screen
    """
    return widget.screen().logicalDotsPerInch()

def scale(dpi):
    """Figures out the expected object scale assuming a default dpi of 96

    Args:
        dpi (float): input dpi, from widget_dpi

    Returns:
        float: dpi scaled by 1/96
    """
    return dpi / 96

class FrameDockLabel(DockLabel):
    '''
    Label for a frame dock, we modify it to add the help and menu buttons if needed. Also adds support for our colours.
    '''
    def __init__(self, text, closable=False, fontSize="12px", menu_fn=None, help_fn=None):
        """_summary_
        Args:
            text (str): the text for the label
            closable (bool, optional): whether the dock as a close button. Defaults to False.
            fontSize (str, optional): font size for the label. Defaults to "12px".
            menu_fn (_type_, optional): function to call when menu button is pressed. Defaults to None.
            help_fn (_type_, optional): function to call when help button is pressed. Defaults to None.
        """        
        super().__init__(text, closable, fontSize)
        self.menuButton = None
        self.helpButton = None
        if menu_fn is not None:
            self.add_menu_button(menu_fn)
        if help_fn is not None:
            self.add_help_button(help_fn)

    def updateStyle(self):
        r = '0px'
        # Dim is when behind in another tab
        if self.dim:
            fg = _light_grey_
            bg = _purple_
            border = _dark_blue_
        else:
            fg = _orange_
            bg = _dark_purple_
            border = _dark_blue_

        if self.orientation == 'vertical':
            self.vStyle = """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: 0px;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: %s;
                border-width: 0px;
                border-right: 2px solid %s;
                padding-top: 3px;
                padding-bottom: 3px;
                font-size: %s;
            }""" % (bg, fg, r, r, border, self.fontSize)
            self.setStyleSheet(self.vStyle)
        else:
            self.hStyle = """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: %s;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-width: 0px;
                border-bottom: 2px solid %s;
                padding-left: 3px;
                padding-right: 3px;
                font-size: %s;
            }""" % (bg, fg, r, r, border, self.fontSize)
            self.setStyleSheet(self.hStyle)

    def add_menu_button(self, function):
        self.menuButton = QtWidgets.QToolButton(self)
        self.menuButton.clicked.connect(function)
        icon = QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView
        self.menuButton.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.menuButton.setToolTip("Options")

    def add_help_button(self, function):
        self.helpButton = QtWidgets.QToolButton(self)
        self.helpButton.clicked.connect(function)
        icon = QtWidgets.QStyle.StandardPixmap.SP_TitleBarContextHelpButton
        self.helpButton.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.helpButton.setToolTip("Help")

    def resizeEvent(self, ev):
        menu_shift = 16
        help_shift = 32
        if not self.closeButton:
            menu_shift -= 16
            help_shift -= 16
        if not self.menuButton:
            help_shift -= 16
        if self.menuButton:
            if self.orientation == 'vertical':
                size = ev.size().width()
                pos = QtCore.QPoint(0, menu_shift)
            else:
                size = ev.size().height()
                pos = QtCore.QPoint(ev.size().width() - size - menu_shift, 0)
            self.menuButton.setFixedSize(QtCore.QSize(size, size))
            self.menuButton.move(pos)
        if self.helpButton:
            if self.orientation == 'vertical':
                size = ev.size().width()
                pos = QtCore.QPoint(0, help_shift)
            else:
                size = ev.size().height()
                pos = QtCore.QPoint(ev.size().width() - size - help_shift, 0)
            self.helpButton.setFixedSize(QtCore.QSize(size, size))
            self.helpButton.move(pos)
        return super().resizeEvent(ev)

class FrameDock(Dock):
    '''
    Our FrameDock, adjusts the Dock to include our default stylesheet (ie colours and formats)
    '''
    def __init__(self, name="   ", area=None, size=(1,1), widget=None, hideTitle=False, autoOrientation=True, label=None, **kargs):
        if label is None:
            label = FrameDockLabel(name, **kargs) 
        super().__init__(name, area, size, widget, hideTitle, autoOrientation, label, **kargs)
        self.setStyleSheet(getGlobalStyleSheet())

    def float(self):
        super().float()
        self.setStyleSheet(getGlobalStyleSheet())

    def containerChanged(self, c):
        super().containerChanged(c)
        self.setStyleSheet(getGlobalStyleSheet())

class SubControlModule:
    '''
    A Basic module for a control. This consists of a QFrame inside a FrameDock. 
    
    It provides methods for passing re-size commmands to modules, which are any object that provides an update_values function
    '''
    def __init__(self, client=None, fixed_size=True, menu_fn=None, help_fn=None, make_dock=True):
        self.frame = QFrame()
        self.frame.setLineWidth(2)
        self.frame.setFrameShape(QFrame.Shape.WinPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.frame.setContentsMargins(2,2,2,2)
        self.client = client

        self.tick = 0
        self.updated = -10
        self.fixed_size = fixed_size

        self._modules = []
        self.oldDPI = 0
        
        if make_dock:
            self.dock = FrameDock(widget=self.frame,menu_fn=menu_fn,help_fn=help_fn)

    def close(self):
        """Called when module is removed, ensure to close any opened resources, etc here.
        """        
        return

    def set_name(self, name):
        self.dock.label.setText(name)
        return self

    def get_dpi(self):
        return widget_dpi(self.frame)

    def resize(self, w, h):
        w *= scale(self.get_dpi())
        self.frame.setFixedWidth(int(w))
        h *= scale(self.get_dpi())
        self.frame.setFixedHeight(int(h))
        if self.fixed_size:
            self.dock.topLayout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)
            self.dock.layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)
    
    def on_init(self):
        self.update_values()

    def on_update(self):
        """Called during the gui update ticks, this is intended for use with updating values in gui boxes.
        """
        self.tick += 1
        if self.tick%2 != 0:
            return
        if(self.tick - self.updated > 5):
            self.update_values()

    def add_module(self, module):
        self._layout.addLayout(module._layout)
        self._modules.append(module)

    def frame_size(self):
        """Called when DPI changes, if you have a fixed size, re-set it here!
        """        
        pass

    def update_values(self):
        dpi = self.get_dpi()
        if self.oldDPI != dpi:
            self.frame_size()
            self.oldDPI = dpi
        for module in self._modules:
            module.update_values()

class ControlLine:
    '''
    This wraps a LineEdit to provide changes when the up/down/enter buttons are pressed.

    Up and Down arrows are assumed to be changing the value of a number, this ensures they
    are within the range of [min, max], and will adjust the contents of the box based on set_fmt

    When the number is changed (or enter is pressed), on_update is called
    '''
    def __init__(self, on_update, box, set_fmt="{:.2f}", min=-1e30, max=1e30):
        self.on_update = on_update
        self.set_fmt = set_fmt
        self.box = box
        self.ufmt = float
        self.min = min
        self.max = max
        self.box.upPressed.connect(self.up_arrow)
        self.box.downPressed.connect(self.down_arrow)
        self.box.enterPressed.connect(self.enter_pressed)
        self.down_to_0 = True

    def update_number(self, text, pos, dir):
        char = text[pos-1]
        exp = 'e' in text

        if(char != ".") or dir == 0:
            try:
                var = self.ufmt(text)
                
                if dir != 0:
                    # find index of a . if present
                    index = len(text)
                    if('.' in text):
                        index = text.index('.')
                    oom = index - pos
                    if(oom < 0):
                        oom += 1
                    if exp:
                        e_ind = text.index('e')
                        oom += int(text[e_ind + 1:])
                    dV = dir * 10**oom
                    if not self.down_to_0 and abs(var+dV) < var / 10:
                        dV /= 10
                    var += dV
                
                var = max(self.min, var)
                var = min(self.max, var)
                var = self.ufmt(var)

                self.box.setText(self.set_fmt.format(var))
                self.on_update()
                pos += len(self.box.text()) - len(text)
                self.box.setCursorPosition(pos)
            except Exception as err:
                print(f"error {err}")
                pass

    def up_arrow(self):
        pos = self.box.cursorPosition()
        if pos <= 0:
            return
        text = self.box.text()
        self.update_number(text, pos, 1)

    def down_arrow(self):
        pos = self.box.cursorPosition()
        if pos <= 0:
            return
        text = self.box.text()
        self.update_number(text, pos, -1)

    def enter_pressed(self):
        pos = self.box.cursorPosition()
        text = self.box.text()
        self.update_number(text, pos, 0)

SAVER_NAMES = {}

class FolderSelector:
    def __init__(self, default) -> None:
        self.box = QLineEdit(default)
        self.button = QPushButton("Find")

        self.button.clicked.connect(self.button_pressed)

    def button_pressed(self):
        orig = self.box.text()
        fname = QFileDialog.getExistingDirectory(self.button, "Select Directory", orig)
        self.box.setText(fname)

    def makeLayout(self):
        self._layout = QHBoxLayout()
        self._layout.addWidget(self.box)
        self._layout.addWidget(self.button)
        return self._layout

class SaveModule(SubControlModule):
    def __init__(self, client=None, fixed_size=True, menu_fn=None, help_fn=None, make_dock=True):
        super().__init__(client, fixed_size, menu_fn, help_fn, make_dock)
        
        self._layout = QHBoxLayout()

        self.save_selector = FolderSelector("./settings/backup")
        self._layout_save = QVBoxLayout()
        self._layout_save.setSpacing(0)

        self.save_dir_box = self.save_selector.box
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_all)

        self._layout_save.addWidget(QLabel("Save Directory"))
        self._layout_save.addLayout(self.save_selector.makeLayout())
        self._layout_save.addWidget(self.save_button)
        self._layout_save.addStretch(0)

        self._layout_log = QVBoxLayout()
        self._layout_log.setSpacing(0)

        self.log_selector = FolderSelector("./logs")
        self.log_update_button = QPushButton("Update Log Dir")
        self.save_button.clicked.connect(self.update_logs_dir)

        self._layout_log.addWidget(QLabel("Logs Root Directory"))
        self._layout_log.addLayout(self.log_selector.makeLayout())
        self._layout_log.addWidget(self.log_update_button)
        self._layout_log.addStretch(0)

        self._layout.addLayout(self._layout_save)
        self._layout.addLayout(self._layout_log)
        self._layout.addStretch(0)

        self.frame.setLayout(self._layout)

    def update_logs_dir(self):
        log_dir = self.log_selector.box.text()
        for _, saver in SAVER_NAMES.items():
            saver.value_map["log_directory"] = log_dir
            saver.save()

    def save_all(self):
        save_dir = f"{self.save_dir_box.text()}"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        for _, saver in SAVER_NAMES.items():
            _oldfile = saver.filename
            filename = f"{save_dir}/{saver.name}.json"
            saver.filename = filename
            saver.save()
            saver.filename = _oldfile

class StateSaver:
    def __init__(self, name, value_map, save_dir="./settings", log_dir="./logs") -> None:

        if name in SAVER_NAMES:
            n = 1
            name_1 = f"{name}_{n}"

            if name_1 in SAVER_NAMES:
                for _ in range(256):
                    n += 1
                    name_1 = f"{name}_{n}"
                    if not name_1 in SAVER_NAMES:
                        break
            print(f"Warning, tried creating a new saver for {name}, instead using {name_1}")
            name = name_1

        SAVER_NAMES[name] = self
        self.name = name
        self.dir = save_dir
        self.filename = f"{self.dir}/{self.name}.json"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        if not "log_directory" in value_map:
            value_map["log_directory"] = log_dir

        # This is a map of key -> QLineEdit
        self.value_map = value_map
        self.rev_map = {}
        self.rev_map = {v: k for k, v in value_map.items()}

        self.init_or_load()

    def init_or_load(self):
        self.data = None
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as file:
                    self.data = json.load(file)
            except Exception as err:
                print(err)
                print(f"while loading json file {self.filename}")
                self.data = None

        if self.data is None:
        # In this case, we did not load anything, so we init from value map
            self.data = {}
            for k, v in self.value_map.items():
                if isinstance(v, QLineEdit):
                    self.data[k] = v.text()
                elif isinstance(v, QCheckBox):
                    self.data[k] = v.isChecked()
                elif isinstance(v, str):
                    self.data[k] = v
                elif isinstance(v, ControlButton):
                    self.data[k] = v.value
                elif hasattr(v, "_saver_save_"):
                    self.data[k] = v._saver_save_()
            self.save()
        else:
        # In this case, we loaded values, so we update the valuemap entry accordingly
            for k, v in self.data.items():
                if k in self.value_map:
                    box = self.value_map[k]
                    if isinstance(box, QLineEdit):
                        box.setText(v)
                    elif isinstance(box, QCheckBox):
                        box.setChecked(v)
                    elif isinstance(box, str):
                        self.value_map[k] = v
                    elif isinstance(box, ControlButton):
                        box.value = v
                    elif hasattr(box, "_saver_load_"):
                        box._saver_load_(v)

    def save(self):
        with open(self.filename, 'w') as file:
            json.dump(self.data, file, indent = 2)

    def on_changed(self, value):
        key = self.rev_map[value]
        if isinstance(value, QLineEdit):
            self.data[key] = value.text()
        elif isinstance(value, QCheckBox):
            self.data[key] = value.isChecked()
        elif isinstance(value, str):
            self.data[key] = value
            self.value_map[key] = value
        elif isinstance(value, ControlButton):
            self.data[key] = value.value
        elif hasattr(value, "_saver_save_"):
            self.data[key] = value._saver_save_()
        self.save()

###
### Here we have some general purpose QWidgets
###

class LineEdit(QLineEdit):
    '''Modified version of QLineEdit to include signals for up/down arrow and enter'''
    upPressed = QtCore.pyqtSignal()
    downPressed = QtCore.pyqtSignal()
    enterPressed = QtCore.pyqtSignal()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == QtCore.Qt.Key_Up:
            self.upPressed.emit()
        if event.key() == QtCore.Qt.Key_Down:
            self.downPressed.emit()
        if event.key() == QtCore.Qt.Key_Enter:
            self.enterPressed.emit()

class ControlButton(QPushButton):
    '''
    This is a QPushButton which syncs status with the data_client, based on the given key. If not dataclient or module, it acts like a checkbox
    '''
    def __init__(self, module=None, key=None, text=["On", "Off"], predicate=lambda x: x, values=[True, False], colours=[_green_, _red_], display_only=False, default_value=None, toggle=None,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        if module is not None:
            self.client = module.client
        self.key = key
        if self.key is None:
            self.client = None
        if isinstance(text, str):
            text = [text,text]
        self.text_opts = text
        self.predicate = predicate
        self.values = values
        self.colours = colours
        self.disabled = False
        self.value = default_value
        if toggle is not None:
            old_tgl = self.toggle
            def wrapped():
                old_tgl()
                toggle()
            self.toggle = wrapped
        if not display_only:
            self.clicked.connect(self.toggle)
        self.isChecked()

    def isChecked(self):        
        if self.value is not None:
            self.setText(self.text_opts[0] if self.predicate(self.value) else self.text_opts[1])
            self.setStyleSheet(f"background-color : {self.colours[0] if self.predicate(self.value) else self.colours[1]}")
        return self.value

    def update_values(self):
        if self.disabled:
            return
        if self.client is None:
            var = None
        else:
            var = self.client.get_value(self.key)
        if var is not None:
            self.value = var[1]
        self.isChecked()

    def get_dpi(self):
        return widget_dpi(self)

    def set_button_sizes(self, w, h):
        dpi_scale = scale(self.get_dpi())
        h = int(h * dpi_scale)
        self.setFixedHeight(int(h))
        w = int(w * dpi_scale)
        self.setFixedWidth(int(w))

    def toggle(self):
        if self.disabled:
            return
        new_value = self.values[1] if self.predicate(self.value) else self.values[0]
        if self.client is not None:
            self.client.set_value(self.key, new_value)
        self.value = new_value
        self.update_values()

###
### Widgets below here are all set to use the data_client and BaseDataClient for value set/lookup
### Do not use the below widgets unless you are using that server system for value management!
###

class SingleDisplayWidget(QLabel):
    '''
    This is a QLabel which updates its value based on looking up the key on the data_client. This only works if the module has a valid data_client!
    '''
    def __init__(self, module, key, fmt, scale = lambda x: x, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.scale = scale
        self.client = module.client
        self.key = key
        self.fmt = fmt

        self.update_values()
        # Label for values       
        self.update_labels()

    def get_dpi(self):
        return widget_dpi(self)
        
    def set_label_sizes(self, size):
        size *= scale(self.get_dpi())
        fm = self.fontMetrics()
        w = size*fm.width("0")
        self.setMaximumWidth(int(w))
        self.setMinimumWidth(int(w))

    def update_values(self):
        var = self.client.get_value(self.key)
        print(self.key, var)
        if var is not None:
            self.value = var[1]
        self.update_labels()

    def update_labels(self):
        self.setText(self.fmt.format(self.scale(self.value)))

class SingleInputWidget(LineEdit):
    '''
    This is a LineEdit which updates the key to the data_client when changed.
    
    it also syncs it's value based on looking up the key on the data_client. 
    
    This only works if the module has a valid data_client!
    '''
    def __init__(self, module, key, fmt, typing=float, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = module.client
        self.key = key
        self.fmt = fmt
        self.init_done = time.time()

        self.typing = typing

        self.update_values()
        # Entry for value      

        self.ctrl = ControlLine(self.update_value, self, self.fmt)
        self.returnPressed.connect(self.update_value)
        self.ctrl.ufmt = typing

        self.init_done = True

    def get_dpi(self):
        return widget_dpi(self)
        
    def set_label_sizes(self, size):
        size *= scale(self.get_dpi())
        fm = self.fontMetrics()
        m = self.textMargins()
        c = self.contentsMargins()
        w = size*fm.width('0')+m.left()+m.right()+c.left()+c.right()
        self.setMaximumWidth(int(w))
        self.setMinimumWidth(int(w))

    def update_values(self):
        if self.init_done > time.time():
            return
        var = self.client.get_value(self.key)
        if var is not None:
            self.value = var[1]
            self.update_labels()
            self.init_done = time.time() + 1

    def update_labels(self):
        pos = self.cursorPosition()
        self.setText(self.fmt.format(self.typing(self.value)))
        self.setCursorPosition(pos)
        
    def update_value(self):
        try:
            value = self.typing(self.text())
            self.client.set_value(self.key, value)
        except Exception as err:
            print(f"format error for setting {self.key} {err}")

class ValuesAndPower(QWidget):
    def __init__(self, module, power_key, set_key, get_key_1, get_key_2, set_fmt, fmt_1, fmt_2, labels, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Power button
        self.power_button = ControlButton(module, power_key)
        self.set_entry = SingleInputWidget(module, set_key, set_fmt)
        self.read_1_holder = SingleDisplayWidget(module, get_key_1, fmt_1)

        self.get_key_2 = get_key_2
        if self.get_key_2 is not None:
            self.read_2_holder = SingleDisplayWidget(module, get_key_2, fmt_2)

        self._layout = QHBoxLayout()

        self.init_done = False

        self.update_values()

        if not type(labels) == list:
            labels = [labels]
        # Label for values        
        self.set_label = QLabel(labels[0])

        self.set_layout(labels)

        self.update_labels()
        self.init_done = True

    def get_dpi(self):
        return widget_dpi(self)

    def set_layout(self, labels):
        self._layout.addWidget(self.power_button)
        self._layout.addSpacing(4)

        self._layout.addWidget(self.set_label)
        self._layout.addSpacing(2)
        self._layout.addWidget(self.set_entry)
        self._layout.addSpacing(4)

        if len(labels) > 1 and labels[1] is not None:
            self.read_1_label = QLabel(labels[1])
            self._layout.addWidget(self.read_1_label)
            self._layout.addSpacing(2)
        self._layout.addWidget(self.read_1_holder)
        self._layout.addSpacing(4)

        if len(labels) > 2 and labels[2] is not None:
            self.read_2_label = QLabel(labels[2])
            self._layout.addWidget(self.read_2_label)
            self._layout.addSpacing(2)
        if self.get_key_2 is not None:
            self._layout.addWidget(self.read_2_holder)
        self._layout.addStretch(1)
        
    def set_label_sizes(self, label_chars, set_chars, get_1_chars, get_2_chars):
        dpi_scale = scale(self.get_dpi())

        self.power_button.set_button_sizes(30 , 20)
        self.set_entry.set_label_sizes(set_chars)
        self.read_1_holder.set_label_sizes(get_1_chars)
        if self.get_key_2 is not None:
            self.read_2_holder.set_label_sizes(get_2_chars)

        label_chars *= dpi_scale
        fm = self.set_label.fontMetrics()
        w = label_chars*fm.width("0")
        self.set_label.setMaximumWidth(int(w))
        self.set_label.setMinimumWidth(int(w))

    def update_values(self):
        self.set_entry.update_values()
        self.read_1_holder.update_values()
        self.power_button.update_values()
        if self.get_key_2 is not None:
            self.read_2_holder.update_values()
        if self.init_done:
            self.update_labels()

    def update_labels(self):
        if not self.init_done:
            self.set_entry.update_labels()
        self.read_1_holder.update_labels()
        if self.get_key_2 is not None:
            self.read_2_holder.update_labels()

    def update_value(self):
        try:
            value = float(self.set_entry.text())
            self.client.set_value(self.set_key, value)
        except Exception as err:
            print(f"format error for setting {self.set_key} {err}")

class ValuesAndPowerPolarity(ValuesAndPower):
    def __init__(self, module, power_key, polarity_key, set_key, get_key_1, get_key_2, set_fmt, fmt_1, fmt_2, labels, *args, **kwargs):
        self.polarity_button = ControlButton(module, polarity_key, ["+", "-"], self.polarity_display, [1, -1], [_blue_, _green_])
        super().__init__(module, power_key, set_key, get_key_1, get_key_2, set_fmt, fmt_1, fmt_2, labels, *args, **kwargs)
        self.read_1_holder.scale = self.polarity_factor
    
    def polarity_display(self, x):
        if isinstance(self.polarity_button.value, bool):
            return not x
        return x > 0

    def polarity_factor(self, x):
        if isinstance(self.polarity_button.value, bool):
            return -x if self.polarity_button.value else x
        return x * self.polarity_button.value

    def update_values(self):
        self.polarity_button.update_values()
        super().update_values()

    def set_label_sizes(self, label_chars, set_chars, get_1_chars, get_2_chars):
        super().set_label_sizes(label_chars, set_chars, get_1_chars, get_2_chars)
        self.polarity_button.set_button_sizes(20, 20)

    def set_layout(self, labels):
        self._layout.addWidget(self.power_button)
        self._layout.addSpacing(4)

        self._layout.addWidget(self.polarity_button)
        self._layout.addSpacing(4)

        self._layout.addWidget(self.set_label)
        self._layout.addSpacing(2)
        self._layout.addWidget(self.set_entry)
        self._layout.addSpacing(4)

        if len(labels) > 1 and labels[1] is not None:
            self.read_1_label = QLabel(labels[1])
            self._layout.addWidget(self.read_1_label)
            self._layout.addSpacing(2)
        self._layout.addWidget(self.read_1_holder)
        self._layout.addSpacing(4)
        
        if len(labels) > 2 and labels[2] is not None:
            self.read_2_label = QLabel(labels[2])
            self._layout.addWidget(self.read_2_label)
            self._layout.addSpacing(2)
        if self.get_key_2 is not None:
            self._layout.addWidget(self.read_2_holder)
        self._layout.addStretch(1)

class TableDisplayWidget(QTableWidget):
    def __init__(self, module, headers, rows, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = module.client
        self.headers = headers
        self.rows = rows
        self.init = True
        self.cells = {}
        self.clickable = True
        self.setColumnCount(len(headers))
        self.setRowCount(len(rows))
        self.update_values()

    def no_clicky(self):
        self.clickable = False
        self.clicked.connect(self.clearSelection)
        self.pressed.connect(self.clearSelection)
        self.activated.connect(self.clearSelection)
        self.entered.connect(self.clearSelection)
        return self

    def setRangeSelected(self, range, select):
        if not self.clickable:
            return
        return super().setRangeSelected(range, select)
    
    def update_values(self):
        # rows format is a list of lists as follows:
        # [ "Name", valueA, fmtA, valueB, fmtB, etc]
        n = 0
        for row in self.rows:
            m = 0
            # First add row label
            if self.init:
                cell = QLabel(row[0])
                self.setCellWidget(n, m, cell)
                self.cells[f'{n},{m}'] = cell
            m = 1
            for i in range(1,len(row),2):
                key = row[i]
                fmt = row[i + 1]
                
                var = self.client.get_value(key)
                val = None
                if var is not None:
                    val = var
                    if isinstance(fmt, str):
                        var = fmt.format(var[1])
                    else:
                        var = fmt(var[1])
                if self.init:
                    cell = QLabel(str(var))
                    self.cells[f'{n},{m}'] = [cell, val]
                    self.setCellWidget(n, m, cell)
                else:
                    cell = self.cells[f'{n},{m}']
                    cell[0].setText(str(var))
                    cell[1] = val
                m += 1
            n += 1
        if not self.clickable:
            self.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
            self.clearSelection()
        self.init = False
        self.setHorizontalHeaderLabels(self.headers)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
