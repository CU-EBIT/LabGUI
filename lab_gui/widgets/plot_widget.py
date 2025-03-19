import numpy
import json
import zlib

import socket
from datetime import datetime
from dateutil import parser
import time

import scipy.signal as signal

import threading

import pyqtgraph as pg

#  * import due to just being things from Qt
from ..utils.qt_helper import *
from ..utils import data_client
from ..utils.data_client import BaseDataClient
from ..utils.data_server import LogServer

from ..modules.module import ClientWrapper, BetterAxisItem, BaseSettings
from .base_control_widgets import register_tracked_key, get_tracked_value

LOG_ACCESS = True

def can_access_logs():
    return LOG_ACCESS and BaseDataClient.DATA_LOG_HOST != None

def get_value_log(key, start=1, end=0, since=None, until=None):
    '''
    This asks the Logging computer for the log of values for the given key.

    key is the item to obtain the log for
    if all is true, then it will obtain values from start hours ago untill end hours ago
    if all is false, then it will obtain the values since last, where last is a string representation
    of a datetime

    The return value is a tuple, of (valid, array), where valid is whether
    the data was obtained
    '''
    
    try:
        client_socket = socket.socket()     # instantiate
        client_socket.settimeout(10)        # Set a longish timeout, as we can request many things
        client_socket.connect(BaseDataClient.DATA_LOG_HOST)# connect to the server

        # Assemble message based on parameters
        message = LogServer.make_request_message(key, start, end, since, until)

        # Send message to server
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
        else:
            packet = b'error!'

        client_socket.close()  # close the connection
    except Exception as err:
        print(f'Log Update Error: {err}')
        return False, []

    # If we got b'error!', then it wasn't a valid response
    valid = packet != b'error!'
    values = []
    if valid:
        packet = zlib.decompress(packet)
        # Otherwise we got some json to unpack values from
        values = json.loads(packet.decode())
        # values = pickle.loads(packet)
        valid = len(values) > 0
    return valid, values

_plots = {} # Map of the data logs
_preload_hours = 1 # How long to default preload
_max_points = 1e6

def smooth_average(array):
    '''Returns a smoothed version of array'''
    b, a = signal.butter(1, 0.05)
    return signal.filtfilt(b, a, array)

def pre_fill(key, start, end=0):
    plots = _plots[key]
    # First get the all array, up to preload hours
    valid, array = get_value_log(key, start=start, end=end)
    if valid:
        _array = numpy.array(array)
        _x = _array[0]
        _y = _array[1]
        
        # If we were valid, stuff the values into the array,
        # We do have a maxiumum number of values of _max_points however
        size = min(len(_x), _max_points)

        times = numpy.full(int(_max_points), _x[0]) # Pre-populate array with the start values
        values = numpy.full(int(_max_points), _y[0])
        times[:size] = _x
        values[:size] = _y

        plots[0] = times
        plots[1] = values
        plots[2] = smooth_average(values)
        plots[3] = True # Mark the plot as having been initialised
        plots[4] = size # treat as having rolled back size times

def clear_plot(key, reload=False, start=None, end=0):
    '''Initialises a clear plot for key, if reload is True, then we also try to populate it from the SQL tables'''

    if start is None:
        start = _preload_hours

    plot = [
        numpy.full(int(_max_points), datetime.now().timestamp()), # Times
        numpy.zeros(int(_max_points)), # Values
        numpy.zeros(int(_max_points)), # Averages
        False, # If setup yet
        0, # number of times rolled
        True, # Whether we are clearing the plot
    ]
    _plots[key] = plot
    # Only reload if the address is the "real" one, as to not load garbage during testing
    do_run = reload and can_access_logs()
    if do_run:
        pre_fill(key, start, end)
    plot[5] = False

