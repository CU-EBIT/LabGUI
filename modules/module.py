from PyQt5.QtWidgets import QComboBox, QLabel, QCheckBox, QHBoxLayout, QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout, QWidget
from PyQt5 import QtCore
import pyqtgraph as pg
from pyqtgraph import AxisItem

import time
import threading
from math import ceil, floor
import numpy

from utils import input_parser
from utils import data_client
from widgets.base_control_widgets import getGlobalStyleSheet
from widgets.base_control_widgets import LineEdit, FrameDock, ControlLine

class BaseSettings:
    def __init__(self):
        # Names of the values, for showing in the options box
        self._names_ = {}
        # Units to go with the value, use `` if no units
        self._units_ = {}
        # These are options which should make a dropdown menu
        self._options_ = {}
        # Initial option if present
        self._default_option = None
        # These are tuples of functions for packing and unpacking the values.
        # If not specified, the `str` function is used for packing
        self._opt_fmts_ = {}
        # these are callbacks to run when the above options are selected
        self._options_callbacks_ = {}
        # The above values will result in Tkinter objects placed in here.
        self._entries_ = {}
        # Array of tuples, of ("Label", Callback) for push buttons
        self._buttons_ = []
        # A help string to show in the help menu
        self.help_text = ''
        # This is the label to click to ge the above help text,
        # this is also used for the label in the settings dropdown
        self._label = ''
        # If this is set to a function, it will be called whenever
        # the settings have been changed via a gui interaction
        self._callback = None
        # Used to notify as to who owns us for checking if a setting can change
        self._owner = None

    def on_window_created(self, window):
        return

class SettingOption:
    def __init__(self, value, key, thing, layout, force_update) -> None:
        self.layout = QHBoxLayout()
        self.label = QLabel()
        self.units = QLabel()
        self.label.setText(value)
        unit = ''
        if key in thing._units_:
            unit = thing._units_[key]
        self.units.setText(unit)
        self.getter = None
        self.option = None
        attr = getattr(thing, key)
        if key in thing._options_:
            self.option = QComboBox()
            opts = thing._options_[key]
            opt_fmt = None
            if key in thing._opt_fmts_:
                opt_fmt = thing._opt_fmts_[key][0]
            if opt_fmt is None:
                opt_fmt = str
            opts_str = [opt_fmt(x) for x in opts]
            self.option.addItems(opts_str)
            if thing._default_option:
                self.option.setCurrentText(thing._default_option)

            if key in thing._options_callbacks_:
                self.option.activated.connect(thing._options_callbacks_[key])

            def value_getter():
                opt_ufmt = None
                opts = self.option.currentText()
                if key in thing._opt_fmts_:
                    opt_ufmt = thing._opt_fmts_[key][1]
                if opt_ufmt is not None:
                    opts = opt_ufmt(opts)
                return opts
            self.getter = value_getter
            self.setter = lambda x: self.select_option(x, opts_str)
        elif isinstance(attr, bool):
            self.option = QCheckBox()
            self.option.setChecked(attr)
            self.getter = lambda:self.option.isChecked()
            self.setter = lambda x: self.option.setChecked(x)
            self.option.clicked.connect(force_update)
        else:
            self.option = LineEdit()
            self.getter = lambda:input_parser.parseVar(self.option.text())
            self.option.returnPressed.connect(force_update)
            fmtter = str
            try:
                float(attr)
                ufmt = float
                fmt = "{:.2f}"
                if key in thing._opt_fmts_:
                    fmt = thing._opt_fmts_[key]
                if isinstance(attr, int):
                    fmt = "{:d}"
                    ufmt = int
                fmtter = lambda x: fmt.format(x)
                def update():
                    self.set_value(self.get_value())
                    force_update()
                self.ctrl = ControlLine(update, self.option, fmt)
                self.ctrl.ufmt = ufmt
            except:
                pass

            self.option.setText(fmtter(attr))
            self.setter = lambda x: self.option.setText(fmtter(x))

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.option)
        self.layout.addWidget(self.units)

        self.layout.addStretch(0)
        self.layout.setSpacing(0)
        layout.addLayout(self.layout)
        
    def get_value(self):
        return self.getter()

    def set_value(self, value):
        self.setter(value)

class LabelledOption:
    def __init__(self, label, value, layout, width=None, ufmt=float, on_return=None, boxargs=None) -> None:
        self.layout = QVBoxLayout()
        self.label = QLabel()
        self.entry = LineEdit()
        self.ufmt = ufmt

        self.layout.addStretch(0)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.entry)

        self.label.setText(label)
        self.entry.setText(str(value))

        if boxargs is not None:
            layout.addLayout(self.layout, *boxargs)
        else:
            layout.addLayout(self.layout)

        if width is not None:
            self.label.setFixedWidth(width)
            self.entry.setFixedWidth(width)

        if on_return is not None:
            self.entry.returnPressed.connect(on_return)

    def get_value(self, default=None):
        try:
            return self.ufmt(self.entry.text())
        except Exception as err:
            print(err)
            return default

