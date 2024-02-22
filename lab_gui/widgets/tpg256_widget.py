import serial
import time
import os

from .device_widget import DeviceReader

class TPG256(DeviceReader):
    '''DeviceReader for reading from a TPG 256 gauge controller.

    This will read from one of the sensors, as given in the sensor argument for the constructor.

    If you provide the list arguments, it will only display the first, but will store the remainder on the data map for plotting via a seperate plotter.
    
    '''
    def __init__(self, parent, addr, sensor=1, data_key=None):
        """
        If you want to read multiple sensors, provide a list of the sensors for sensor. Then also provde a same-sized list of str for data_key.

        The first entry in the list will be used for the default plot, but then the rest of the keys will be populated for reading with a seperate plotter.

        Args:
            parent (FigureModule): the module we are made from
            port (str): serial port to connect to
            sensor (int, optional) or list of int: sensor to read, 1-6. Defaults to 1.
            data_key (str, optional) or list of str: key to update with our value. Defaults to None.
        """
        key = data_key
        if isinstance(key, list): 
            key = key[0]
        super().__init__(parent, key, name=f"Pressure Gauge", axis_title=f"Pressure Gauge (mbar)")
        self.addr = addr

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3e}} mbar'
        else:
            self.settings.title_fmt = f'Latest: {{:.3e}} mbar'

        self.sensor = sensor
        self.on = [0,0,0,0,0,0]
        if isinstance(sensor, int):
            self.sensor = [sensor]
            self.read_cmd = f'PR{sensor}\r\n'.encode()
            self.read_multiple = False
        elif isinstance(sensor, list):
            assert len(sensor) == len(data_key) and isinstance(data_key, list)
            self.read_multiple = True
            self.read_cmds = [f'PR{s}\r\n'.encode() for s in sensor]
            self.data_keys = data_key
            self.do_log_m = False
            self.log_files = {}
            

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
            self.on = [1,1,1,1,1,1]
            for sensor in self.sensor:
                self.on[sensor-1] = 2
            on_cmd = f'SEN'
            for id in self.on:
                on_cmd = on_cmd + f',{id}'
            on_cmd = on_cmd + '\r\n'
            self.device.write(on_cmd.encode())
            self.device.readline()
            self.device.write(b'\x05')
            self.device.readline()
        except Exception as err:
            print(err)
            print(f"Failed to open {self.name}")
            self.device = None
        return self.device != None

    def read_device(self):
        if self.device is None:
            return False, 0
        
        if not self.do_log and len(self.log_files):
            self.log_files = {}

        valid, value = True, 0
        if self.read_multiple:
            read_cmd = self.read_cmds[0]
            # First read the "main" sensor
            self.device.write(read_cmd)     
            response = self.device.readline()
            if response != b'\x06\r\n':
                print(f"Failed response? {response}")
                valid = False
            if valid:
                self.device.write(b'\x05')
                response = self.device.readline().decode().strip().split(',')
                status = response[0]
                if status != '0':
                    print(f"Wrong Status? {response}")
                    valid = False
            if valid:
                value = float(response[1])
            
            # Now read the remainder
            for i in range(1, len(self.read_cmds)):
                read_cmd = self.read_cmds[i]
                key = self.data_keys[i]
                # First read the "main" sensor
                _valid = True
                self.device.write(read_cmd)     
                response = self.device.readline()
                if response != b'\x06\r\n':
                    print(f"Failed response? {response}")
                    _valid = False
                if _valid:
                    self.device.write(b'\x05')
                    response = self.device.readline().decode().strip().split(',')
                    status = response[0]
                    if status != '0':
                        print(f"Wrong Status? {response}")
                        _valid = False
                if _valid:
                    timestamp = time.time()
                    # And stuff them in the data server if valid
                    _value = float(response[1])
                    self.client.set_float(key, _value)

                    # And try to log them
                    if self.do_log:
                        if key in self.log_files:
                            file_name = self.log_files[key]
                        else:
                            file_name = self.get_log_file(key)
                            if not os.path.exists(file_name):
                                with open(file_name, 'w') as file:
                                    file.write(self.make_file_header())
                            self.log_files[key] = file_name
                        with open(file_name, 'a') as file:
                            file.write(self.format_values_for_print(timestamp, _value))

        else:
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
        return valid, value

    def close_device(self):
        if self.device is None:
            return
        self.device.close()