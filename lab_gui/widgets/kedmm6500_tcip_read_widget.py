from .scpi_tcpip_reader_widget import SCPITCPIPReader

class KEDMM6500(SCPITCPIPReader):
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
        super().__init__(parent, "KEDMM6500", addr, data_key=data_key)

    def init_settings(self):
        # Update settings scales so that the pA title is correct
        self.settings.log_scale = False
        self.settings.scale = 1

        # Include title based on key
        if self.data_key is not None:
            self.settings.title_fmt = f'{self.data_key}: {{:.3e}} V'
        else:
            self.settings.title_fmt = f'Latest: {{:.3e}} V'

        self.settings.axis_name = f"Voltage on KEDMM6500 (V)"
        self.header = "Local Time\tVoltage (V)\n"

    def make_file_header(self):
        # Adjust the header to indicate amps
        return self.header
    
    def format_values_for_print(self, timestamp, value):
        return f"{timestamp:.2f}\t{value:.4e}\n"