class Menu:
    def __init__(self):
        self._opts_order = []
        self._help_order = self._opts_order
        self._options = {}
        self._labels = {}
        self._helps = {}
        self._label = ''
        self._owners = {}
        self._owner = None

    def set_owner(self, module):
        self._owner = module

    def get_owner(self, key):
        if key in self._owners:
            return self._owners[key]
        return self._owner

    def is_same(self, other):
        return other._label == self._label
    
    def merge_in(self, other):
        if not self.is_same(other):
            return other

        self._opts_order.append('sep')
        self._opts_order.extend(other._opts_order)

        for key, val in other._options.items():
            self._options[key] = val
            self._owners[key] = other._owner
        for key, val in other._labels.items():
            self._labels[key] = val
            self._owners[key] = other._owner
        for key, val in other._helps.items():
            self._helps[key] = val
            self._owners[key] = other._owner

        return self

def deleteItemsOfLayout(layout):
     if layout is not None:
         while layout.count():
             item = layout.takeAt(0)
             widget = item.widget()
             if widget is not None:
                 widget.setParent(None)
             else:
                 deleteItemsOfLayout(item.layout())

class Module:

    def __init__(self, root):
        # This is the gui instance that owns this module.
        self._root = root
        self._active = root
        self._layout = None
        self._dock = None
        self.name = None
        self._help_main = None
        self.placement = 'top'
        self._dock_area = None
        self._stopped = False

    def set_name(self, name):
        self.name = name

    def set_saves(self, name):
        self.set_name(name)
        
    
    def get_layout(self):
        if self._layout == None:
            self.create_layout()
        return self._layout

    def create_layout(self):

        help_fn = None
        menu_fn = None
        if len(self.get_settings()):
            menu_fn = self.open_settings
        if self._help_main:
            help_fn = self.open_help

        self._dock = FrameDock(self.name, closable=True,menu_fn=menu_fn,help_fn=help_fn)
        
        self._dock.setStyleSheet(getGlobalStyleSheet())
        widget = QWidget()
        self._dock.addWidget(widget)
        if self._dock_area is None:
            self._dock_area = self._root._main
        self._active = self._root
        self._layout = QHBoxLayout(widget)
        self._dock_area.addDock(self._dock, self.placement)
        self._dock.sigClosed.connect(self.dock_closed)

    def open_settings(self):
        for setting in self.get_settings():
            key = setting._label
            callback = setting._callback
            self._root.edit_options(self._dock, setting, key, callback)

    def open_help(self):
        self._root.help_settings(*self._help_main)

    def delete_layout(self, box):
        if box is not None:
            for i in range(self.get_layout().count()):
                layout_item = self.get_layout().itemAt(i)
                if layout_item.layout() == box:
                    deleteItemsOfLayout(layout_item.layout())
                    self.get_layout().removeItem(layout_item)
                    break
        if self._dock is not None and self._dock.container() is not None:
            self._dock.close()
        self._layout = None

    def get_gui(self):
        return self._root

    def on_start(self):
        self._stopped = False

    def on_stop(self):
        self._stopped = True
    
    def dock_closed(self, *_):
        self.on_stop()
        self._dock = None
        self._layout = None

    def uses_main_window(self):
        return False

    def using_main_window(self):
        return False

    def pre_setting_changed(self, option, module):
        # option - name of setting window
        # module - owner of the setting window

        # This gets sent to all modules before a setting value is changed
        # This allows a module to do something to cancel the change if say it is
        # not active yet.

        # Return whether we allow the change
        return True

    def on_option_clicked(self, option, module):
        # option - name of value
        # module - owner of the value

        # This is called when an option gets clicked in a menu for an option.
        # this can be used to clean things up if the new module has taken over
        # the main window.

        # Return whether we allow the button click
        return True

    def get_settings(self):
        return []

    def get_menus(self):
        return []

pg.setConfigOption('background', (200, 201, 199))
pg.setConfigOption('foreground', 'k')

# Here we have a module that just makes a figure in the main window
class FigureModule(Module):
    
    def __init__(self, root):
        super().__init__(root)

        # self.canvas = None
        # self.toolbar = None
        self.anim = None
        self.plot_widget = None
        # self.fig = None
        # self.ax = None

        self._plot_layout = None
        self._timer = None

        self.active = False
        self.paused = False

        self.has_toolbar = True
        self.place_canvas = True

        self.update_rate = 50

    def using_main_window(self):
        return False

    def uses_main_window(self):
        return False

    def on_stop(self):
        if self._stopped:
            return
        self.active = False
        if self.plot_widget is not None:
            self.plot_widget.close()
            self.plot_widget = None
        if self._timer is not None:
            self._timer.stop()
        self._stopped = True
        self.clear_fig()

    def pause_animation(self, to_pause):
        if to_pause == self.paused:
            return
        self.paused = not self.paused

    def get_plot_layout(self):
        if self._plot_layout is not None:
            return self._plot_layout
        root_layout = self.get_layout()
        self._plot_layout = QVBoxLayout()
        root_layout.addLayout(self._plot_layout)
        return self._plot_layout
    
    def clear_fig(self):
        self.delete_layout(self._plot_layout)
        self._plot_layout = None

    # Displays the matplotlib figure fig in the main window
    def show_fig(self):
        self.clear_fig()
        
        if self.place_canvas:
            self.get_plot_layout().addWidget(self.plot_widget)

        if self.anim is not None:
            self._timer = QtCore.QTimer()
            self._timer.timeout.connect(self._update_canvas)
            self._timer.start(self.update_rate)

    def _update_canvas(self):
        if self.paused:
            return
        self.anim(None)

    def make_plot(self):
        # Here is where yours should setup your actual plot
        return

    def post_figure(self):
        # Here is where you should add things that you want to have on after the main plot has been added to the canvas
        return

    def on_option_clicked(self, _, module):
        return True

    def start_plotting(self):
        if self.active:
            return False
        self.clear_fig()
        self.active = True
        self.make_plot()
        self.show_fig()
        self.post_figure()
        return True

