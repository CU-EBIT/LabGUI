import time
import serial

from .device_widget import DeviceReader

class SM7110(DeviceReader):
    '''DeviceReader for a HIOKI SM7110.
    
    Presently this is set to read current, with an averaging of 16 samples.
    
    This uses pyserial to read the device from the given serial address (port argument)'''
    def __init__(self, parent, port="COM4", data_key=None):
        super().__init__(parent, data_key, name=f"SM7110", axis_title=f"SM7110 (pA)")
        self.port = port

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1e12

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3f}} pA'
        else:
            self.settings.title_fmt = f'Latest: {{:.3f}} pA'

    def make_file_header(self):
        # Adjust the header to indicate amps
        return "Local Time\tCurrent (A)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We read only every 10-300ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        try:
            self.device = serial.Serial(self.port)
            self.device.write(b"*IDN?\n")
            idn = self.device.readline().decode().strip()
            print(idn)
            if not idn.startswith('HIOKI,SM7110'):
                print(f"Wrong device on {self.port}, expected a HIOKI,SM7110")
                self.device = None
                return False

            self.device.write(b":MEASure:MODE A\n")
            self.device.write(b":RANGe:AUTO ON\n")
            self.device.write(b":AVERage HOLD\n")
            self.device.write(b":AVERage:COUNt 16\n")
            self.device.write(b":SPEEd SLOW2\n")

            self.device.write(b":STARt\n")

            self.valid = True
        except Exception as err:
            print(err)
            print('error opening SM7110?')
            self.device = None
        return self.device != None

    def read_device(self):

        if self.device is None:
            return False, 0

        self.device.write(b":STATe?\n")
        status = self.device.readline().decode()[0]
        while status == "2":
            self.device.write(b":STATe?\n")
            status = self.device.readline()[0]
            time.sleep(0.001)
        self.device.write(b":MEASure?\n")
        var = float(self.device.readline().decode().strip())
        if var > 1e30:
            print("Over range!")
            return False, 2e30
        return True, var

    def close_device(self):
        if self.device is None:
            return
        self.device.write(b":STOP\n")
        self.device.close()