from .base_devices import BasicPowerSupply
from .drivers.tenma_72_2715 import TENMA722715 as Device

class TENMA722715(BasicPowerSupply):
    def __init__(self, parent, addr, data_keys=[None, None]):
        super().__init__(parent, Device(addr), "TENMA-72-2715", data_keys, [0, 60], [0, 2])