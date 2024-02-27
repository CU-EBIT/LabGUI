import time

from ..device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource
from ..device_types.pyserial_devices import PySerialDevice

# protocol found on https://www.farnell.com/datasheets/2578054.pdf
#
# This requires the 50ms sleeps between commands, otherwise bad things happen.
# Testing shows that a 45ms sleep may also suffice, but not a 40 or lower.
SLEEP_DUR = 0.05

class TENMA722715(PySerialDevice, BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
    def __init__(self, addr) -> None:
        super().__init__(addr)
        self.query_delay = SLEEP_DUR
    
    def set_voltage(self, V):
        cmd = f'VSET1:{V:.2f}'
        self.write(cmd)
        time.sleep(SLEEP_DUR)

    def set_current(self, I):
        cmd = f'ISET1:{I:.2f}'
        self.write(cmd)
        time.sleep(SLEEP_DUR)

    def is_output_enabled(self):
        """This device is turned on by manual button, so this does nothing
        """
        return True
    
    def enable_output(self, _: bool):
        """This device is turned on by manual button, so this does nothing
        """
        return True

    def get_set_voltage(self):
        return float(self.query('VSET1?'))

    def get_set_current(self):
        return float(self.query('ISET1?'))

    def get_voltage(self):
        return float(self.query('VOUT1?'))

    def get_current(self):
        return float(self.query('IOUT1?'))

    def is_output_enabled(self):
        """This device is turned on by manual button, so this does nothing

        Returns:
            bool: True, this is always on if present
        """
        return True
    
    def open_device(self):
        opened = super().open_device()
        if not opened:
            return opened
        idn = self.query("*IDN?")
        time.sleep(self.query_delay)
        if not idn.startswith('TENMA 72-2715'):
            print(f"Wrong device response, expected TENMA 72-2715, got {idn}")
            self.close_device()
            return False
        return True