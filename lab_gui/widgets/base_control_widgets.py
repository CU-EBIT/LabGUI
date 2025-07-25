import time
import os
import json
import datetime

from pyqtgraph.dockarea.DockArea import Dock
from pyqtgraph.dockarea.Dock import DockLabel

#  * import due to just being things from Qt
from ..utils.qt_helper import *
from ..utils.data_client import BaseDataClient

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
QTableWidget QTableCornerButton::section
{{
    background-color: {_light_grey_};
    color: {_black_};
}}
"""

# This is a ValueListener (see modules.module.ValueListener)
callbacks = None

def try_init_value(key, _default):
    client = BaseDataClient()
    vars = client.get_value(key)
    if vars is None:
        client.set_value(key, _default)
        return _default
    return vars[1]

def get_tracked_value(key):
    value = callbacks.get_value(key)
    if value is not None:
        return value
    client = BaseDataClient()
    value = client.get_value(key)
    client.close()
    callbacks.values[key] = value
    return value

def register_tracked_key(key):
    if callbacks.add_listener(key, callbacks.listener):
        client = BaseDataClient()
        client.register_callback_server(key, callbacks.port)
        client.close()

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

def addCrossHairs(plot_widget, coord_label=None, add_copy_event=True):
    """Adds a coordinate tooltip similar to the crosshairs example from pyqtgraph

    Args:
        plot_widget (Plot): plot to add coordinate tooltip to

    Returns:
        QLabel: the label with the coordinate information
    """
    if coord_label is None:
        coord_label = QLabel()
    def mouseMoved(evt):
        pos = evt
        if plot_widget.sceneBoundingRect().contains(pos):
            plot = plot_widget.getPlotItem()
            vb = plot.vb
            mousePoint = vb.mapSceneToView(pos)
            log = plot.ctrl.logYCheck.isChecked()
            x = mousePoint.x()
            y = mousePoint.y()
            if log:
                # Convert to log coords
                y = 10 ** y
                pass
            x_msg = f"{x:.3f}"
            y_msg = f"{y:.3f}"
            if y > 1e3 or y < 1e-1:
                y_msg = f"{y:.3e}"
            coord_label.setText(f"x={x_msg}, y={y_msg}")

    plot_widget.scene().sigMouseMoved.connect(mouseMoved)
    if add_copy_event:
        addDoubleClickCoordCopy(plot_widget)
    plot_widget._coord_label = coord_label
    return coord_label

def addDoubleClickCoordCopy(plot_widget):
    def mouseClicked(evt):
        try:
            pos = evt.scenePos()
        except AttributeError:
            # This throws exception if double clicked outside of plot
            return
        if evt.double() and plot_widget.sceneBoundingRect().contains(pos):
            plot = plot_widget.getPlotItem()
            vb = plot.vb
            mousePoint = vb.mapSceneToView(pos)
            log = plot.ctrl.logYCheck.isChecked()
            x = mousePoint.x()
            y = mousePoint.y()
            if log:
                # Convert to log coords
                y = 10 ** y
                pass
            clipboard = QtGui.QGuiApplication.clipboard()
            x_msg = f"{x:.3f}"
            y_msg = f"{y:.3f}"
            if y > 1e3 or y < 1e-1:
                y_msg = f"{y:.3e}"
            msg = f"x={x_msg}, y={y_msg}"
            clipboard.setText(msg)
    plot_widget.scene().sigMouseClicked.connect(mouseClicked)

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

        if isinstance(function, tuple):
            _right_click = function[1]
            function = function[0]
            _wrapped = self.menuButton.mouseReleaseEvent
            def mouse_wrapper(event, **kargs):
                _wrapped(event, **kargs)
                if event.button() == Qt.MouseButton.RightButton:
                    _right_click()
            self.menuButton.mouseReleaseEvent = mouse_wrapper
        
        self.menuButton.clicked.connect(function)
        icon = QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView
        self.menuButton.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.menuButton.setToolTip("Options")

    def add_help_button(self, function):
        self.helpButton = QtWidgets.QToolButton(self)

        if isinstance(function, tuple):
            _right_click = function[1]
            function = function[0]
            _wrapped = self.helpButton.mouseReleaseEvent
            def mouse_wrapper(event, **kargs):
                _wrapped(event, **kargs)
                if event.button() == Qt.MouseButton.RightButton:
                    _right_click()
            self.helpButton.mouseReleaseEvent = mouse_wrapper
        
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

class SubControlWidget:
    '''
    A Basic module for a control. This consists of a QFrame inside a FrameDock. 
    
    It provides methods for passing re-size commmands to modules, which are any object that provides an update_values function
    '''
    def __init__(self, fixed_size=True, menu_fn=None, help_fn=None, make_dock=True, make_frame=True):

        self.tick = 0
        self.updated = -10
        self.fixed_size = fixed_size

        self._modules = []
        self.oldDPI = 0
        
        if make_frame:
            self.makeFrame(menu_fn, help_fn, make_dock)

    def makeFrame(self, menu_fn=None, help_fn=None, make_dock=True):
        self.frame = QFrame()
        self.frame.setLineWidth(2)
        self.frame.setFrameShape(QFrame.Shape.WinPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.frame.setContentsMargins(2,2,2,2)
        if make_dock:
            self.dock = FrameDock(widget=self.frame,menu_fn=menu_fn,help_fn=help_fn)
            self.dock._holder_widget = self

    def close(self):
        """Called when module is removed, ensure to close any opened resources, etc here.
        """        
        return
    
    def post_added_to_dockarea(self):
        """Called after adding us to our parent's dock area, can be used to then add sub-docks
        """
        return

    def set_name(self, name):
        self.dock.label.setText(name)
        return self

    def get_dpi(self):
        return widget_dpi(self.frame)

    def resize(self, w, h):
        if self.fixed_size:
            w *= scale(self.get_dpi())
            self.frame.setFixedWidth(int(w))
            h *= scale(self.get_dpi())
            self.frame.setFixedHeight(int(h))
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

    def get_value(self):
        return self.ufmt(self.box.text())

    def adjust_number(self, old, new):
        return new

    def update_number(self, pos, dir):
        text = self.box.text()
        char = text[pos-1]
        exp = 'e' in text

        if(char != ".") or dir == 0:
            try:
                var = self.get_value()
                old_var = var
                
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
                
                var = self.ufmt(var)
                var = self.adjust_number(old_var, var)
                
                var = max(self.min, var)
                var = min(self.max, var)

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
        self.update_number(pos, 1)

    def down_arrow(self):
        pos = self.box.cursorPosition()
        if pos <= 0:
            return
        self.update_number(pos, -1)

    def enter_pressed(self):
        pos = self.box.cursorPosition()
        self.update_number(pos, 0)

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

class SaveModule(SubControlWidget):
    def __init__(self, **args):
        super().__init__(**args)
        
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
    def __init__(self, name, value_map, save_dir="./settings", log_dir="./logs", warn_many=True) -> None:
        """Constructs a new StateSaver, this will also make the appropriate save directory and load the values if present.

        If multiple of these of the same name are constructed, successive ones will have numbers appended to the end of the names.

        Args:
            name (str): Name of the file to use
            value_map (dict): map of key: value for things to save
            save_dir (str, optional): Directory to save to. Defaults to "./settings".
            log_dir (str, optional): Directory for logging (if needed). Defaults to "./logs".
            warn_many (bool, optional): If true, will warn if name already exists. Defaults to True.
        """
        if name in SAVER_NAMES:
            n = 1
            name_1 = f"{name}_{n}"

            if name_1 in SAVER_NAMES:
                for _ in range(256):
                    n += 1
                    name_1 = f"{name}_{n}"
                    if not name_1 in SAVER_NAMES:
                        break
            if warn_many:
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

    def save(self, mark_all_changed=False):
        """Called to save the file. If you do not call on_changed manually, then set mark_all_changed true.

        Args:
            mark_all_changed (bool, optional): If true, will update the datamap before saving. Defaults to False.
        """
        if mark_all_changed:
            for _, value in self.value_map.items():
                self.on_changed(value, False)
        with open(self.filename, 'w') as file:
            json.dump(self.data, file, indent = 2)

    def on_changed(self, value, do_save=True):
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
        if do_save:
            self.save()

    def close(self):
        """Call this when the owner is closed. This will free up the name saved, so that when it re-opens it is likely to get the same settings.
        """
        if self.name in SAVER_NAMES:
            del SAVER_NAMES[self.name]

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
        if event.key() == Key_Up:
            self.upPressed.emit()
        if event.key() == Key_Down:
            self.downPressed.emit()
        if event.key() == Key_Enter:
            self.enterPressed.emit()

class ControlButton(QPushButton):
    '''
    This is a QPushButton which syncs status with the data_client, based on the given key. If not dataclient or module, it acts like a checkbox
    '''
    def __init__(self, module=None, key=None, text=["On", "Off"], predicate=lambda x: x, values=[True, False], colours=[_green_, _red_], display_only=False, data_source=None, default_value=None, toggle=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.tracked = False
        if module is not None:
            self.client = module.client
            self.tracked = True
            register_tracked_key(key)
        elif data_source is not None:
            self.client = data_source
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
        self.locked = False
        self.checked_lock_tooltip = False
        self.value = default_value
        self.timestamp = 0
        if toggle is not None:
            old_tgl = self.toggle
            def wrapped():
                if self.disabled or self.locked:
                    return
                old_tgl()
                toggle()
            self.toggle = wrapped
        if not display_only:
            self.clicked.connect(self.toggle)

        def update_style(button, value):
            button.setText(button.text_opts[0] if button.predicate(value) else button.text_opts[1])
            button.setStyleSheet(f"background-color : {button.colours[0] if button.predicate(value) else button.colours[1]}")

        self.style_updater = update_style
        self.default_tooltip = ''
        self.isChecked()

    def isChecked(self):        
        if self.value is not None:
            self.style_updater(self, self.value)
        return self.value

    def setChecked(self, a0: bool) -> None:
        self.value = a0
        return super().setChecked(a0)

    def update_values(self):
        if self.disabled:
            return
        if self.tracked:
            var = get_tracked_value(self.key)
        elif self.client is None:
            var = None
        else:
            var = self.client.get_value(self.key)
        if var is not None:
            self.timestamp = var[0]
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
        if self.disabled or self.locked:
            return
        new_value = self.values[1] if self.predicate(self.value) else self.values[0]
        if self.client is not None:
            self.client.set_value(self.key, new_value)
            if self.tracked:
                callbacks.values[self.key] = (datetime.datetime.now(),new_value)
        self.value = new_value
        self.update_values()

    def lock(self):
        if not self.checked_lock_tooltip:
            self.hasTooltip = self.toolTip() != ''
            self.checked_lock_tooltip = True
        if not self.hasTooltip:
            self.setToolTip("Locked")
        self.locked = True

    def unlock(self):
        if not self.checked_lock_tooltip:
            self.hasTooltip = self.toolTip() != ''
            self.checked_lock_tooltip = True
        if not self.hasTooltip:
            self.setToolTip("")
        self.locked = False

class InterlockButton(QPushButton):
    """
    This button allows adding a series of buttons to try to keep locked. 
    this calls the "lock" and "unlock" functions for the contents of the passed in buttons list

    After unlock_dur, this button will automatically re-call the "lock" function.
    """
    def __init__(self, buttons:list, unlock_dur=10, on_lock = lambda self: self.set_locked_texture(), 
                on_unlock = lambda self: self.set_unlocked_texture(), no_icon=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.unlock_time = 0
        self.unlock_dur = unlock_dur

        self.on_lock = on_lock
        self.on_unlock = on_unlock

        self.buttons = buttons
        self.no_icon = no_icon
        
        self.lock()

        def toggle():
            if self.locked:
                self.unlock()
            else:
                self.lock()

        self.clicked.connect(toggle)

    def set_locked_texture(self):
        if not self.no_icon:
            icon = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
            self.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.setStyleSheet(f"background-color : {_red_}")

    def set_unlocked_texture(self):
        if not self.no_icon:
            icon = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
            self.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.setStyleSheet(f"background-color : {_green_}")

    def lock(self):
        self.locked = True
        self.on_lock(self)
        for button in self.buttons:
            button.lock()

    def unlock(self):
        self.unlock_time = time.time()
        self.locked = False
        self.on_unlock(self)
        for button in self.buttons:
            button.unlock()

    def get_dpi(self):
        return widget_dpi(self)
    
    def update_values(self):
        now = time.time()
        if not self.locked and now > self.unlock_time + self.unlock_dur:
            self.lock()

    def set_button_sizes(self, w, h):
        dpi_scale = scale(self.get_dpi())
        h = int(h * dpi_scale)
        self.setFixedHeight(int(h))
        w = int(w * dpi_scale)
        self.setFixedWidth(int(w))

###
### Widgets below here are all set to use the data_client and BaseDataClient for value set/lookup
### Do not use the below widgets unless you are using that server system for value management!
###

class SingleDisplayWidget(QLabel):
    '''
    This is a QLabel which updates its value based on looking up the key on the data_client. This only works if the module has a valid data_client!
    '''
    def __init__(self, module, key, fmt, scale = lambda x: x, data_source=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.scale = scale
        self.value = 0
        self.timestamp = 0
        if data_source is not None:
            self.get_value = data_source.get_value
        else:
            self.get_value = get_tracked_value
            register_tracked_key(key)
        
        self.key = key
        self.fmt = fmt

    def get_dpi(self):
        return widget_dpi(self)
        
    def set_label_sizes(self, size):
        size *= scale(self.get_dpi())
        fm = self.fontMetrics()
        w = size*fm.averageCharWidth()
        self.setMaximumWidth(int(w))
        self.setMinimumWidth(int(w))

    def update_values(self):
        var = self.get_value(self.key)
        if var is not None:
            self.timestamp = var[0]
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
        register_tracked_key(key)
        self.input_active_checker = 0
        self.fmt = fmt
        self.value = 0
        self.timestamp = 0

        self.typing = typing

        self.ctrl = ControlLine(self.update_value, self, self.fmt)
        self.returnPressed.connect(self.update_value)
        self.ctrl.ufmt = typing
    def get_dpi(self):
        return widget_dpi(self)
    
    def keyPressEvent(self, event):
        # give 10s for user to press enter to confirm
        self.input_active_checker = time.time() + 10
        return super().keyPressEvent(event)
        
    def set_label_sizes(self, size):
        size *= scale(self.get_dpi())
        fm = self.fontMetrics()
        m = self.textMargins()
        c = self.contentsMargins()
        w = size*fm.averageCharWidth()+m.left()+m.right()+c.left()+c.right()
        self.setMaximumWidth(int(w))
        self.setMinimumWidth(int(w))

    def update_values(self):
        if self.input_active_checker > time.time():
            return
        var = get_tracked_value(self.key)
        if var is not None:
            self.timestamp = var[0]
            self.value = var[1]
            self.update_labels()
            self.input_active_checker = time.time() + 1

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

        if not type(labels) == list:
            labels = [labels]
        # Label for values        
        self.set_label = QLabel(labels[0])

        self.read_1_label = None
        self.read_2_label = None

        self.custom_buttons = False

        self.set_layout(labels)

    def get_dpi(self):
        return widget_dpi(self)

    def set_layout(self, labels):
        self._layout.addWidget(self.power_button)

        self._layout.addWidget(self.set_label)
        self._layout.addWidget(self.set_entry)

        if len(labels) > 1 and labels[1] is not None:
            self.read_1_label = QLabel(labels[1])
            self._layout.addWidget(self.read_1_label)
        self._layout.addWidget(self.read_1_holder)

        if len(labels) > 2 and labels[2] is not None:
            self.read_2_label = QLabel(labels[2])
            self._layout.addWidget(self.read_2_label)
        if self.get_key_2 is not None:
            self._layout.addWidget(self.read_2_holder)
        self._layout.addStretch(1)
        
    def set_label_sizes(self, label_chars, set_chars, get_1_chars, get_2_chars, read_1_chars=0, read_2_chars=0):
        dpi_scale = scale(self.get_dpi())

        if read_1_chars == 0:
            read_1_chars = label_chars
        if read_2_chars == 0:
            read_2_chars = label_chars

        if not self.custom_buttons:
            self.power_button.set_button_sizes(30 , 20)
        
        self.set_entry.set_label_sizes(set_chars)
        self.read_1_holder.set_label_sizes(get_1_chars)
        if self.get_key_2 is not None:
            self.read_2_holder.set_label_sizes(get_2_chars)

        label_chars *= dpi_scale
        fm = self.set_label.fontMetrics()
        w = label_chars*fm.averageCharWidth()
        self.set_label.setFixedWidth(int(w))

        if self.read_1_label != None:
            read_1_chars *= dpi_scale
            fm = self.read_1_label.fontMetrics()
            w = read_1_chars*fm.averageCharWidth()
            self.read_1_label.setFixedWidth(int(w))

        if self.read_2_label != None:
            read_2_chars *= dpi_scale
            fm = self.read_2_label.fontMetrics()
            w = read_2_chars*fm.averageCharWidth()
            self.read_2_label.setFixedWidth(int(w))

    def update_values(self):
        self.set_entry.update_values()
        self.read_1_holder.update_values()
        self.power_button.update_values()
        if self.get_key_2 is not None:
            self.read_2_holder.update_values()
        self.update_labels()

    def update_labels(self):
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
        if self.polarity_button.value is None:
            return 0
        if isinstance(self.polarity_button.value, bool):
            return -x if self.polarity_button.value else x
        return x * self.polarity_button.value

    def update_values(self):
        self.polarity_button.update_values()
        super().update_values()

    def set_label_sizes(self, label_chars, set_chars, get_1_chars, get_2_chars, read_1_chars=0, read_2_chars=0):
        super().set_label_sizes(label_chars, set_chars, get_1_chars, get_2_chars, read_1_chars, read_2_chars)
        self.polarity_button.set_button_sizes(20, 20)

    def set_layout(self, labels):
        self._layout.addWidget(self.power_button)
        self._layout.addWidget(self.set_label)
        self._layout.addWidget(self.set_entry)

        if len(labels) > 1 and labels[1] is not None:
            self.read_1_label = QLabel(labels[1])
            self._layout.addWidget(self.read_1_label)
        self._layout.addWidget(self.read_1_holder)
        
        if len(labels) > 2 and labels[2] is not None:
            self.read_2_label = QLabel(labels[2])
            self._layout.addWidget(self.read_2_label)
        if self.get_key_2 is not None:
            self._layout.addWidget(self.read_2_holder)
            
        self._layout.addStretch(1)
        self._layout.addWidget(self.polarity_button)

class TableDisplayWidget(QTableWidget):
    def __init__(self, module, headers, rows, cell_size=lambda cell, *_:cell.width(), font_size=9, data_source=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = module.client
        if data_source is not None:
            self.get_value = data_source.get_value
            self.register_value = lambda *_:()
        else:
            self.get_value = get_tracked_value
            self.register_value = register_tracked_key
        self.col_headers = headers[0]
        self.row_headers = headers[1]
        self.rows = rows
        self.init = True
        self.cells = {}
        self.clickable = True
        self.cell_size = cell_size
        self.padding = [' ', ' ']
        self._added_horiz = False
        self._added_vert = False
        self.font_size = font_size
        self.setColumnCount(len(self.col_headers))
        self.setRowCount(len(self.row_headers))
        self.setVerticalHeaderLabels(self.row_headers)
        self.setHorizontalHeaderLabels(self.col_headers)
        self.setViewportMargins(0,0,0,0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.update_values()

    def no_clicky(self):
        self.clickable = False
        self.clicked.connect(self.clearSelection)
        self.pressed.connect(self.clearSelection)
        self.activated.connect(self.clearSelection)
        self.entered.connect(self.clearSelection)

        self.horizontalHeader().setSectionsClickable(False)
        self.horizontalHeader().setSectionsMovable(False)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)

        self.verticalHeader().setSectionsClickable(False)
        self.verticalHeader().setSectionsMovable(False)
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        
        return self

    def setRangeSelected(self, range, select):
        if not self.clickable:
            return
        return super().setRangeSelected(range, select)
    
    def update_values(self):
        # rows format is a list of lists as follows:
        # [ "Name", valueA, fmtA, valueB, fmtB, etc]
        column_widths = [0.0 for _ in range(self.columnCount())]
        for n in range(len(self.rows)):
            row = self.rows[n]
            m = 0
            for i in range(0,len(row),2):
                key = row[i]
                fmt = row[i + 1]
                cell_key = f'{n},{m}'
                var = None
                if self.init:
                    self.register_value(key)
                var = self.get_value(key)
                val = None
                if var is not None:
                    val = var
                    if isinstance(fmt, str):
                        var = fmt.format(var[1])
                    else:
                        var = fmt(var[1])
                cell_widget = None
                if self.init:
                    cell = QLabel(str(var))
                    font = QtGui.QFont()
                    font.setPointSize(self.font_size)
                    cell.setFont(font)
                    self.cells[cell_key] = [cell, val]
                    self.setCellWidget(n, m, cell)
                    cell_widget = cell
                else:
                    cell = self.cells[cell_key]
                    cell_widget = cell[0]
                    cell_widget.setText(f'{self.padding[0]}{var}{self.padding[1]}')
                    cell[1] = val
                size = self.cell_size(cell_widget, m, n)
                column_widths[m] = max(column_widths[m], size)
                m += 1 
        if not self.clickable:
            self.setEditTriggers(TableNoEdit)
            self.clearSelection()

        if self.init:
            self.resizeRowsToContents()

        dpi_scale = scale(widget_dpi(self))
        # Compute maximum length of a row label
        w = 0
        # Compute height of the column headers
        h = self.horizontalHeader().height() if self.horizontalHeader().isVisible() else 0
        for i in range(self.rowCount()):
            _header = self.verticalHeaderItem(i)
            header_f = _header.font()
            header_t = _header.text()
            metrics = QtGui.QFontMetricsF(header_f)
            self.setRowHeight(i, metrics.height())
            header_w = (len(header_t))*metrics.averageCharWidth()*dpi_scale
            h += self.rowHeight(i)
            w = max(w, header_w)
        self.verticalHeader().setFixedWidth(w)
        w = self.verticalHeader().width()

        columns_w = 0
        for i in range(self.columnCount()):
            _header = self.horizontalHeaderItem(i)
            header_f = _header.font()
            header_t = _header.text()
            metrics = QtGui.QFontMetricsF(header_f)
            header_w = (len(header_t)+2)*metrics.averageCharWidth()*dpi_scale
            column_w = max(column_widths[i], header_w)+2
            self.setColumnWidth(i, column_w)
            columns_w += column_w
            for j in range(self.rowCount()):
                self.cellWidget(j, i).setFixedWidth(column_w-1)
        w += columns_w
        _w = self.size().width()
        _h = self.size().height()
        if _w != w or _h != h:
            self.resize(w+4, h+4)

        self.init = False
