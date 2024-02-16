import random
import time
from .device_widget import DeviceReader

class TestDevice(DeviceReader):
    '''Pretends to be a device that responds with numbers'''
    def __init__(self, parent, id=0, data_key=None):
        super().__init__(parent, data_key, name=f"TEST_{id}", axis_title=f"??? (units)")

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3f}} ???'
        else:
            self.settings.title_fmt = f'Latest: {{:.3f}} ???'

    def make_file_header(self):
        # Adjust the header to indicate ???
        return "Local Time\tValue (???)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We "read" only every 50ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        # We don't actually have a device, so we pretend to open something
        self.device = 1
        self.valid = True
        return self.device != None

    def read_device(self):
        if self.device is None:
            return False, 0
        # Report some random value
        var = random.random()
        # Sleep to emulate a read delay in the device
        time.sleep(0.05 + var * 1e-3)
        return True, var

    def close_device(self):
        if self.device is None:
            return
        # nothing was opened to close earlier
        self.device = None