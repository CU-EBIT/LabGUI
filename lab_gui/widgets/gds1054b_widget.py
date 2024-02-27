import serial
import struct
import numpy
import math
import time

from .device_widget import DeviceReader
from .plot_widget import Plot
from .base_control_widgets import ControlLine, LineEdit

from ..modules.module import BetterAxisItem

from ..utils.qt_helper import *

class GDS1054B(DeviceReader):
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
        self.numbered = {}
        n = 0
        for channel in channels:
            self.numbered[channel] = n
            n += 1

        super().__init__(parent, data_key=None, name=f"GDS1054B", axis_title=f"Signal (V)")

        self.plot_data = {key:[[0], [0], [0], False, 0] for key in channels}

        self.addr = addr
        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        self.times = None
        self.values = None
        self.avgs = None

        # Add some controls
        
        # Time domain controls
        time_outer = QVBoxLayout()
        time_outer.setSpacing(0)
        time_layout = QHBoxLayout()
        time_layout.setSpacing(0)

        def update_time_scale(*_):
            value = self.time_scale_line.get_value()
            def do_update():
                self.device.write(f'horizontal:main:scale {value}\n'.encode())
            self.queue_cmd(do_update)

        def one_two_five(old, new, values=[1.0, 2.0, 5.0]):
            # Probably a better way to do this, can be fixed later.
            old_str = f'{old:.3e}'
            oom = math.floor(math.log10(old))
            if old < new:
                if old_str.startswith("1"):
                    new = values[1]
                elif old_str.startswith("2"):
                    new = values[2]
                elif old_str.startswith("5"):
                    new = values[0]
                    oom += 1
                else:
                    new = values[0]
                new = new*10**oom
            elif old > new:
                if old_str.startswith("1"):
                    new = values[2]
                    oom -= 1
                elif old_str.startswith("2"):
                    new = values[0]
                elif old_str.startswith("5"):
                    new = values[1]
                else:
                    new = values[0]
                new = new*10**oom
            return new

        self.time_scale_line = ControlLine(lambda:(), LineEdit("1.0e-04"), "{:.1e}", 5e-9, 5e1)
        self.time_scale_line.adjust_number = one_two_five
        self.time_scale_line.box.setFixedWidth(50)
        time_layout.addWidget(self.time_scale_line.box)
        applyBtn = QPushButton("Apply")
        applyBtn.clicked.connect(update_time_scale)
        time_layout.addWidget(applyBtn)
        time_layout.addStretch(0)

        time_outer.addWidget(QLabel("Time Range Control"))
        time_outer.addLayout(time_layout)
        
        self._layout.addLayout(time_outer)

        # Channel Controls
        self.scale_box = {}

        def addChannelCtrl(channel):
            outer = QVBoxLayout()
            outer.setSpacing(0)

            layout = QHBoxLayout()
            layout.setSpacing(0)

            def values(old, new):
                return one_two_five(old, new, values=[1,2,5])
            
            def update_channel(*_):
                value = self.scale_box[channel].get_value()
                def do_update():
                    self.device.write(f':channel{channel}:scale {value}\n'.encode())
                self.queue_cmd(do_update)

            scale_line = ControlLine(lambda:(), LineEdit("5.0e+00"), "{:.1e}", 2e-3, 5)
            self.scale_box[channel] = scale_line
            scale_line.adjust_number = values

            scale_line.box.setFixedWidth(50)
            layout.addWidget(scale_line.box)
            applyBtn = QPushButton("Apply")
            applyBtn.clicked.connect(update_channel)
            layout.addWidget(applyBtn)
            layout.addStretch(0)

            outer.addWidget(QLabel(f"CH{channel} Control"))
            outer.addLayout(layout)
            self._layout.addLayout(outer)
        
        for channel in channels:
            addChannelCtrl(channel)

    def make_plot(self):
        self.plot_widget = Plot(x_axis=BetterAxisItem('bottom'))
        self.plot_widget.cull_x_axis = False
        self.plot_widget.show_avg = False
        self.plot_widget.label_x = "Time (s)"

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
            def query(cmd):
                self.device.write(f'{cmd}\n'.encode())
                return self.device.readline()

            self.device = serial.Serial(self.addr,baudrate=38400)
            while self.device.in_waiting:
                self.device.read_all()
            self.device.query = query
            print(self.device.query("*idn?"))
            
            for channel in self.channels:
                scale = float(self.device.query(f'channel{channel}:scale?'))
                self.scale_box[channel].box.setText(f"{scale:.1e}")

        except Exception as err:
            print(f"Error opening MSO2012 {err}")
            self.device = None
        return self.device != None

    def get_data(self, key, *_):
        """Returns the data for the plotter to plot"""
        return self.plot_data[key]

    def do_device_update(self):
        for channel in self.channels:
            try:
                vars, times = self.acquire(channel)
            except Exception as err:
                print(f"Error reading {channel}")
                raise err
            if vars is None:
                continue
            plots = self.plot_data[channel]
            plots[0] = times
            plots[1] = vars
            plots[2] = vars
            plots[3] = True
        time.sleep(0.05)

    def close_device(self):
        if self.device is None:
            return
        self.device.close()

    def acquire(self, channel):

        curves = self.plot_widget.plot_widget.getPlotItem().curves
        curve = curves[self.numbered[channel]]
        if not curve.isVisible():
            return None, None
        dev = self.device

        while dev.in_waiting:
            dev.read_all()

        resp = dev.query(f':ACQ{channel}:STAT?').decode().strip()
        if resp != '1':
            return None, None
        
        dev.write(f':ACQ{channel}:MEM?\n'.encode())
        while dev.in_waiting < 1000:
            time.sleep(0.001)
        buf = dev.read_all()

        header = b''
        data_size = 0
        data_start = 0
        for i in range(len(buf)):
            if buf[i] == b'\n'[0]:
                data_start = i + 1
                break
        header = buf[:data_start - 1].decode().split(";")
        buf = buf[data_start:]
        params = {}
        for value in header:
            if not ',' in value:
                continue
            split = value.split(',')
            params[split[0]] = split[1]
        data_size = int(header[1].split(',')[1])

        pound = buf[0]
        if pound != b'#'[0]:
            print("Not correct char!")
        n_header = int(buf[1:2].decode())
        scale = float(params['Vertical Scale'])
        x = float(params['Horizontal Scale'])
        
        skip = 2 + n_header
        expected_buf_size = 2*data_size + skip + 1
        n = 0
        
        while expected_buf_size != len(buf):
            buf = buf + dev.read_all()
            time.sleep(0.005)
            n += 1
            if n > 20:
                while dev.in_waiting:
                    dev.read_all()
                return None, None
        data = buf[skip:-1]
        data = struct.unpack(f'{data_size}h',data)
        data = scale * numpy.array(data, dtype='float64') / (25.0 * 256.0)
        s = x * len(data)
        times = numpy.linspace(-s/2, s/2, num=len(data))
        
        return data, times