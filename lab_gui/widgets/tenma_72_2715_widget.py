import time
import serial

from .device_widget import DeviceReader
from .device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource
from .base_control_widgets import ControlButton, ControlLine, LineEdit, scale
from ..utils.qt_helper import *

# protocol found on https://www.farnell.com/datasheets/2578054.pdf
#
# This requires the 50ms sleeps between commands, otherwise bad things happen.
# Testing shows that a 45ms sleep may also suffice, but not a 40 or lower.
SLEEP_DUR = 0.05

class TENMA722715(DeviceReader, BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
    def __init__(self, parent, addr, data_keys=[None, None]):
        super().__init__(parent, data_key=data_keys[0], name=f"TENMA-72-2715", axis_title=f"Signal (V)")
        self.addr = addr
        self.channels = 1
        self.output = False
        self.mutex = False
        self.data_keys = data_keys

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

    def set_voltage(self, V):
        cmd = f'VSET1:{V:.2f}\n'.encode()
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)

    def set_current(self, I):
        cmd = f'ISET1:{I:.2f}\n'.encode()
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)

    def is_output_enabled(self):
        """This device is turned on by manual button, so this does nothing
        """
        return True
    
    def enable_output(self, output: bool):
        """This device is turned on by manual button, so this does nothing
        """
        return output

    def get_set_voltage(self):
        cmd = b'VSET1?'
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)
        return float(self.device.read_all().decode().strip())

    def get_set_current(self):
        cmd = b'ISET1?'
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)
        return float(self.device.read_all().decode().strip())

    def get_voltage(self):
        cmd = b'VOUT1?'
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)
        return float(self.device.read_all().decode().strip())

    def get_current(self):
        cmd = b'IOUT1?'
        self.device.write(cmd)
        time.sleep(SLEEP_DUR)
        return float(self.device.read_all().decode().strip())

    def is_output_enabled(self):
        """This device is turned on by manual button, so this does nothing

        Returns:
            bool: True, this is always on if present
        """
        return True

    def open_device(self):
        try:
            self.device = serial.Serial(self.addr)
            self.powerBtn.setChecked(self.is_output_enabled())
            self.powerBtn.isChecked()
            V = self.get_set_voltage()
            I = self.get_set_current()
            self.V_out.box.setText(f'{V:.2f}')
            self.I_out.box.setText(f'{I:.3f}')
            self.valid = True
        except Exception as err:
            print(err)
            print('error opening PPS 2116A?')
            self.device = None
        return self.device != None

    def close_device(self):
        if self.device is None:
            return
        self.device.close()

    def read_device(self):

        if self.device is None:
            return False, 0
        
        self.is_output_enabled()
        V = self.get_voltage()
        if self.data_keys[1] != None:
            I = self.get_current()
            self.client.set_float(self.data_keys[1], I)

        return True, V