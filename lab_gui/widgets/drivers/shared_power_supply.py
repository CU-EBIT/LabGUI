import os
import time
import threading

from ...utils.data_client import BaseDataClient, DataCallbackServer
from ..device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource

class DummySupply(BasicCurrentMeasure, BasicVoltageMeasure, BasicCurrentSource, BasicVoltageSource):
    def __init__(self):
        self.V = 0
        self.I = 0
        self.on = False

    def get_current(self):
        return self.I if self.on else 0.0
    
    def get_voltage(self):
        return self.V if self.on else 0.0
    
    def set_current(self, current):
        self.I = current
    
    def set_voltage(self, voltage):
        self.V = voltage
    
    def get_set_voltage(self):
        return self.V
    
    def get_set_current(self):
        return self.I
    
    def is_output_enabled(self):
        return self.on
    
    def enable_output(self, output):
        self.on = output

class SupplyWrapper(BasicCurrentMeasure, BasicVoltageMeasure, BasicCurrentSource, BasicVoltageSource):
    def __init__(self, wrapped_supply):
        self.wrapped = wrapped_supply

    def get_current(self):
        return self.wrapped.get_current()
    
    def get_voltage(self):
        return self.wrapped.get_voltage()
    
    def set_current(self, current):
        return self.wrapped.set_current(current)
    
    def set_voltage(self, voltage):
        return self.wrapped.set_voltage(voltage)
    
    def get_set_voltage(self):
        return self.wrapped.get_set_voltage()
    
    def get_set_current(self):
        return self.wrapped.get_set_current()
    
    def is_output_enabled(self):
        return self.wrapped.is_output_enabled()
    
    def enable_output(self, output):
        return self.wrapped.enable_output(output)
    
class PowerSupply(SupplyWrapper):
    def __init__(self, key, wrapped_supply, callbackServer=None, data_client=None, verbose=False, update_rate=0.25):
        super().__init__(wrapped_supply)
        self.client = BaseDataClient() if data_client is None else data_client
        self.server = DataCallbackServer() if callbackServer is None else callbackServer
        self.key_on = f"{key}_Enabled"
        self.key_v_set = f"{key}_Voltage_Set"
        self.key_v_read = f"{key}_Voltage_Read"
        self.key_i_set = f"{key}_Current_Set"
        self.key_i_read = f"{key}_Current_Read"
        self.verbose = verbose
        self.running = True
        self.io_lock = threading.Lock()

        # Register handlers
        self.server.add_listener(self.key_on, self.on_update)
        self.server.add_listener(self.key_v_set, self.on_update)
        self.server.add_listener(self.key_i_set, self.on_update)

        # Register run loop for feedback
        def run_loop():
            t = time.time()
            last_V, last_I = 1e32, 1e32
            V_t = t
            I_t = t
            while self.running:
                V_o, I_o = self.get_voltage(), self.get_current()
                t = time.time()
                if V_o != last_V or t - V_t > 5:
                    V_t = t
                    self.client.set_float(self.key_v_read, V_o)
                if I_o != last_I or t - I_t > 5:
                    I_t = t
                    self.client.set_float(self.key_i_read, I_o)
                if self.verbose:
                    with self.io_lock:
                        V_s, I_s = self.get_set_voltage(), self.get_set_current()
                    if os.name != 'nt':
                        os.system("clear")
                    print(f' {I_s:0.3f}A {V_s:0.3f}V\n {I_o:0.3f}A {V_o:0.3f}V')
                time.sleep(update_rate)
        
        self.run_thread = threading.Thread(target=run_loop,daemon=True)
        self.run_thread.start()

    def __del__(self):
        self.close()

    def close(self):
        if self.running:
            self.running = False
            self.run_thread.join()

    def on_update(self, key, value):
        print(key, value)
        if key == self.key_on:
            self.enable_output(value[1])
        elif key == self.key_i_set:
            self.set_current(value[1])
        elif key == self.key_v_set:
            self.set_voltage(value[1])

def run_dummy_test(dummy=None):
    dummy = DummySupply() if dummy is None else dummy
    BaseDataClient.DATA_SERVER_KEY = "local_test"
    supply = PowerSupply("Test", dummy, verbose=True)
    input("")
    supply.close()