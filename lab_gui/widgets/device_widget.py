import threading
import time
import numpy
import os

#  * import due to just being things from Qt
from ..utils.qt_helper import *

from ..widgets.base_control_widgets import SubControlWidget, FrameDock, StateSaver, addCrossHairs
from .device_types.devices import BaseDevice
from ..widgets.plot_widget import Plot, smooth_average

# Change this if you want to change how many points are kept in memory.
_max_points = 1e5

class DeviceController(SubControlWidget, BaseDevice):
    """
    Generic Device Controller template. This provides a thread to access the device on, as well as stub functions
    for opening and closing the device.
    """
    def __init__(self, parent, name="???", **args):

        self.parent = parent
        # Set this first so that we have a name before the makeFrame in super().__init__
        self.name = name

        super().__init__(**args)

        self.client = parent.data_client
            
        self.ended = False
        self._alive_ = False
        self.device = None     # device object we are handling
        self.reboot_time = 25  # Time to reboot if device update errors

        self.made_thread = False

        self.paused = True
        self.active_button = QCheckBox("Enabled")
        self.active_button.setChecked(True)
        self.active_button.clicked.connect(self.toggle_paused)

        self._layout = QHBoxLayout()
        self._layout.setSpacing(0)
        self._layout.addWidget(self.active_button)

        self.frame.setLayout(self._layout)

        self.cmd_queue = []

    def makeFrame(self, menu_fn=None, help_fn=None, make_dock=True):
        super().makeFrame(menu_fn, help_fn, make_dock)
        self.dock.label.setText(self.name)

    def collect_saved_values(self, values):
        """Add values to the array to save, implementers should call super().collect_saved_values(values)"""
        values["enabled"] = self.active_button
    
    def process_load_saved(self):
        """Process the loaded saved values, implementers should call super().process_load_saved()"""
        self.toggle_paused()

    def do_device_update(self):
        """
        This is called to loop access the device. If this throws an error, the device will be closed,
        and then re-opened after a delay of self.reboot_time
        """
        pass

    def queue_cmd(self, callable):
        """queues a callable to run on the device thread. this is intended for use with buttons, etc.

        The functions are run before do_device_update, and are each wrapped in a try-except block
        
        Args:
            callable (function): Function to run
        """
        self.cmd_queue.append(callable)

    def toggle_paused(self):
        """Toggles whether we are paused. When paused, we release control of the device, ie close_device is called."""
        self.paused = not self.active_button.isChecked()
        self.saver.on_changed(self.active_button)

    def open_settings(self):
        """Makes the button for showing the plotter's options"""
        key = self.name
        callback = self.settings._callback
        def _cb():
            if callback is not None:
                callback()
            self.saver.on_changed(self.settings)
        self.parent._root.edit_options(self.dock, self.settings, key, _cb)

    def pre_loop_start(self):
        """Called on the device access thread before entering the main loop.
        
        This loads the saved values before handling any device calls, to ensure things
        are still in the same state as when the program was closed. If you want to reset a state
        then delete the file for the device in the settings folder."""
        values = {}
        self.collect_saved_values(values)
        self.saver = StateSaver(self.name, values)
        self.process_load_saved()

    def run_loop(self):
        """The content of the device access thread."""
        self._alive_ = True

        # Handle processing any possibly saved values/states
        self.pre_loop_start()
        
        is_open = False

        def wait_to_reset():
            start = time.time()
            # Delay by self.reboot_time in this case to give things time to possibly re-initialise
            while time.time() - self.reboot_time < start and not self.ended:
                time.sleep(0.01)

        while not self.ended:
            if self.paused:
                if is_open:
                    try:
                        self.close_device()
                    except Exception as err:
                        print(f"Error while trying to close {self.name}")
                        print(err)
                    is_open = False
                # ms sleep to not peg core
                time.sleep(0.001)
                continue

            # Open the device if needed
            if not is_open:
                is_open = self.open_device()
                if not is_open:
                    # Delay by self.reboot_time in this case to give things time to possibly re-initialise
                    wait_to_reset()

            # Try to access the device, and close it if it fails.
            try:
                try:
                    while len(self.cmd_queue):
                        # pop the element and then call it
                        self.cmd_queue.pop()()
                except Exception as err:
                    print("Error running a queued command!")
                    print(err)
                self.do_device_update()
            except Exception as err:
                print(f"Error while trying to access {self.name}")
                print(err)
                # Try to close the device, chances are this will error as well
                try:
                    self.close_device()
                except Exception:
                    pass
                # Delay by self.reboot_time in this case to give things time to possibly re-initialise
                wait_to_reset()
                # Mark as not open so we re-open next loop
                is_open = False
        
        if is_open:
            try:
                self.close_device()
            except Exception as err:
                print(f"Error while trying to close {self.name}")
                print(err)
        self._alive_ = False
    
    def on_update(self):
        # Here we start the thread, doing it here ensures we had time to otherwise init.
        if not self.made_thread:
            self.run_thread = threading.Thread(target=self.run_loop, daemon=True,name=f"Controlling {self.name}")
            self.run_thread.start()
            self.made_thread = True
        return super().on_update()

    def close(self):
        super().close()
        self.ended = True
        while self._alive_:
            # ms sleep to not peg core
            time.sleep(0.001)
        self.run_thread = None
        self.saver.close()

