from math import ceil, floor
import numpy
from datetime import datetime
import json
import time
import zlib
import threading

import pyqtgraph as pg
from pyqtgraph import AxisItem

#  * import due to just being things from Qt
from ..utils.qt_helper import *
from ..utils import input_parser
from ..utils import data_client
from ..utils.data_client import BaseDataClient, DataCallbackServer
from ..utils.data_server import LogServer
from ..widgets.base_control_widgets import getGlobalStyleSheet
from ..widgets.base_control_widgets import LineEdit, FrameDock, ControlLine, StateSaver

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
        # Map of buttons by label, populated from above list
        self._button_objs_ = {}
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
    
    def make_option_dropdown(self, setting, key):     
        setting.option = QComboBox()
        opts = self._options_[key]
        opt_fmt = None
        if key in self._opt_fmts_:
            opt_fmt = self._opt_fmts_[key][0]
        if opt_fmt is None:
            opt_fmt = str
        opts_str = [opt_fmt(x) for x in opts]
        setting.option.addItems(opts_str)
        if self._default_option:
            setting.option.setCurrentText(self._default_option)
        if key in self._options_callbacks_:
            setting.option.activated.connect(self._options_callbacks_[key])

        def value_getter():
            opt_ufmt = None
            opts = setting.option.currentText()
            if key in self._opt_fmts_:
                opt_ufmt = self._opt_fmts_[key][1]
            if opt_ufmt is not None:
                opts = opt_ufmt(opts)
            return opts
        setting.getter = value_getter
        setting.setter = lambda x: setting.select_option(x, opts_str)


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
            thing.make_option_dropdown(self, key)
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
                if isinstance(attr, int):
                    fmt = "{:d}"
                    ufmt = int
                elif isinstance(attr, str):
                    fmt = "{}"
                    ufmt = str
                if key in thing._opt_fmts_:
                    fmt = thing._opt_fmts_[key]
                if hasattr(thing, "_opt_ufmts_") and key in thing._opt_ufmts_:
                    ufmt = thing._opt_ufmts_[key]
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
        if isinstance(self.option, QLayout):
            self.layout.addLayout(self.option)
        else:
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
        self.saves = False
        self.default_init_menu = False
        self.menu_action = None
        self.starts_floating = True

        # If this is true, this is considered a copied module
        # for cases where you have multiple of the same module allowed
        self.dummy = False

    def set_name(self, name):
        self.name = name

    def init_menu_naming(self, menu_name="Modules", key=None, name=None, help="Opens Module"):
        self.menu_key = key
        if name is not None:
            self.name = name
        self.menu_name = menu_name
        self.menu_help = help
        self.default_init_menu = True

    def set_saves(self, name):
        self.set_name(name)
        values = {}
        self.populate_save_values(values)
        self.saver = StateSaver(name, values, warn_many=False)
        self.on_loaded()
        self.saves = True

    def populate_save_values(self, values):
        return

    def on_loaded(self):
        return
    
    def save(self):
        self.saver.save(True)

    def get_layout(self):
        if self._layout == None:
            self.create_layout()
        return self._layout

    def create_layout(self):

        help_fn = None
        menu_fn = None
        if len(self.get_settings()):
            def _left_click():
                self.open_settings(False)
            def _right_click():
                self.open_settings(True)
            menu_fn = (_left_click, _right_click)
        if self._help_main:
            help_fn = self.open_help

        self._dock = FrameDock(self.name, closable=True, menu_fn=menu_fn, help_fn=help_fn)
        
        self._dock.setStyleSheet(getGlobalStyleSheet())
        widget = QWidget()
        self._dock.addWidget(widget)
        if self._dock_area is None:
            self._dock_area = self._root._main
        self._active = self._root
        self._layout = QHBoxLayout(widget)
        if self.starts_floating and len(self._dock_area.docks) > 0:
            self._dock.area = self._dock_area
            self._dock.float()
        else:
            self._dock_area.addDock(self._dock, self.placement)
        self._dock.sigClosed.connect(self.dock_closed)

    def open_settings(self, new_window=False):
        for setting in self.get_settings():
            key = setting._label
            callback = setting._callback
            if self.saves:
                def wrapped():
                    if setting._callback is not None:
                        setting._callback()
                    self.save()
                callback = wrapped
            self._root.edit_options(self._dock, setting, key, callback, new_window=new_window)

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
        if self.saves:
            self.saver.save(True)
            self.saver.close()

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

        if self.default_init_menu:
            _menu = Menu()
            # Add some options, the value is the function to run on click
            _menu._options[self.menu_key] = self.menu_action
            _menu._opts_order.append(self.menu_key)
            # Adds some help menu text for these as well
            _menu._helps[self.menu_key] = help
            # Adds labels for the non-separator values
            _menu._labels[self.menu_key] = self.name
            self.set_name(self.name)
            # Specify a label for the menu
            _menu._label = self.menu_name

            # Returns an array of menus (only 1 in this case)
            return [_menu]


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

        self.menu_action = self.start_plotting

    def using_main_window(self):
        return False

    def uses_main_window(self):
        return False

    def on_stop(self):
        super().on_stop()
        self.active = False
        if self.plot_widget is not None:
            self.plot_widget.close()
            self.plot_widget = None
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
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
        if self._plot_layout is not None:
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

