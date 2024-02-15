import serial
from .device_widget import DeviceReader

class TPG256(DeviceReader):
    '''DeviceReader for reading from a TPG 256 gauge controller.

    This will read from one of the sensors, as given in the sensor argument for the constructor.
    
    '''
    def __init__(self, parent, addr, sensor=1, data_key=None):
        """

        Args:
            parent (FigureModule): the module we are made from
            port (str): serial port to connect to
            sensor (int, optional): sensor to read, 1-6. Defaults to 1.
            data_key (str, optional): key to update with our value. Defaults to None.
        """
        super().__init__(parent, data_key, name=f"Pressure Gauge", axis_title=f"Pressure Gauge (mbar)")
        self.addr = addr

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3e}} mbar'
        else:
            self.settings.title_fmt = f'Latest: {{:.3e}} mbar'

        self.read_cmd = f'PR{sensor}\r\n'.encode()

    def make_file_header(self):
        # Adjust the header to indicate amps
        return "Local Time\tPressure (mbar)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We read only every 300ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        try:
            self.device = serial.Serial(port=self.addr)
            self.valid = True
        except Exception as err:
            print(err)
            print(f"Failed to open {self.name}")
            self.device = None
        return self.device != None

    def read_device(self):
        if self.device is None:
            return False, 0
        
        self.device.write(self.read_cmd)     
        response = self.device.readline()
        if response != b'\x06\r\n':
            print(f"Failed response? {response}")
            return False, 1e30
        self.device.write(b'\x05')
        response = self.device.readline().decode().strip().split(',')
        status = response[0]
        if status != '0':
            print(f"Wrong Status? {response}")
            return False, 1e30
        value = float(response[1])
        return True, value

    def close_device(self):
        if self.device is None:
            return
        self.device.close()