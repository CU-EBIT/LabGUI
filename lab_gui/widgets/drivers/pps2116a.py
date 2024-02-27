import time

from ..device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource
from ..device_types.pyserial_devices import PySerialDevice

# Based on https://github.com/circuit-specialists/PowerSupply_ElectronicLoad_Control/blob/master/PowerSupplies/pps2116a.py

SLEEP_DUR = 0.02

class PPS2116A(PySerialDevice, BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
    def __init__(self, addr) -> None:
        super().__init__(addr)
        self.query_delay = SLEEP_DUR

    def is_output_enabled(self):
        resp = self.query('rs')
        if resp == '0000':
            output = False
        elif resp == '0016' or resp == '0001':
            # b'0016\n' seems to be on and C.C
            # b'0001\n' seems to be on and C.V
            output = True
        else:
            output = True
            print(f"New status?? {resp}")
        return output

    def set_voltage(self, V):
        V *= 100
        V = int(V)
        self.query(f'su{V:04d}')

    def set_current(self, I):
        I *= 1000
        I = int(I)
        self.query(f'si{I:04d}')

    def enable_output(self, state):
        if(state):
            self.turnON()
        else:
            self.turnOFF()
        return state

    def turnON(self):
        self.query('o1')

    def turnOFF(self):
        self.query('o0')

    def get_voltage(self):
        voltage = self.query('rv')
        voltage = float(voltage) / 100.0
        return voltage

    def get_current(self):
        amperage = self.query('ra')
        amperage = float(amperage) / 1000.0
        return amperage
    
    def get_set_voltage(self):
        voltage = self.query('ru')
        voltage = float(voltage) / 100.0
        return voltage

    def get_set_current(self):
        amperage = self.query('ri')
        amperage = float(amperage) / 1000.0
        return amperage