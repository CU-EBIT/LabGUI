from .device_widget import DeviceReader
from .drivers.pps2116a import PPS2116A as Driver
from .device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource, copy_driver_methods
from .base_control_widgets import ControlButton, ControlLine, LineEdit, scale
from ..utils.qt_helper import *

class PPS2116A(DeviceReader, BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
    def __init__(self, parent, addr, data_keys=[None, None]):
        super().__init__(parent, data_key=data_keys[0], name=f"PPS2116A", axis_title=f"Signal (V)")
        
        self.data_keys = data_keys

        self.device = Driver(addr)

        outer = QVBoxLayout()
        outer.setSpacing(0)

        self.powerBtn = ControlButton(toggle=self.toggle_output)
        self.powerBtn.setFixedWidth(125)
        outer.addWidget(self.powerBtn)
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

        self.V_out = ControlLine(update_voltage, LineEdit("15.00"), "{:.2f}", 0, 32)
        self.I_out = ControlLine(update_current, LineEdit("0.000"), "{:.3f}", 0, 5)

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

        copy_driver_methods(self.device, self)
        
    def on_init(self):
        return super().on_init()

    def open_device(self):
        opened = self.device.open_device()
        self.valid = opened
        if not opened:
            return False
        try:
            self.powerBtn.setChecked(self.is_output_enabled())
            self.powerBtn.isChecked()
            self.V_out.box.setText(f'{self.get_set_voltage():.2f}')
            self.I_out.box.setText(f'{self.get_set_current():.3f}')
        except Exception as err:
            print(err)
            print('error opening PPS 2116A?')
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
        if self.data_keys[1] != None:
            I = self.get_current()
            self.client.set_float(self.data_keys[1], I)

        return True, V