class ClientWrapper(BaseDataClient):
    SET_WRAPPER = None
    def __init__(self) -> None:
        super().__init__()
    def set_value(self, key, value, timestamp=None):
        if ClientWrapper.SET_WRAPPER is not None:
            return ClientWrapper.SET_WRAPPER.set_value(key, value, timestamp)
        return super().set_value(key, value, timestamp)
    def get_value(self, key):
        if ClientWrapper.SET_WRAPPER is not None:
            return ClientWrapper.SET_WRAPPER.get_value(key)
        return super().get_value(key)

class MQTTClient(BaseDataClient):
    LAST_ALL_CHECK = 0
    all_values = {}
    def __init__(self) -> None:
        super().__init__()

    def close(self, _=False):
        return True

    def set_value(self, key, value, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        # Determine if this is a control variable
        from ..widgets import base_control_widgets
        if key in base_control_widgets.MQTT_CTRL_VALUES:
            # If this is the case, then whatever handles controls should
            # handle the change of this variable, then feed it back as a data
            # variable, via a manual call to publish_mqtt_data
            publish_mqtt_data(key, value, timestamp, 'ctrl')
        else:
            # Here we should also go an publish to /raw/, so it gets logged
            raw = data_client.pack_value(timestamp, value)
            publish_mqtt_data(key, value, timestamp, sub_path='raw', to_publish=raw)
            publish_mqtt_data(key, value, timestamp)
        return True
    
    def get_value(self, key):
        from ..widgets import base_control_widgets
        return base_control_widgets.callbacks.get_value(key)
    
    def get_all(self):
        now = time.time()
        if now - MQTTClient.LAST_ALL_CHECK < 15:
            return MQTTClient.all_values
        MQTTClient.LAST_ALL_CHECK = now
        import socket
        try:
            # Query list of keys from data server
            client_socket = socket.socket()     # instantiate
            client_socket.settimeout(10)        # Set a longish timeout, as we can request many things
            client_socket.connect(BaseDataClient.DATA_LOG_HOST)# connect to the server
            message = 'keys?'
            client_socket.send(message.encode())

            read = b'' # Build the response, by combining recv calls
            data = client_socket.recv(LogServer.MAX_PACKET_SIZE)  # receive response
            while data:
                read += data
                data = client_socket.recv(LogServer.MAX_PACKET_SIZE)  # receive response
            packet = read
            # If we are a combined packet, we have these as header and footer
            s = read.index(LogServer.HEADER)
            e = read.index(LogServer.FOOTER)
            if s >= 0 and e >= 0:
                packet = read[s + len(LogServer.HEADER):e]
                packet = zlib.decompress(packet)
            else:
                packet = b'error!'
            keys = json.loads(packet)
            for key in keys:
                if not key in MQTTClient.all_values:
                    MQTTClient.all_values[key] = (datetime.now(), 0.0)
        except Exception as err:
            print(err)
        return MQTTClient.all_values

def publish_mqtt_data(key, value, timestamp, sub_path='data', to_publish=None, immediate=False):
    if not isinstance(timestamp, float):
        timestamp = timestamp.timestamp()
    import paho.mqtt.publish as publish
    topic = f"{MQTT_TOPIC_ROOT}/{sub_path}/{key}"
    if to_publish is None:
        to_publish = {"time":timestamp, "value":value}
        to_publish = json.dumps(to_publish)

    def pub():
        publish.single(topic, to_publish, hostname=MQTT_SERVER, auth=MQTT_AUTH, retain=True)
    if immediate:
        pub()
    else:
        pub_thread = threading.Thread(target=pub, daemon=True)
        pub_thread.start()

__values__ = {}
__keys__ = []
__open__ = True
USE_ALL = True

global ended
ended = False
global local_server
local_server = None

global access_lock
access_lock = False

global USE_MQTT
USE_MQTT = False
global MQTT_SERVER
MQTT_SERVER = None
global MQTT_TOPIC_ROOT
MQTT_TOPIC_ROOT = ''
MQTT_AUTH = {}
MQTT_CTRL_HANDLERS = {}

def set_MQTT(server='127.0.0.1', topic_root='feeds', auth={}):
    global USE_MQTT
    global MQTT_SERVER
    global MQTT_TOPIC_ROOT
    
    USE_MQTT = True
    MQTT_SERVER = server
    MQTT_TOPIC_ROOT = topic_root
    for key, value in auth.items():
        MQTT_AUTH[key] = value
    
    from ..widgets import base_control_widgets
    base_control_widgets.callbacks = MQTTListener()
    def make_client():
        return MQTTClient()
    base_control_widgets.make_client = make_client

    global local_server
    if local_server is None:
        local_server = threading.Thread(target=run_mqtt, daemon=True)
        local_server.start()

def register_ctrl_handler(key, handler):
    MQTT_CTRL_HANDLERS[key] = handler

def run_mqtt():

    import json
    import paho.mqtt.client as mqtt
    from ..widgets import base_control_widgets

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code!='Success':
            print(f"MQTT result code: {reason_code}")
        callbacks = base_control_widgets.callbacks
        for key in callbacks.keys:
            # print(f"On Connect subscribe: {key}")
            client.subscribe(f"{MQTT_TOPIC_ROOT}/data/{key}")
            client.subscribe(f"{MQTT_TOPIC_ROOT}/ctrl/{key}")
        callbacks.connection = client

    # The callback for when a PUBLISH message is received from the server.
    def on_message(client, userdata, msg):
        callbacks = base_control_widgets.callbacks
        topic = msg.topic
        if '/ctrl/' in topic:
            key = topic.replace(f"{MQTT_TOPIC_ROOT}/ctrl/", "")
            if key in MQTT_CTRL_HANDLERS:
                args = json.loads(msg.payload.decode())
                stamp = args['time']
                value = args['value']
                MQTT_CTRL_HANDLERS[key](key, stamp, value)
            return
        key = topic.replace(f"{MQTT_TOPIC_ROOT}/data/", "")
        args = json.loads(msg.payload.decode())
        stamp = args['time']
        value = args['value']

        # print(f"Read {key} {value}")
        callbacks.listener(key, (stamp, value))
        callbacks.connection = client

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message

    if MQTT_AUTH is not None:
        mqttc.username = MQTT_AUTH['username']
        mqttc.password = MQTT_AUTH['password']

    while True:
        try:
            print("Connecting to MQTT")
            mqttc.connect(MQTT_SERVER, 1883, 60)
            mqttc.loop_forever()
        except Exception as err:
            print(f"Error in mqttc loop {err}")

def update_values():
    global local_server
    if USE_MQTT:
        return

    from ..widgets import base_control_widgets
    if local_server is None:
        from ..utils import data_server as server
        found = False

        if BaseDataClient.DATA_SERVER_KEY is None:
            BaseDataClient.DATA_SERVER_KEY = "LabGUI"

        if BaseDataClient.DATA_SERVER_KEY is not None:
            BaseDataClient.ADDR = data_client.find_server(BaseDataClient.DATA_SERVER_KEY, 'tcp', default_addr=None)
            BaseDataClient.DATA_LOG_HOST = data_client.find_server(BaseDataClient.DATA_SERVER_KEY, 'log', default_addr=None)
            if BaseDataClient.ADDR is not None:
                found = True

        if not found:
            print("Making Server!")
            (server_tcp, _), (server_udp, _), (saver, _) = server.make_server_threads()
            (server_logs, _) = server.make_log_thread()
            server.ServerProvider.server_key = BaseDataClient.DATA_SERVER_KEY
            # Now start the provider thread who says where the server is
            server.BaseDataServer.provider_thread.start()
            time.sleep(0.5)
            local_server = (server_tcp, server_udp, saver, server_logs)
            BaseDataClient.ADDR = data_client.find_server(BaseDataClient.DATA_SERVER_KEY, 'tcp', target_ip='127.0.0.1')
            BaseDataClient.DATA_LOG_HOST = data_client.find_server(BaseDataClient.DATA_SERVER_KEY, 'log', target_ip='127.0.0.1')
            print(BaseDataClient.ADDR)
        else:
            local_server = False

    base_control_widgets.callbacks = ValueListener(BaseDataClient.ADDR)

class ValueListener(DataCallbackServer):

    def __init__(self, client_addr=BaseDataClient.ADDR):
        super().__init__(client_addr=client_addr)
        self.values = {}
        self.timeout = 0.5

    def listener(self, key, value):
        if(isinstance(value[0], float)):
            value = (datetime.fromtimestamp(value[0]), value[1])
        self.values[key] = value

    def register_listener(self, key):
        client = BaseDataClient()
        client.register_callback_server(key, self.port)
        client.close()

    def get_value(self, key):
        if key in self.values:
            return self.values[key]
        return None

class MQTTListener(ValueListener):
    def __init__(self):
        self.values = {}
        self.keys = []
        self.timedout = []
        self.connection = None
        self.alive_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self._running_ = False
        self._dummy_ = True
        self.listeners = {}
        self.last_heard_times = {}
        self.timeout = 0.5

    def listener(self, key, value):
        if(isinstance(value[0], float)):
            value = (datetime.fromtimestamp(value[0]), value[1])
        with self.write_lock:
            MQTTClient.all_values[key] = value
            self.values[key] = value

    def register_listener(self, key):
        if not key in self.keys:
            self.keys.append(key)
            if self.connection is not None:
                def sub():
                    while not self.connection.is_connected():
                        time.sleep(0.001)
                    # print(f"Subscribing to {key}")
                    self.connection.subscribe(f"{MQTT_TOPIC_ROOT}/data/{key}")
                    self.connection.subscribe(f"{MQTT_TOPIC_ROOT}/ctrl/{key}")
                t = threading.Thread(target=sub, daemon=True)
                t.start()
    
    def get_value(self, key):
        resp = super().get_value(key)
        if resp is not None or key in self.keys:
            return resp
        # Try registering the value
        self.register_listener(key)
        # give a little bit of time to try to return the value
        start = time.time()
        while resp is None and time.time() - start < self.timeout:
            time.sleep(0.001)
            with self.write_lock:
                resp = super().get_value(key)
        return resp