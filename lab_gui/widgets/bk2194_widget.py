import pyvisa
import struct
import numpy
import math
import time

from .device_widget import DeviceReader
from .plot_widget import Plot
from .base_control_widgets import ControlLine, LineEdit

from ..modules.module import BetterAxisItem

from ..utils.qt_helper import *

class BK2194(DeviceReader):
    '''A GW INSTEK GDS-1054B Four Channel Digital Storage Oscilloscope

    This uses pyserial to communicate with the device. 
    
    This presently displays the 4 channels for the scope. It is not yet set to save logs of the output though.
    '''
    def __init__(self, parent, addr, channels=[1, 2, 3, 4]):
        """_summary_

        Args:
            parent (FigureModule): the module we are made from
            addr (str): serial address of the scope
            channels (list, optional): channels to display. Defaults to [1, 2, 3, 4].
        """

        # Set this first as it is needed in super().__init__
        self.channels = channels

        super().__init__(parent, data_key=None, name=f"BK2194", axis_title=f"Signal (V)")

        self.plot_data = {key:[[],[],[], False, 0] for key in channels}
        self.raw_data = {key:[[],[[],[]]] for key in channels}

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
        self.plot_widget.settings.title_fmter = lambda x: ""

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
            print(self.device.query('*idn?'))
        except Exception as err:
            print(f"Error opening BK2194 {err}")
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
        inst = self.device
        # Below code taken from the BK2194 Programming Manual
        vdiv = inst.query(f"c{channel}:vdiv?").strip().replace(f"C{channel}:VDIV", "").replace("V", "")
        ofst = inst.query(f"c{channel}:ofst?").strip().replace(f"C{channel}:OFST", "").replace("V", "")
        tdiv = inst.query("tdiv?").strip().replace("TDIV ", "").replace("S", "")
        sara = inst.query("sara?").strip().replace("SARA ", "")
        inst.query("*opc?")
        sara_unit = {'G':1E9,'M':1E6,'k':1E3,'S':1e0}
        for unit in sara_unit.keys():
            if sara.find(unit)!=-1:
                sara = sara[0:sara.find(unit)]
                sara = float(sara)*sara_unit[unit]
                break
        sara = float(sara)
        inst.timeout = 30000 #default value is 2000(2s)
        inst.chunk_size = 20*1024*1024 #default value is 20*1024(20k bytes)
        inst.write("c1:wf? dat2")
        recv = list(inst.read_raw())[15:]
        recv.pop()
        recv.pop()
        volt_value = []
        for data in recv:
            if data > 127:
                data = data - 256
            volt_value.append(data)
        time_value = []
        vdiv = float(vdiv)
        ofst = float(ofst)
        tdiv = float(tdiv)
        for idx in range(0,len(volt_value)):
            volt_value[idx] = volt_value[idx]/25*vdiv-ofst
            time_data = -(tdiv*14/2)+idx*(1/sara)
            time_value.append(time_data)
        y = numpy.array(volt_value[7:])
        t = numpy.array(time_value[7:])
        inst.query("*opc?")

        return y, t