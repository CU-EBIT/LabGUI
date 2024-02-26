import serial
import time
import os

from .device_widget import DeviceReader
from .plot_widget import Settings

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
        super().__init__(parent, key, name=f"Pressure Gauge", has_plot=False, axis_title=f"Pressure Gauge (mbar)")
        self.addr = addr

        # We manage our own logging, as we do multiple sensors
        self.custom_logging = True

        self.settings = Settings()

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
        self.sensors = {}
        if isinstance(sensor, int):
            self.sensor = [sensor]
            self.data_keys = {sensor:data_key}
        elif isinstance(sensor, list):
            assert len(sensor) == len(data_key) and isinstance(data_key, list)
            self.data_keys = {sensor[i]:data_key[i] for i in range(len(sensor))}

        self.log_files = {}
        self.do_log_m = False
        
        for i in range(len(self.sensor)):
            sensor = self.sensor[i]
            cmd = f'PR{sensor}\r\n'.encode()
            key = self.data_keys[sensor]
            self.sensors[sensor] = [True, cmd, key]
        
        for i in range(1, len(self.on) + 1):
            if not i in self.sensors:
                cmd = f'PR{i}\r\n'.encode()
                self.sensors[i] = [False, cmd, None]
            on, _, key = self.sensors[i]
            setattr(self.settings, f'sensor_on_{i}', on)
            setattr(self.settings, f"sensor_key_{i}", "" if key is None else key)

            self.settings._names_[f'sensor_on_{i}'] = f"Sensor {i}: "
            self.settings._names_[f'sensor_key_{i}'] = f"Key {i}: "

        def on_changed(*_):
            while self.read_lock:
                time.sleep(0.001)
            self.read_lock = True
            for i in range(1, len(self.on) + 1):
                on, _, key = self.sensors[i]
                on = getattr(self.settings, f'sensor_on_{i}')
                key = getattr(self.settings, f"sensor_key_{i}")
                cmd = f'PR{i}\r\n'.encode()
                self.sensors[i] = [on, cmd, key]
            self.needs_init = True
            self.read_lock = False
        
        self.read_lock = False
        self.needs_init = True

        self.settings._callback = on_changed

    def process_load_saved(self):
        super().process_load_saved()
        self.settings._callback()

    def make_file_header(self):
        # Adjust the header to indicate amps
        return "Local Time\tPressure (mbar)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We read only every 300ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def init_sensors(self):
        if self.device is None:
            self.open_device()
        if self.device is None:
            print("Error, TPG 256 device not open, cannot init sensors")
            return
        self.needs_init = False
        self.on = [1,1,1,1,1,1]
        for i in range(len(self.on)):
            on, _, _ = self.sensors[i + 1]
            self.on[i] = 2 if on else 1
        on_cmd = f'SEN'
        for id in self.on:
            on_cmd = on_cmd + f',{id}'
        on_cmd = on_cmd + '\r\n'
        self.device.write(on_cmd.encode())
        self.device.readline()
        self.device.write(b'\x05')
        self.device.readline()

    def open_device(self):
        try:
            self.device = serial.Serial(port=self.addr)
            self.valid = True
        except Exception as err:
            print(err)
            print(f"Failed to open {self.name}")
            self.device = None
        return self.device != None

    def read_channel(self, channel):
        valid, value, timestamp = True, 0, 0

        on, cmd, key = self.sensors[channel]
        if not on:
            return False, 0, 0
        
        self.device.write(cmd)     
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
            timestamp = time.time()
            if key is not None:
                self.client.set_float(key, value)
        return valid, value, timestamp

    def read_device(self):
        if self.device is None:
            return False, 0
        
        if not self.do_log and len(self.log_files):
            self.log_files = {}

        while self.read_lock:
            time.sleep(0.001)
        self.read_lock = True

        if self.needs_init:
            self.init_sensors()

        read_values = [None for _ in self.sensors]

        first_channel = True
        # Now read the remainder
        for channel in self.sensors.keys():
            _valid, _value, timestamp = self.read_channel(channel)
            _, _, key = self.sensors[channel]
            if _valid and key is not None:
                read_values[channel - 1] = (timestamp, _value, key)
            if first_channel:
                first_channel = False
                valid, value, timestamp = _valid, _value, timestamp
        self.read_lock = False
        
        # Now check if we need to log things
        if self.do_log:
            for i in range(len(read_values)):
                if read_values[i] is None:
                    continue
                timestamp, _value, key = read_values[i]

                # Check if we have the file, if not we will make it
                if key in self.log_files:
                    file_name = self.log_files[key]
                else:
                    file_name = self.get_log_file(key)
                    if not os.path.exists(file_name):
                        with open(file_name, 'w') as file:
                            file.write(self.make_file_header())
                    self.log_files[key] = file_name

                # Finally append the line to the log
                with open(file_name, 'a') as file:
                    file.write(self.format_values_for_print(timestamp, _value))

        return valid, value

    def close_device(self):
        if self.device is None:
            return
        self.device.close()