def roll_plot_values(plots, value, timestamp):
    if len(plots) > 5 and plots[5]:
        return
    times = plots[0]
    values = plots[1]
    avgs = plots[2]
    existing = plots[3]
    if not existing: # First time we back-fill the arrays with initial value
        times = numpy.full(int(_max_points), timestamp[0])
        values = numpy.full(int(_max_points), value[0])
        avgs = smooth_average(values)
        plots[3] = True
        plots[4] = 0 # clear rolled status
    else: # Otherwise we roll back the arrays, and append the new value to the end
        timestamp = numpy.array(timestamp)
        value = numpy.array(value)
        
        length = len(timestamp)
        times = numpy.roll(times,-length)
        values = numpy.roll(values,-length)
        avgs = numpy.roll(avgs,-length)

        times[-length:] = timestamp
        values[-length:] = value
        plots[4] = plots[4] + 1 # Increment rolled status
    # Finally update the arrays
    avgs[-100:] = smooth_average(values[-200:])[-100:]
    plots[0] = times
    plots[1] = values
    plots[2] = avgs

def get_values(first:bool, key:str):
    '''This updates the values in _plots for key, it will also try to pre-fill with existing values if first is true'''

    if can_access_logs():
        try:
            # Try pre-filling array
            # Only pre-fill if on the real address, and on first run
            if first:
                try:
                    pre_fill(key, _preload_hours, 0)
                except Exception as err:
                    print(f'pre_fill Error {err}')
            else:
                plots = _plots[key]
                if len(plots) > 5 and plots[5]:
                    return
                times = plots[0]
                last_stamp = times[-1]
                
                # First get the all array, up to preload hours
                valid, array = get_value_log(key, since=last_stamp)
                if not valid:
                    print(f"Not valid for {key}")
                    return
                roll_plot_values(plots, array[1], array[0])
            return
        except Exception as err:
            print(f'get_values part 1 Error {err}')

    if first:
        register_tracked_key(key)
    # Now try filling new value in
    
    plots = _plots[key]
    if len(plots) > 5 and plots[5]:
        return
    read = get_tracked_value(key)
    # Skip if not present
    if read is None:
        return
    times = plots[0]
    timestamp = read[0].timestamp()
    value = read[1]
    # Otherwise, only add if the timestamp has changed
    if timestamp != times[-1]:
        roll_plot_values(plots, [value], [timestamp])

__threads__ = {} # Cache of threads to prevent the GC from eating them
__update_rate_ = 2.5e-1

def run_plot_thread(key):
    if key in __threads__ or key is None:
        return
    cache = [None, True, time.time()]
    __threads__[key] = cache
    '''Starts a thread for obtaining values for key for plotting'''
    def run():
        '''Run loop to keep the values updates'''
        # Start by initialisng the plots
        clear_plot(key)
        first = True

        # We only want to automatically clear if we have access to historical logs
        auto_clears = can_access_logs()

        from time import perf_counter
        lastTime = perf_counter()
        n = 0
        while cache[1]:
            get_values(first, key)
            first = False
            now = perf_counter()
            dt = now - lastTime
            # Check if we have not been used lately, and if so, terminate
            last_access = cache[2]
            if auto_clears and time.time() - last_access > 300:
                cache[1] = False
                break
            if dt < __update_rate_:
                time.sleep(__update_rate_ - dt)
            n+=1
            lastTime = perf_counter()
        del __threads__[key]
        del _plots[key]

    # make and start the thread
    live_plot_thread = threading.Thread(target=run, daemon=True)
    cache[0] = live_plot_thread
    live_plot_thread.start()
    # and add to cache to protect from the GC
    __threads__[key] = cache

