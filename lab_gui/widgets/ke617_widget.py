import time
import pyvisa

from .device_widget import DeviceReader
from .base_control_widgets import ControlButton

class KE617(DeviceReader):
    '''DeviceReader for reading from a Keithley 617 Electrometer
    
    Presently this is set to read current, and has buttons for toggling auto range and zerocheck.
    Zerocheck is also applied whenever this reader closes, unless the button to disable that is pressed.
    
    This uses pyvisa to read from the device via the given GPIB address.'''
    def __init__(self, parent, addr, data_key=None):
        """

        Args:
            parent (FigureModule): the module we are made from
            addr (int): GPIB Address
            data_key (str, optional): key to update with our value. Defaults to None.
        """
        super().__init__(parent, data_key, name=f"KE617-{addr}", axis_title=f"Current on KE617-{addr} (pA)")
        self.addr = addr

        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1e12

        # make a button for setting zerocheck
        self.zchk_button = ControlButton(text="ZCHK", default_value=True,toggle=self.toggle_zchk)
        self.zchk = True

        # make a button for autorange
        self.autorange_button = ControlButton(text="Auto Range", default_value=True,toggle=self.toggle_autorange)
        self.autorange = True

        # make a button for setting zerocheck when closed
        self.auto_zchk_button = ControlButton(text="Auto ZCHK", default_value=True,toggle=self.toggle_auto_zchk)
        self.auto_zchk = True

        # Add our buttons to the layout
        self._layout.addWidget(self.zchk_button)
        self._layout.addWidget(self.auto_zchk_button)
        self._layout.addWidget(self.autorange_button)
        self._layout.addStretch(0)

        # Include title based on key
        if data_key is not None:
            self.settings.title_fmt = f'{data_key}: {{:.3f}} pA'
        else:
            self.settings.title_fmt = f'Latest: {{:.3f}} pA'

    ###
    ### Start of DeviceReader function overrides
    ###

    def make_file_header(self):
        # Adjust the header to indicate amps
        return "Local Time\tCurrent (A)\n"
    
    def format_values_for_print(self, timestamp, value):
        # We read only every 300ms or so, so .2f is plenty of resolution on the timestamp
        return f"{timestamp:.2f}\t{value:.3e}\n"
    
    def open_device(self):
        # Try to open the device. We need to handle the exception that occurs in this
        # case, as then we can properly set device to None
        try:
            rm = pyvisa.ResourceManager()
            self.device = rm.open_resource(f'GPIB0::{self.addr}::INSTR')
            self.device.write("F1X") # AMP mode
            if self.zchk:
                self.device.write("C1X") # Zero Check On
            else:
                self.device.write("C0X") # Zero Check Off
            if self.autorange:
                self.device.write("R0X") # Auto range On
            else:
                self.device.write("R12X") # Auto Range Off
            self.zchk_O = self.zchk
            self.autorange_O = self.autorange
            self.valid = True
        except Exception as err:
            print(err)
            print(f"Failed to open {self.name}")
            self.device = None
        return self.device != None
            
    def read_device(self):
        # If we somehow failed to open, return false status.
        if self.device is None:
            return False, 0
        # Check if zchk was changed since we last read
        if self.zchk_O != self.zchk:
            if self.zchk:
                self.device.write("C1X") # Zero Check On
            else:
                self.device.write("C0X") # Zero Check Off
            self.zchk_O = self.zchk

        # Check status of autorange
        if self.autorange_O != self.autorange:
            if self.autorange:
                self.device.write("R0X") # Auto range On
            else:
                self.device.write("R12X") # Auto Range Off
            self.autorange_O = self.autorange

        # Zero checked, nothing to return
        if self.zchk:
            # Delay so we don't peg the core in the loop
            time.sleep(0.5)
            return False, 0
        
        response = self.device.read()
        # N(ormal)DCA(mps)
        if 'NDCA' in response:
            response = response.replace('NDCA', '') 
            return True, float(response.strip())
        elif response.startsWith("O"): # O(verflow)
            print("Over range")
        return False, 2e30

    def close_device(self):
        # If we somehow failed to open, nothing to close
        if self.device is None:
            return
        if self.auto_zchk:
            self.device.write("C1X") # Zero Check On
        self.device.close()

    def collect_saved_values(self, values):
        values["zchk"] = self.zchk_button
        values["auto_zchk"] = self.auto_zchk_button
        values["auto_range"] = self.autorange_button
        return super().collect_saved_values(values)

    def process_load_saved(self):
        # Sync our saved values
        self.toggle_zchk()
        self.toggle_autorange()
        self.toggle_auto_zchk()
        return super().process_load_saved()

    ###
    ### Start of KE617 specific functions
    ###
    
    def toggle_zchk(self):
        '''
        toggles the zerocheck option
        
        The actual toggling of zchk is handled in the read_device function to ensure
        that all serial comms happen on the same thread.
        '''
        self.zchk = self.zchk_button.isChecked()
        self.saver.on_changed(self.zchk_button)
    
    def toggle_auto_zchk(self):
        '''
        toggles if zchk is automatically set on when closed.
        '''
        self.auto_zchk = self.auto_zchk_button.isChecked()
        self.saver.on_changed(self.auto_zchk_button)
    
    def toggle_autorange(self):
        '''
        toggles the auto range option
        
        The actual toggling of auto range is handled in the read_device function to 
        ensure that all serial comms happen on the same thread.
        '''
        self.autorange = self.autorange_button.isChecked()
        self.saver.on_changed(self.autorange_button)

    