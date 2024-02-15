import socket

from .device_widget import DeviceReader

class SCPITCPIPReader(DeviceReader):
    '''DeviceReader for reading from anything that uses SCPI over TCPIP, and just needs to call read?
    
    Presently this is just set to call read?, so it will measure whatever the multimeter is set for.
    '''
    def __init__(self, parent, name, addr, data_key=None):
        """
        Args:
            parent (FigureModule): the module we are made from
            name (str): Instrument name.
            addr (tuple): (address, port) pair for the instrument.
            data_key (str, optional): key to update with our value. Defaults to None.
        """
        super().__init__(parent, data_key, name)
        self.addr = addr
        self.init_settings()

    def init_settings(self):
        """Init your settings here for things like the plot axes, etc
        """
    
    def valid_idn(self, idn):
        """Check if the IDN response is as expected

        Args:
            idn (str): response from "*idn?"

        Returns:
            bool: whether this is acceptable idn response
        """
        return idn != None

    def open_device(self):
        try:
            self.device = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.device.connect(self.addr)
            self.device.send(b"*idn?\n")
            if not self.valid_idn(self.device.recv(1024).decode().strip()):
                self.close_device()
                self.device = None
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
    addr=("0.0.0.0", 5025)
    device = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    device.connect(addr)
    device.send(b"*idn?\n")
    print(device.recv(1024))
    device.send(b"read?\n")
    print(float(device.recv(1024).decode().strip()))
    device.close()