class BetterAxisItem(AxisItem):

    def __init__(self, orientation='left', pen=None, textPen=None, tickPen=None, linkView=None, parent=None, maxTickLength=-5, showValues=True, text='', units='', unitPrefix='', **args):
        super().__init__(orientation, pen, textPen, tickPen, linkView, parent, maxTickLength, showValues, text, units, unitPrefix, **args)
        self.tick_fmt = '{:.2e}'
        self.scale_fn = lambda x:x

    def tickValues(self, minVal, maxVal, size):
        return super().tickValues(minVal, maxVal, size)

    def logTickValues(self, minVal, maxVal, size, stdTicks):
        ticks = []
        for (spacing, t) in stdTicks:
            if spacing >= 1.0:
                ticks.append((spacing, t))
        # Above is from super class

        # this is all we changed
        if len(ticks) == 0 and len(stdTicks):
            for i in range(min(3, len(stdTicks))):
                ticks.append(stdTicks[i])

        # Below is from super class
        if len(ticks) < 3:
            v1 = int(floor(minVal))
            v2 = int(ceil(maxVal))
            #major = list(range(v1+1, v2))

            minor = []
            for v in range(v1, v2):
                minor.extend(v + numpy.log10(numpy.arange(1, 10)))
            minor = [x for x in minor if x>minVal and x<maxVal]
            ticks.append((None, minor))
        return ticks
    
    def logTickStrings(self, values, scale, spacing):
        # return super().logTickStrings(values, scale, spacing)
        return self.tickStrings(values, scale, spacing)

    def tickStrings(self, values, _, spacing):
        strings = []
        for v in values:
            if self.logMode:
                v = 10**v
            vs = self.scale_fn(v)
            vstr = self.tick_fmt.format(vs)
            strings.append(vstr)
        return strings
    
    def labelString(self):
        s = '%s' % (self.labelText)
        style = ';'.join(['%s: %s' % (k, self.labelStyle[k]) for k in self.labelStyle])
        return "<span style='%s'>%s</span>" % (style, s)

__values__ = {}
__keys__ = []
__open__ = False
USE_ALL = True

global _value_thread
_value_thread = None
global ended
ended = False
def update_values():
    global _value_thread
    client = data_client.BaseDataClient(data_client.ADDR)

    def run():
        avg_t = 0.05
        t_total = 0
        for _ in range(20):
            start = time.time()
            values = client.get_all()
            t_total += time.time() - start
        dt_per = t_total / 20
        do_all = USE_ALL and dt_per < avg_t / 2

        n = 0
        # m = 0

        while(not ended):
            start = time.time()
            if do_all:
                client.init_connection()
                values = client.get_all()
                for key, value in values.items():
                    __values__[key] = value
            else:
                for key in __keys__:
                    var = client.get_value(key)
                    if var is not None:
                        __values__[key] = var
            dt = time.time() - start
            sleep = avg_t - dt
            if sleep > 0:
                time.sleep(sleep)
            # else:
            #     m += 1
            # t_total += dt
            n += 1
            if n == 100:
                client.init_connection()
            #     print(f"Average time: {t_total/n:.3f}s, Too longs: {m}, totals: {n}")
                n = 0
            #     t_total = 0
            #     m = 0

    _value_thread = threading.Thread(target=run, daemon=True)
    _value_thread.start()

class ClientWrapper:
    def __init__(self) -> None:
        self.set_client = data_client.BaseDataClient(data_client.ADDR)

    def get_value(self, key, immediate=False):
        if not key in __keys__:
            __keys__.append(key)
        if not key in __values__:
            if immediate:
                return None
            self.set_client.init_connection()
            self.set_client.connection.settimeout(1)
            return self.set_client.get_value(key)
        return __values__[key]

    def get_float(self, key):
        return self.get_value(key)
    
    def get_bool(self, key):
        return self.get_value(key)

    def get_var(self, key):
        return self.get_value(key)

    def set_value(self, key, value):
        self.set_client.init_connection()
        return self.set_client.set_value(key, value)

    def set_float(self, key, value):
        self.set_client.init_connection()
        return self.set_client.set_float(key, value)