def adjust_nudge(self, nudge=0):

    def resizeEvent(ev=None):
        #s = self.size()

        ## Set the position of the label
        if self.label is None: # self.label is set to None on close, but resize events can still occur.
            self.picture = None
            return
            
        br = self.label.boundingRect()
        p = QtCore.QPointF(0, 0)
        if self.orientation == 'left':
            p.setY(int(self.size().height()/2 + br.width()/2))
            p.setX(-nudge)
        elif self.orientation == 'right':
            p.setY(int(self.size().height()/2 + br.width()/2))
            p.setX(int(self.size().width()-br.height()+nudge))
        elif self.orientation == 'top':
            p.setY(-nudge)
            p.setX(int(self.size().width()/2. - br.width()/2.))
        elif self.orientation == 'bottom':
            p.setX(int(self.size().width()/2. - br.width()/2.))
            p.setY(int(self.size().height()-br.height()+nudge))
        self.label.setPos(p)
        self.picture = None
    self.resizeEvent = resizeEvent

class Settings(BaseSettings):
    '''
    Settings class for options for plots
    '''
    def __init__(self):
        super().__init__()
        # Names of the values, for showing in the options box
        self._names_ = {
            'paused': 'Plot Paused: ',
            'update_rate': 'Update Rate: ',
            'log_length': 'Log Length: ',
            'reload_hours': 'Reload Length: ',
            'scale': 'Scale: ',
            'axis_name': 'Axis Label: ',
            'source_key': 'Key: ',
            'log_scale': 'log Plot: ',
            'y_axis_fmt': 'Y Axis Format: ',
            'title_fmt': 'Title Format: ',
        }
        # Units to go with the value, use `` if no units
        self._units_ = {
            'avg_length': 'points',
            'log_length': 'hours',
            'reload_hours': 'hours',
            'update_rate': 'ms',
        }

        def opt_changed(*_):
            '''Updates things when the dropdown list is changed'''
            chosen = self._entries_['source_key'].get_value()
            if chosen == 'None' or chosen.strip() == '':
                chosen = None
            self.source_key = chosen
            if chosen is not None and chosen in self._option_defaults_:
                defs = self._option_defaults_[chosen]
                self.axis_name = defs[0]
                self.scale = defs[1]
                axis_entry = self._entries_['axis_name']
                axis_entry.set_value(self.axis_name)
                scale_entry = self._entries_['scale']
                scale_entry.set_value(self.scale)
                if len(defs) > 2:
                    self.y_axis_fmt = defs[2]
                    fmt_entry = self._entries_['y_axis_fmt']
                    fmt_entry.set_value(self.y_axis_fmt)
                if len(defs) > 3:
                    self.log_scale = defs[3]
                    log_entry = self._entries_['log_scale']
                    log_entry.set_value(self.log_scale)

        self._options_callbacks_['source_key'] = opt_changed

        self._opt_fmts_ = {
            'source_key': (str, None),
            'log_length': "{:0.3f}",
        }

        def refresh_pressed():
            if self.source_key == 'None' or self.source_key.strip() == '':
                self.source_key = None
            if self.source_key is not None:
                clear_plot(self.source_key, True, start=self.reload_hours)
            if self._callback is not None:
                self._callback()

        self._buttons_ = [("Refresh",refresh_pressed)]

        self.paused = False
        self.log_length = 0.5
        self.update_rate = 500
        self.scale = 1
        self.reload_hours = 8.0
        self.log_scale = True
        self.y_axis_fmt = '{:.2e}'
        self.source_key = 'Pressure_HV_Source'
        self.axis_name = 'Source Pressure (mbar)'
        self.title_fmt = 'Latest: {:.2e}'
        self.title_fmter = lambda x: self.title_fmt.format(x)
        self._default_option = self.source_key

        # A help string to show in the help menu
        self.help_text = 'Log Length: Length of time shown on the plot\n'+\
                         'Axis Label: Label for Y-axis of the plot\n'+\
                         'Source Table: Which SQL table to look for value in\n'+\
                         'Value: Column in the SQL table to use for value\n'+\
                         'Key: SQL match key for the row to use'

        # This is the label to click to ge the above help text,
        # this is also used for the label in the settings dropdown
        self._label = 'Plot Settings'

        # If this is set to a function, it will be called whenever
        # the settings have been changed via a gui interaction
        self._callback = None
    
    def get_value(self):
        ret = (None, None, None)
        if hasattr(self, 'source_key'):
            if self.source_key in _plots:
                ret = _plots[self.source_key]
        return ret
    
    def make_option_dropdown(self, setting, key):
        # The super() call makes a QComboBox as setting.option, we
        # need to replace it with a layout of the box, with an update button
        # where the update button will run a get_all from dataclient
        # and then update the dropdown box with all valid keys
        super().make_option_dropdown(setting, key)

        def on_update():
            client = ClientWrapper()
            _map = client.get_all()
            option = setting._option
            old_selected = setting.get_value()
            if not old_selected or len(old_selected) == 0:
                old_selected = getattr(self, key)
            
            keys = []
            for _key, value in _map.items():
                if value != None and isinstance(value[1], float):
                    keys.append(_key)
            # Clear initial options
            while option.count():
                option.removeItem(0)
            keys.sort()
            keys.insert(0, 'None')
            opt_fmt = None
            if key in self._opt_fmts_:
                opt_fmt = self._opt_fmts_[key][0]
            if opt_fmt is None:
                opt_fmt = str
            opts_str = [opt_fmt(x) for x in keys]
            option.addItems(opts_str)
            if old_selected in keys:
                option.setCurrentText(old_selected)
            elif self._default_option in keys:
                option.setCurrentText(self._default_option)
            if key in self._options_callbacks_:
                option.activated.connect(self._options_callbacks_[key])

        setting._option = setting.option

        def value_getter():
            opt_ufmt = None
            opts = setting._option.currentText()
            if key in self._opt_fmts_:
                opt_ufmt = self._opt_fmts_[key][1]
            if opt_ufmt is not None:
                opts = opt_ufmt(opts)
            return opts
        # Call this once to init the list
        on_update()
        setting.getter = value_getter

        button = QPushButton("Update List")
        button.clicked.connect(on_update)
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(setting._option)
        layout.addWidget(button)
        layout.addStretch(0)
        setting.option = layout

    def _saver_save_(self):
        values = {}
        for key in self._names_.keys():
            values[key] = getattr(self, key)
        return values
    
    def _saver_load_(self, values):
        for key in values.keys():
            if hasattr(self, key) and key in self._names_:
                setattr(self, key, values[key])
        if hasattr(self, 'source_key'):
            if self.source_key == 'None' or self.source_key.strip() == '':
                self.source_key = None
            self._default_option = self.source_key

