import socket

from .device_widget import DeviceReader

class KEDMM6500(DeviceReader):
    '''DeviceReader for reading from a Keithley DMM6500 Multimeter
    
    Presently this is just set to call read?, so it will measure whatever the multimeter is set for.
    '''
    def __init__(self, parent, addr, data_key=None):
        """

        Args:
            parent (FigureModule): the module we are made from
            addr (tuple): (address, port) pair for the instrument.
            data_key (str, optional): key to update with our value. Defaults to None.
        """
        super().__init__(parent, data_key, name=f"KEDMM6500", axis_title=f"Voltage on KEDMM6500 (V)")
        self.addr = addr

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3e}} V'
        else:
            self.settings.title_fmt = f'Latest: {{:.3e}} V'

        self.header = "Local Time\tVoltage (V)\n"

    def make_file_header(self):
        # Adjust the header to indicate amps
        return self.header
    
    def format_values_for_print(self, timestamp, value):
        return f"{timestamp:.2f}\t{value:.4e}\n"
    
    def open_device(self):
        try:
            self.device = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.device.connect(self.addr)
            self.device.send(b"*idn?\n")
            print(self.device.recv(1024))
            self.valid = True
        except Exception as err:
            print(err)
            print(f"Failed to open {self.name}")
            self.device = None
        return self.device != None

    def read_device(self):

        if self.device is None:
            return False, 0
        
        self.device.send(b"read?\n")
        response = float(self.device.recv(1024).decode().strip())
        return True, response

    def close_device(self):
        if self.device is None:
            return
        self.device.close()

if __name__ == "__main__":
    addr=("169.254.131.236", 5025)
    device = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    device.connect(addr)
    device.send(b"*idn?\n")
    print(device.recv(1024))
    device.send(b"read?\n")
    print(float(device.recv(1024).decode().strip()))
    device.close()