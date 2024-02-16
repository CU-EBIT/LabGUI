import time
import serial

from .device_widget import DeviceReader
from .base_control_widgets import ControlButton, ControlLine, LineEdit, scale
from ..utils.qt_helper import *

# Based on https://github.com/circuit-specialists/PowerSupply_ElectronicLoad_Control/blob/master/PowerSupplies/pps2116a.py

class PPS2116A(DeviceReader):
    def __init__(self, parent, addr, data_keys=[None, None]):
        super().__init__(parent, data_key=data_keys[0], name=f"PPS2116A", axis_title=f"Signal (V)")
        self.addr = addr
        self.channels = 1
        self.output = False
        self.mutex = False
        self.data_keys = data_keys

        outer = QVBoxLayout()
        outer.setSpacing(0)

        self.powerBtn = ControlButton(toggle=self.toggleOutput)
        self.powerBtn.setFixedWidth(125)
        outer.addWidget(self.powerBtn)
        self._modules.append(self.powerBtn)

        layout = QHBoxLayout()
        layout.setSpacing(0)

        def update_current(*_):
            value = self.I_out.get_value()
            def do_update():
                self.set_I(value)
            self.queue_cmd(do_update)
        def update_voltage(*_):
            value = self.V_out.get_value()
            def do_update():
                self.set_V(value)
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

    def lock(self):
        while(self.mutex):
            pass
        self.mutex = True

    def unlock(self):
        while(not self.mutex):
            pass
        self.mutex = False

    def getChannels(self):
        return self.channels

    def getOutput(self):
        self.lock()
        self.key = f'rs\n'
        resp = self.writeFunction()
        if resp == b'0000\n':
            self.output = False
        elif resp == b'0016\n' or resp == b'0001\n':
            # b'0016\n' seems to be on and C.C
            # b'0001\n' seems to be on and C.V
            self.output = True
        else:
            self.output = True
            print(f"New status?? {resp}")
        self.unlock()
        return self.output

    def set_V(self, V):
        V *= 100
        V = int(V)
        self.lock()
        self.key = f'su{V:04d}\n'
        self.writeFunction()
        self.unlock()

    def set_I(self, I):
        I *= 1000
        I = int(I)
        self.lock()
        self.key = f'si{I:04d}\n'
        self.writeFunction()
        self.unlock()

    def writeFunction(self):
        self.device.write(self.key.encode())
        time.sleep(.02)
        return self.device.read_all()

    def toggleOutput(self):
        state = not self.getOutput()
        self.setOutput(state)

    def setOutput(self, state):
        self.output = state
        if(state):
            self.turnON()
        else:
            self.turnOFF()

    def turnON(self):
        self.lock()
        self.key = "o1\n"
        self.writeFunction()
        self.unlock()

    def turnOFF(self):
        self.lock()
        self.key = "o0\n"
        self.writeFunction()
        self.unlock()

    def measureVoltage(self):
        self.lock()
        self.key = "rv\n"
        self.voltage = self.writeFunction().decode()
        self.voltage = float(self.voltage) / 100.0
        self.unlock()
        return self.voltage

    def measureAmperage(self):
        self.lock()
        self.key = "ra\n"
        self.amperage = self.writeFunction().decode()
        self.amperage = float(self.amperage) / 1000.0
        self.unlock()
        return self.amperage
    
    def presetVoltage(self):
        self.lock()
        self.key = "ru\n"
        voltage = self.writeFunction().decode()
        voltage = float(voltage) / 100.0
        self.unlock()
        return voltage

    def presetCurrent(self):
        self.lock()
        self.key = "ri\n"
        amperage = self.writeFunction().decode()
        amperage = float(amperage) / 1000.0
        self.unlock()
        return amperage

    def open_device(self):
        try:
            self.device = serial.Serial(self.addr)
            self.powerBtn.setChecked(self.getOutput())
            self.powerBtn.isChecked()

            self.V_out.box.setText(f'{self.presetVoltage():.2f}')
            self.I_out.box.setText(f'{self.presetCurrent():.3f}')

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
        
        self.getOutput()
        V = self.measureVoltage()
        if self.data_keys[1] != None:
            I = self.measureAmperage()
            self.client.set_float(self.data_keys[1], I)

        return True, V