import pyvisa
import struct
import numpy

from .device_widget import DeviceReader
from .plot_widget import Plot

from ..modules.module import BetterAxisItem

class MSO2012(DeviceReader):
    '''A Tektronix MSO 2012 Mixed Signal Oscilloscope

    This uses pyvisa to communicate with the device. 
    
    If the scales are changed manually on the scope, you need to toggle the enabled button to reload it here. 
    The time to look those up is as long as to get an entire reading...
    
    This presently displays the 2 channels for the scope. It is not yet set to save logs of the output though.
    '''
    def __init__(self, parent, addr, channels=['ch1', 'ch2']):
        """_summary_

        Args:
            parent (FigureModule): the module we are made from
            addr (str): pyvisa address of the scope
            channels (list, optional): channels to display. Defaults to ['ch1', 'ch2'].
        """

        # Set this first as it is needed in super().__init__
        self.channels = channels

        super().__init__(parent, data_key=None, name=f"MSO2012", axis_title=f"Signal (V)")

        self.plot_data = {key:[[], [], [], False, 0] for key in channels}

        self.addr = addr
        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        self.times = None
        self.values = None
        self.avgs = None

    def make_plot(self):
        self.plot_widget = Plot(x_axis=BetterAxisItem('bottom'))
        self.plot_widget.cull_x_axis = False
        self.plot_widget.show_avg = False
        self.plot_widget.label_x = "Time (μs)"

    def set_data_key(self, _):

        if 'reload_hours' in self.settings._names_:
            del self.settings._names_['reload_hours']

        self.settings._options_ = {}

        self.plot_widget._has_value = True
        self.plot_widget.update_values = lambda*_:_
        self.plot_widget.get_data = self.get_data

        self.plot_widget.keys = [[channel, channel, ""] for channel in self.channels]

    def make_file_header(self):
        # Adjust the header to indicate ???
        return "Local Time\tValue (???)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We "read" only every 50ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        # We don't actually have a device, so we pretend to open something
        try:
            rm = pyvisa.ResourceManager()
            self.device = rm.open_resource(self.addr)
            self.device.timeout = 2000

            # Setup block
            self.device.write('data:resolution reduced') # full resolution data output
            self.device.write('data:composition singular_yt')
            self.device.write('data:width 2')
            self.device.write('data:enc RIB')

            self.x = {}
            self.y = {}

            for channel in self.channels:
                self.device.write(f'data:source {channel}')
                # The below lines take 300-500ms to run, so only do it rarely
                self.x[channel] = float(self.device.query('wfmoutpre:xincr?'))
                self.y[channel] = float(self.device.query('wfmoutpre:ymult?'))
                
            self.device.query('*OPC?') # block until data is present (supposedly, more manual delays to be safe)
        except Exception as err:
            print(f"Error opening MSO2012 {err}")
            self.device = None
        return self.device != None

    def get_data(self, key, *_):
        """Returns the data for the plotter to plot"""
        return self.plot_data[key]

    def do_device_update(self):
        for channel in self.channels:
            vars, times = self.acquire(channel)
            plots = self.plot_data[channel]
            plots[0] = times
            plots[1] = vars
            plots[2] = vars
            plots[3] = True

    def close_device(self):
        if self.device is None:
            return
        self.device.close()

    def acquire(self, channel):
        
        self.device.write(f'data:source {channel}')
        self.device.write('curv?')
        vars = self.device.read_raw()
        digits = int(vars[1:2])
        vars = vars[digits+3:]
        vars = struct.unpack(f'{int(len(vars) / 2)}h',vars)
        vars = numpy.array(vars) * self.y[channel]
        s = self.x[channel] * len(vars) * 1e6
        times = numpy.linspace(-s/2, s/2, num=len(vars))
        return vars[0:-1], times[0:-1]