class DeviceReader(DeviceController):
    """
    A DeviceReader is a widget which handles communicating with and reading simple float values from a Device.
    It provides a GUI with a button to enable/disable the reading, as well as a plot of the value read.

    Device Reading it handled on a separate thread. Example implementations:

    ke617_widget: reading a GPIB device via pyvisa, also adds some extra controls
    sm7110_widget: reading a serial device via pyserial
"""
    def __init__(self, parent, data_key=None, name="???", has_plot = True, axis_title="???", plot_title="???", **args):
        super().__init__(parent, name, menu_fn=self.open_settings, **args)

        self.log_file_name = None
        self.value = 0
        self.valid = False

        # If set to true, we will not manage logging from the log_button. This also affects whether the value goes to the data_client
        self.custom_logging = False

        # Pre-populate array with the start values
        self.times = numpy.full(int(_max_points), time.time())
        self.values = numpy.full(int(_max_points), self.value)
        self.avgs = numpy.full(int(_max_points), self.value)

        self.do_log = True
        self.do_log_O = False
        self.log_button = QCheckBox("Log Values")
        self.log_button.setChecked(True)
        self.log_button.clicked.connect(self.toggle_log)

        self.has_plot = has_plot
        if has_plot:
            self.make_plot()
            self.settings = self.plot_widget.settings
            self.settings.y_axis_fmt = '{:.3f}'
            if plot_title != '???':
                self.settings.title_fmt = plot_title
            self.settings.axis_name = axis_title

            self.plot_data = [self.times, self.values, self.avgs, False, 0]

            self.plot_update_backup = self.plot_widget.update_values
            self.plot_get_data_backup = self.plot_widget.get_data

            self.set_data_key(data_key)

            self.plot_widget.setup()
            self.plot_widget.start()

            self.plot_dock = FrameDock(widget=self.plot_widget,menu_fn=self.open_settings,help_fn=None)
            self.plot_dock.label.setText(name)

        self.full_layout = QVBoxLayout()
        self._layout = QHBoxLayout()
        self._layout.setSpacing(0)
        self._layout.addWidget(self.active_button)
        self._layout.addWidget(self.log_button)

        self.makeFrame(menu_fn=self.open_settings)
        self.frame.setLayout(self.full_layout)
        self.full_layout.addLayout(self._layout)
        if has_plot:
            self.full_layout.addWidget(self.plot_widget)
            self.full_layout.addWidget(addCrossHairs(self.plot_widget.plot_widget))

    def make_plot(self):
        """This makes the plot_widget, implementers can add custom arguments to their plot, etc by replacing this function
        """
        self.plot_widget = Plot()

    def set_data_key(self, data_key):
        """
        Initialises the various settings for the plot
        """
        self.data_key = data_key
        
        if not self.has_plot:
            return

        if 'reload_hours' in self.settings._names_:
            del self.settings._names_['reload_hours']

        self.settings._options_ = {}

        def key_updated(*_):
            chosen = self.settings._entries_['source_key'].text().strip()
            if chosen == "":
                self.settings.source_key = None
                self.plot_widget._has_value = True
                self.plot_widget.update_values = lambda*_:_
                self.plot_widget.get_data = self.get_data
            else:
                self.settings.source_key = data_key
                self.plot_widget.update_values = self.plot_update_backup
                self.plot_widget.get_data = self.plot_get_data_backup
            self.data_key = self.settings.source_key
            self.plot_widget.keys = [["???" if data_key is None else data_key, "Raw Value", "Smoothed"]]

        if data_key is None:
            self.plot_widget._has_value = True
            self.plot_widget.update_values = lambda*_:_
            self.plot_widget.get_data = self.get_data
        else:
            self.settings._options_callbacks_['source_key'] = key_updated
            self.plot_widget.update_values = self.plot_update_backup
            self.plot_widget.get_data = self.plot_get_data_backup
        
        self.settings.source_key = data_key
        self.plot_widget.keys = [["???" if data_key is None else data_key, "Raw Value", "Smoothed"]]

    def collect_saved_values(self, values):
        """Add values to the array to save, implementers should call super().collect_saved_values(values)"""
        values["log_output"] = self.log_button
        values["plot_settings"] = self.settings
        super().collect_saved_values(values)
    
    def process_load_saved(self):
        """Process the loaded saved values, implementers should call super().process_load_saved()"""
        self.toggle_log()
        self.do_log_0 = not self.do_log
        self.set_data_key(self.settings.source_key)
        super().process_load_saved()

    def make_file_header(self):
        """Makes the header section of the log file"""
        return "Local Time\tValue Read\n"
    
    def format_values_for_print(self, timestamp, value):
        """Makes an entry line of the log file, timestamp is local unix time"""
        return f"{timestamp}\t{value}\n"

    def toggle_log(self):
        """Toggles log output of data, when this is enabled, a new logfile will be created"""
        self.do_log = self.log_button.isChecked()
        self.saver.on_changed(self.log_button)

    def get_log_file(self, value_name, init_dir=True):
        """Makes a new logfile to run with, here you can change the directory, etc"""
        log_dir = self.saver.value_map["log_directory"]
        log_dir = f'{log_dir}/{self.name}/{time.strftime("%Y-%m-%d")}'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file_name = f'{log_dir}/{value_name}_{time.strftime("%H_%M_%S")}.log'
        return log_file_name
    
    def make_log_file(self):
        name = self.name if self.data_key is None else self.data_key
        self.data_key_O = self.data_key
        self.log_file_name = self.get_log_file(name)
        with open(self.log_file_name, 'w') as file:
            file.write(self.make_file_header())
        
    def get_data(self, *_):
        """Returns the data for the plotter to plot"""
        return self.plot_data

    def read_device(self):
        """
        Reads the device and returns a tuple of (value, reading), where reading is a float.

        If this does not handle any exceptions thrown, the device will be closed and re-opened.
        """
        return False, 2e30

    def do_device_update(self):
        self.valid, self.value = self.read_device()
        if self.valid:
            timestamp = time.time()
            if self.has_plot:
                times = self.plot_data[0]
                values = self.plot_data[1]
                avgs = self.plot_data[2]
                existing = self.plot_data[3]
                plots = self.plot_data

                if not existing: # First time we back-fill the arrays with initial value
                    times = numpy.full(int(_max_points), timestamp)
                    values = numpy.full(int(_max_points), self.value)
                    avgs = smooth_average(values)
                    plots[3] = True
                    plots[4] = 0 # clear rolled status
                else: # Otherwise we roll back the arrays, and append the new value to the end
                    times = numpy.roll(times,-1)
                    times[-1] = timestamp
                    values = numpy.roll(values,-1)
                    avgs = numpy.roll(avgs,-1)
                    values[-1] = self.value
                    plots[4] = plots[4] + 1 # Increment rolled status
                # Finally update the arrays
                avgs[-100:] = smooth_average(values[-200:])[-100:]
                plots[0] = times
                plots[1] = values
                plots[2] = avgs

            if not self.custom_logging:
                if self.do_log != self.do_log_O or self.data_key != self.data_key_O:
                    if self.do_log and self.name != "???":
                        self.make_log_file()
                    else:
                        self.do_log = False
                    self.do_log_O = self.do_log
                if self.data_key is not None:
                    self.client.set_float(self.data_key, self.value)
                if self.do_log:
                    with open(self.log_file_name, 'a') as file:
                        file.write(self.format_values_for_print(timestamp, self.value))