from .base_devices import BasicPowerSupply
from .drivers.pps2116a import PPS2116A as Device

class PPS2116A(BasicPowerSupply):
    def __init__(self, parent, addr, data_keys=[None, None]):
        super().__init__(parent, Device(addr), "PPS2116A", data_keys, [0, 32], [0, 5])