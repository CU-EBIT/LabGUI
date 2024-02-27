
import numpy
from datetime import datetime
import time

from .device_widget import DeviceReader, _max_points
from .device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource, copy_driver_methods
from .base_control_widgets import ControlButton, ControlLine, LineEdit, scale
from .plot_widget import Plot, roll_plot_values

from ..utils.qt_helper import *

class BasicPowerSupply(DeviceReader, BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
    def __init__(self, parent, device, name, data_keys=[None, None], v_range=[0,10], i_range=[0,10]):
        self.data_keys = data_keys
        self.data_key=data_keys[0]
        super().__init__(parent, data_key=data_keys[0], name=name)

        self.data_keys = data_keys
        self.device = device

        outer = QVBoxLayout()
        outer.setSpacing(0)

        self.output_enabled = False
        def toggle():
            self.output_enabled = self.toggle_output()
        self.powerBtn = ControlButton(toggle=toggle, key="power_button", data_source=self)
        self.powerBtn.setFixedWidth(125)
        outer.addWidget(self.powerBtn)
        # Mark it for updating
        self._modules.append(self.powerBtn)

        layout = QHBoxLayout()
        layout.setSpacing(0)

        def update_current(*_):
            value = self.I_out.get_value()
            def do_update():
                self.set_current(value)
            self.queue_cmd(do_update)
        def update_voltage(*_):
            value = self.V_out.get_value()
            def do_update():
                self.set_voltage(value)
            self.queue_cmd(do_update)

        self.V_out = ControlLine(update_voltage, LineEdit("0.00"), "{:.2f}", *v_range)
        self.I_out = ControlLine(update_current, LineEdit("0.000"), "{:.3f}", *i_range)

        self.V_read = (datetime.now(), 0)
        self.I_read = (datetime.now(), 0)

        self.V_out.box.setFixedWidth(50)
        self.I_out.box.setFixedWidth(50)

        layout.addWidget(self.V_out.box)
        layout.addWidget(QLabel(" V "))
        layout.addWidget(self.I_out.box)
        layout.addWidget(QLabel(" A"))
        layout.addStretch(0)

        outer.addLayout(layout)
        self._frame = QFrame()
        self._frame.setLineWidth(2)
        self._frame.setFrameShape(QFrame.Shape.WinPanel)
        self._frame.setFrameShadow(QFrame.Shadow.Sunken)
        self._frame.setContentsMargins(2,2,2,2)
        self._frame.setLayout(outer)
        self._layout.addWidget(self._frame)
        w = 140
        h = 60

        w *= scale(self.get_dpi())
        self._frame.setFixedWidth(int(w))
        h *= scale(self.get_dpi())
        self._frame.setFixedHeight(int(h))

        self._layout.addStretch(0)
        
        times = numpy.full(int(_max_points), time.time())
        values = numpy.full(int(_max_points), self.value)
        avgs = numpy.full(int(_max_points), self.value)
        self.i_plot_data = [times, values, avgs, False, 0]

        # This copies the functions from the device to self, we now adjust toggle output to include our tracker
        copy_driver_methods(self.device, self)

    def make_plot(self):
        self.plot_widget = Plot()
        self.plot_widget.show_avg = False
        self.plot_widget.label_x = "Time (s)"

    def set_data_key(self, _):

        if 'reload_hours' in self.settings._names_:
            del self.settings._names_['reload_hours']

        self.settings._options_ = {}

        self.plot_widget._has_value = True
        self.plot_widget.update_values = lambda*_:_
        self.plot_widget.get_data = self.get_data

        self.plot_widget.keys = [[channel, "", ""] for channel in self.data_keys]
        self.plot_widget.keys[0][1] = "Voltage (V)"
        self.plot_widget.keys[1][1] = "Current (A)"

    def get_data(self, key, *_):
        """Returns the data for the plotter to plot"""
        return self.i_plot_data if key == self.data_keys[1] else self.plot_data

    def get_value(self, key):
        if key == self.data_key[0]:
            return self.V_read
        if key == self.data_key[1]:
            return self.I_read
        if key == "power_button":
            return datetime.now(), self.output_enabled
        
    def set_value(self, *_):
        """We do nothing here, but we have the function so we act as a "data_source" for the ControlButton
        """
        return

    def open_device(self):
        opened = self.device.open_device()
        self.valid = opened
        if not opened:
            return False
        try:
            self.powerBtn.setChecked(self.is_output_enabled())
            self.output_enabled = self.powerBtn.isChecked()
            V = self.get_set_voltage()
            I = self.get_set_current()
            self.V_out.box.setText(f'{V:.2f}')
            self.I_out.box.setText(f'{I:.3f}')
            self.valid = True
        except Exception as err:
            print(err)
            print(f'error opening {self.name}?')
            self.valid = False
        return self.valid

    def close_device(self):
        self.device.close_device()
        self.valid = False

    def read_device(self):

        if not self.valid:
            return False, 0
        
        self.is_output_enabled()

        V = self.get_voltage()
        I = self.get_current()
        
        self.V_read = (datetime.now(), V)
        self.I_read = (datetime.now(), I)

        timestamp = time.time()
        if self.has_plot:
            plots = self.i_plot_data
            roll_plot_values(plots, I, timestamp)

        if self.data_keys[1] != None:
            self.client.set_float(self.data_keys[1], I)

        return True, V