plot_colours = [(245,102,0), (185,71,0), (84,98,35), (239,219,178)]
avgs_colours = [(82,45,128), (46,26,71), (0,32,91), (0,94,184)]

class Plot(QWidget):
    '''Widget for plotting values from the _plots map above'''
    def __init__(self, x_axis=None, y_axis=None, y_2_axis=None) -> None:
        super().__init__()

        self.show_avg = True # Whether we include a smoothed plot

        self.client = ClientWrapper()

        self.settings = Settings() # Settings object we use

        # Some cache values for updating/limits
        self.start_index = 0
        self.last_stamp = 0.0
        self.last_label = None
        self._has_value = False

        self.keys = []  # Array of keys we plot from, as (key, label_raw, label_smooth)
        self.plots = [] # Array of tuples of (plot_raw, plot_smooth)

        self._timer = None # Timer for updates

        # Axis labels
        self.label_x = 'Time (Local time)'
        self.label_y = True

        # Actual Axes
        self.y_axis = y_axis
        self.y_2_axis = y_2_axis
        self.x_axis = x_axis

        # Whether we assume x-axis is timestamps, and cull based on settings
        self.cull_x_axis = True

        # Callback run at the beginning of each timer tick
        self.tick_callback = lambda:()
        
        # Setup axes if not provided
        if self.y_axis is None:
            self.y_axis = BetterAxisItem()
        if self.y_2_axis is None:
            self.y_2_axis = BetterAxisItem(orientation='right')
            self.y_2_axis.hide()
        if self.x_axis is None:
            self.x_axis = pg.DateAxisItem()

        # Make plot widget
        self.plot_widget = pg.PlotWidget(axisItems = {'bottom': self.x_axis, 'left': self.y_axis, 'right': self.y_2_axis})

        # Enable some default options
        # self.plot_widget.getPlotItem().ctrl.downsampleCheck.setChecked(True)
        vb = self.plot_widget.getPlotItem().vb
        vb.setMouseMode(vb.RectMode)

        # Legend for plot, if you set this before calling setup, you can override the legend
        self.legend = None
        self.font_size()

    def font_size(self, axis='x,y', tick_size=12, title_size=16, line_width=3):
        title_font = QtGui.QFont()
        tick_font = QtGui.QFont()
        tick_font.setPixelSize(tick_size)
        title_font.setPixelSize(title_size)
        self.line_width = line_width
        if 'x' in axis:
            self.x_axis.setTickFont(tick_font)
            self.x_axis.label.setFont(title_font)
            adjust_nudge(self.x_axis)
        if 'y' in axis:
            self.y_axis.setTickFont(tick_font)
            self.y_axis.label.setFont(title_font)
            self.y_2_axis.setTickFont(tick_font)
            self.y_2_axis.label.setFont(title_font)
            adjust_nudge(self.y_axis)
            adjust_nudge(self.y_2_axis)
        for plots in self.plots:
            for plot in plots:
                old_pen = plot.opts['pen']
                plot.setPen(color=old_pen.color(), width=line_width)

    def start(self):
        '''Starts a timer which we use for updating values'''
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.animate_fig)
        self._timer.start(self.settings.update_rate)

    def stop(self):
        '''Stops the timer if present'''
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def setup(self):
        '''Initialises the plot widget'''
        
        if self.legend is None:
            self.legend = self.plot_widget.addLegend()

        n = 0
        if len(self.keys) == 2:
            # twin the axes
            for (_,label,avg_label) in self.keys:
                raw_pen = pg.mkPen(plot_colours[n%4], width=self.line_width)
                data_raw = pg.PlotDataItem(pen=raw_pen,skipFiniteCheck=True,name=label)
                self.plots.append([data_raw])
                if n == 0:
                    self.plot_widget.getPlotItem().addItem(data_raw)
                    self.plot_widget.setLabel('left', label)
                else:
                    plot = self.plot_widget
                    plot.setLabel('right', label)
                    viewbox = pg.ViewBox()
                    plot.scene().addItem(viewbox)
                    plot.getAxis('right').linkToView(viewbox)
                    viewbox.setXLink(plot)
                    viewbox.addItem(data_raw)
                    self.legend.addItem(data_raw, label)

                    def updateViews():
                        viewbox.setGeometry(plot.getViewBox().sceneBoundingRect())
                        viewbox.linkedViewChanged(plot.getViewBox(), viewbox.XAxis)
                    updateViews()
                    plot.getViewBox().sigResized.connect(updateViews)

                n += 1
        else:
            for (_,label,avg_label) in self.keys:
                raw_pen = pg.mkPen(plot_colours[n%4], width=self.line_width)
                data_raw = pg.PlotDataItem(pen=raw_pen,skipFiniteCheck=True,name=label)
                self.plot_widget.getPlotItem().addItem(data_raw)
                self.plots.append([data_raw])
                if self.show_avg:
                    avg_pen = pg.mkPen(avgs_colours[n%4], width=self.line_width)
                    data_avg = pg.PlotDataItem(pen=avg_pen,skipFiniteCheck=True,name=avg_label)
                    self.plot_widget.getPlotItem().addItem(data_avg)
                    self.plots[-1].append(data_avg)
                n += 1
            plot = self.plot_widget
            plot.removeItem(self.y_2_axis)
            plot.getPlotItem().layout.removeItem(self.y_2_axis)
            self.y_2_axis.scene().removeItem(self.y_2_axis)
            self.y_2_axis.unlinkFromView()
        
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.plot_widget)
        self.layout().setContentsMargins(0,0,0,0)
        self.layout().setSpacing(0)

    def update_values(self):
        '''Updates the values from _plots, and marks if we did have anything change'''
        self._has_value = False
        try:
            for (key,_,_) in self.keys:
                if key not in __threads__:
                    run_plot_thread(key)
                    continue
                if key not in _plots:
                    continue
                __threads__[key][2] = time.time()
                times = _plots[key][0]
                if not self._has_value:
                    differs = times[-1] != self.last_stamp
                    self._has_value = differs
        except Exception as err:
            print(f'Error in update values: {err} {self.keys}')

    def get_data(self, key):
        return _plots[key]
    
    def set_axis_label(self, axis, label):
        if axis == 'x':
            axis = 'bottom'
        elif axis == 'y':
            axis = 'left'
        elif axis == 'y_2':
            axis = 'right'

        self.plot_widget.setLabel(axis, label)

    def set_plot_title(self, label):
        self.plot_widget.setTitle(label)

    def refresh_from_settings(self):
        if self.last_label != self.settings.axis_name \
        or self.y_axis.logMode != self.settings.log_scale \
        or self.y_axis.tick_fmt != self.settings.y_axis_fmt:
            self.y_axis.tick_fmt = self.settings.y_axis_fmt
            self.y_2_axis.tick_fmt = self.settings.y_axis_fmt
            self.plot_widget.getPlotItem().ctrl.logYCheck.setChecked(self.settings.log_scale)
            # self.y_axis.setLogMode(False, self.settings.log_scale)
            if self.label_y:
                self.set_axis_label('y', self.settings.axis_name)
            if self.label_x:
                self.set_axis_label('x', self.label_x)
            self.last_label = self.settings.axis_name
            self.plot_widget.updateLogMode()

    def animate_fig(self, *_):
        '''Primary animation loop'''

        self.tick_callback() # Start by running our callback, this can be used to update settings, etc

        # Check if we are paused, if so, skip
        if self.settings.paused:
            return
        # check if timer's rate has changed, and update accordingly
        if self._timer.interval() != self.settings.update_rate:
            self._timer.setInterval(self.settings.update_rate)
        # now get some new values
        self.update_values()

        # If not new, skip
        if not self._has_value:
            return
        
        # Update labels if they have changed
        self.refresh_from_settings()
        
        n = 0
        
        # Then finally update the plots
        for (key,_,_) in self.keys:
            plots = self.plots[n]
            n += 1

            [times, values, avgs, valid, rolled, *_] = self.get_data(key)

            # Skip any invalid plots
            if not valid:
                continue

            # Find values which are in appropriate range
            if self.cull_x_axis:
                end = times[-1] - self.settings.log_length * 3600.0
                max_end = len(times) - rolled - 1
                last = numpy.argwhere(times < end)
                if len(last) > 2:
                    self.start_index = last[-2][0]
                else:
                    self.start_index = 0
                self.start_index = max(self.start_index, max_end)
                times = times[self.start_index:]
            else:
                self.start_index = 0
            
            # If we do show average, then compute that next
            if self.show_avg:
                avgs = avgs[self.start_index:] * self.settings.scale
                avg = plots[1]
                avg.setData(times, avgs)

            # And finally get the plot and update it
            values = values[self.start_index:] * self.settings.scale
            raw = plots[0]
            raw.setData(times, values)

        # If we only have 1 thing to plot, set the plot title based on values of that thing
        if len(self.keys)==1 and len(values) > 1:
            label = self.settings.title_fmt.format(values[-1])
            self.set_plot_title(label)
