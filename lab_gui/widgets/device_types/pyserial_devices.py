import serial
import time

from .devices import BaseDevice

class PySerialDevice(BaseDevice):

    def __init__(self, addr, write_term='\n', read_term='\n') -> None:
        super().__init__()
        self.addr = addr
        self.write_term = write_term
        self.read_term = read_term.encode()
        self.query_delay = 0
    
    def open_device(self):
        try:
            self.device = serial.Serial(self.addr)
            self.valid = True
        except Exception as err:
            print(err)
            print('error opening PPS 2116A?')
            self.device = None
        return self.device != None

    def close_device(self):
        if self.device is None:
            return
        self.device.close()
        self.device = None

    def write(self, cmd):
        if isinstance(cmd, bytes):
            self.device.write(cmd)
        else:
            self.device.write(f'{cmd}{self.write_term}'.encode())

    def read(self):
        return self.device.read_until(self.read_term).decode().strip()

    def query(self, cmd):
        self.write(cmd)
        if self.query_delay > 0:
            time.sleep(self.query_delay)
        return self.read()
    
    def read_raw(self):
        return self.device.read_all()