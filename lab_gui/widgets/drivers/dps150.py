import serial
import struct
import time
import threading

# Thanks to https://github.com/cho45/fnirsi-dps-150/tree/main for information on the formatting needed here.

HEADER_INPUT = b'\xf0' # 240
HEADER_OUTPUT = b'\xf1'# 241

CMD_GET = b'\xa1'   # 161
CMD_BAUD = b'\xb0'  # 176
CMD_SET = b'\xb1'   # 177
CMD_UNK_2 = b'\xc0' # 192
CMD_INIT = b'\xc1'  # 193

VALUE_OUTPUT_VI = b'\xc3'   # 195
VALUE_INPUT_V = b'\xc0'     # 192
VALUE_DEVICE_T = b'\xc4'    # 196
VALUE_OUTPUT_LIM_V = b'\xe2'# 226
VALUE_OUTPUT_LIM_I = b'\xe3'# 227

VALUE_OUTPUT_CAP = b'\xd9'  # 217
VALUE_OUTPUT_ENE = b'\xda'  # 218

VOLTAGE_SETPOINT = b'\xc1' # 193
CURRENT_SETPOINT = b'\xc2' # 194

OUTPUT_ENABLED = b'\xdb' # 219
OUTPUT_MODE = b'\xdd'    # 221, 0 for CC, 1 for CVs

MODEL_NAME = b'\xde'
VERSION_HW = b'\xdf'
VERSION_FW = b'\xe0'
ALL = b'\xff'

unpackers = {
    VALUE_OUTPUT_VI[0]: lambda data,callback: callback("output_VIP",struct.unpack('3f', data)),
    VALUE_INPUT_V[0]: lambda data,callback: callback("input_V",struct.unpack('f', data)),
    VALUE_DEVICE_T[0]: lambda data,callback: callback("device_T",struct.unpack('f', data)),
    VOLTAGE_SETPOINT[0]: lambda data,callback: callback("set_V",struct.unpack('f', data)),
    CURRENT_SETPOINT[0]: lambda data,callback: callback("set_I",struct.unpack('f', data)),
    MODEL_NAME[0]: lambda data,callback: callback("Name", data.decode()),
    VERSION_HW[0]: lambda data,callback: callback("HW", data.decode()),
    VERSION_FW[0]: lambda data,callback: callback("FW", data.decode()),
    OUTPUT_ENABLED[0]: lambda data,callback: callback("Output", data[0]==1),
    OUTPUT_MODE[0]: lambda data,callback: callback("Mode", "CC" if data[0]==0 else "CV"),

    # This block we don't really care about for now.
    VALUE_OUTPUT_LIM_V[0]: lambda *_: False,
    VALUE_OUTPUT_LIM_I[0]: lambda *_: False,
    VALUE_OUTPUT_CAP[0]: lambda *_: False,
    VALUE_OUTPUT_ENE[0]: lambda *_: False,
    # VALUE_OUTPUT_LIM_V[0]: lambda data,callback: callback("limit_V",struct.unpack('f', data)),
    # VALUE_OUTPUT_LIM_I[0]: lambda data,callback: callback("limit_I",struct.unpack('f', data)),
    # VALUE_OUTPUT_CAP[0]: lambda data,callback: callback("total_CAP",struct.unpack('f', data)),
    # VALUE_OUTPUT_ENE[0]: lambda data,callback: callback("total_ENE",struct.unpack('f', data)),
}

def compute_checksum(msg):
    checksum = 0
    for i in range(2,len(msg)):
        checksum += msg[i]
    checksum %= 256
    return (checksum).to_bytes(1, byteorder='big')

def send_cmd(dev, header, command, argument, data):
    if len(data) > 1:
        data = (len(data)).to_bytes(1, byteorder='big') + data
    msg = header + command + argument + data
    msg += compute_checksum(msg)
    dev.write(msg)
    time.sleep(0.025)

def read_response(dev:serial.Serial, callback=print):
    dt = dev.timeout
    dev.timeout = None

    args = dev.read(4)
    header = args[0]
    cmd = args[1]
    arg = args[2]
    length = args[3]
    # while dev.in_waiting < length + 1:
    data = dev.read(length + 1)
    args = args + data
    checksum = compute_checksum(args[:-1])
    valid = checksum[0] == args[-1]
    handled = False
    if header == HEADER_INPUT[0]:
        if cmd == CMD_GET[0]:
            if arg in unpackers:
                try:
                    unpackers[arg](data[:-1],callback)
                    handled = True
                except Exception as err:
                    print(err)
    if not handled:
        print("unhandled: ", header, cmd, arg, valid)

    # Pass around again if still things in buffer
    if dev.in_waiting > 0:
        read_response(dev, callback)

    dev.timeout = dt

def open(dev):
    send_cmd(dev,HEADER_OUTPUT,CMD_INIT,b'\x00',b'\x01')

def close(dev):
    send_cmd(dev,HEADER_OUTPUT,CMD_INIT,b'\x00',b'\x00')

# from ..device_types.devices import BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource
# class DPS150(BasicCurrentMeasure, BasicCurrentSource, BasicVoltageMeasure, BasicVoltageSource):
class DPS150:
    def __init__(self,addr=None):
        if addr is None:
            desc_matcher=lambda _:True
            hwid_matcher=lambda x: "VID:PID=2E3C:5740" in x
            try:
                from .serial_helper import find_devices
            except ImportError:
                # for test case run from inside this file.
                from serial_helper import find_devices
            addr = find_devices(desc_matcher,hwid_matcher)[0]
        self.addr = addr
        self.dev = None
        self.running = False

    def __del__(self):
        if not hasattr(self, "dev"):
            return
        if self.dev is not None:
            self.close()

    def open(self, auto_read=False):
        assert(self.dev is None)
        dev = serial.Serial(self.addr,115200,timeout=0.1)
        if hasattr(dev, 'set_buffer_size'):
            dev.set_buffer_size(1024,1024)
        self.dev = dev
        open(self.dev)
        self.check_valid()
        if auto_read:
            self.running = True
            def run_loop():
                while self.running:
                    self.read_values()
            self.run_thread = threading.Thread(target=run_loop,daemon=True)
            self.run_thread.start()

    def close(self):
        assert(self.dev is not None)
        if self.running:
            self.running = False
            self.run_thread.join()
        close(self.dev)
        self.dev.close()
        self.dev = None

    def send_cmd(self, cmd, arg, data=b'\x00'):
        send_cmd(self.dev, HEADER_OUTPUT, cmd, arg, data)

    def read_values(self):
        read_response(self.dev, self.on_read)

    def check_valid(self):
        self.get_set_current()
        self.get_set_voltage()
        self.is_output_enabled()
        while True:
            if 'V_out' in self.__dict__:
                return
            time.sleep(0.025)
            self.read_values()

    def on_read(self, msg, data):
        if msg == 'output_VIP':
            self.V_out, self.I_out, self.P_out = data
        elif msg == 'input_V':
            self.V_in = data[0]
        elif msg == 'device_T':
            self.T = data[0]
        elif msg == 'set_V':
            self.V_set = data[0]
        elif msg == 'set_I':
            self.I_set = data[0]
        elif msg == 'Output':
            self.Output_enabled = data
        elif msg == 'Mode':
            self.mode = data
        else:
            print(msg, data)
    
    def get_current(self):
        if not self.running:
            self.send_cmd(CMD_GET, VALUE_OUTPUT_VI)
            self.read_values()
        return self.I_out
    
    def get_set_current(self):
        if not self.running:
            self.send_cmd(CMD_GET, CURRENT_SETPOINT)
            self.read_values()
        return self.I_set
    
    def set_current(self, current:float):
        differs = abs(current-self.I_set) > 1e-5
        self.I_set = current
        if differs:
            self.send_cmd(CMD_SET, CURRENT_SETPOINT, struct.pack('f', current))
            self.get_set_current()
        return differs
    
    def get_voltage(self):
        if not self.running:
            self.send_cmd(CMD_GET, VALUE_OUTPUT_VI)
            self.read_values()
        return self.V_out
    
    def get_set_voltage(self):
        if not self.running:
            self.send_cmd(CMD_GET, VOLTAGE_SETPOINT)
            self.read_values()
        return self.V_set
    
    def set_voltage(self, voltage:float):
        differs = abs(voltage-self.V_set) > 1e-5
        self.V_set = voltage
        if differs:
            self.send_cmd(CMD_SET, VOLTAGE_SETPOINT, struct.pack('f', voltage))
            self.get_set_voltage()
        return differs
    
    def enable_output(self, state):
        differs = self.Output_enabled!=state
        self.Output_enabled = state
        if differs:
            self.send_cmd(CMD_SET, OUTPUT_ENABLED, b'\x00' if not state else b'\x01')
            self.get_set_voltage()
        return differs

    def is_output_enabled(self):
        if not self.running:
            self.send_cmd(CMD_GET, OUTPUT_ENABLED)
            self.read_values()
        return self.Output_enabled


def test_current_ramp(dev:DPS150,high=0.25,steps=100,sleep=0.1):
    high = 0.25
    steps = 10
    sleep = 1.0
    dev.set_voltage(5.0)
    dev.set_current(0)
    time.sleep(sleep)
    dev.enable_output(True)
    time.sleep(2.5)
    for i in range(steps):
        dev.set_current(high*(float(i)/steps))
        time.sleep(sleep)
    dev.set_current(high)
    time.sleep(sleep)
    for i in range(steps):
        dev.set_current(high - high*(float(i+1)/steps))
        time.sleep(sleep)
    dev.enable_output(False)

def test_voltage_ramp(dev:DPS150,high=0.25,steps=100,sleep=0.1):
    high = 0.25
    steps = 10
    sleep = 1.0
    dev.set_current(5.0)
    dev.set_voltage(0)
    time.sleep(sleep)
    dev.enable_output(True)
    for i in range(steps):
        dev.set_voltage(high*(float(i)/steps))
        time.sleep(sleep)
    dev.set_voltage(high)
    time.sleep(sleep)
    for i in range(steps):
        dev.set_voltage(high - high*(float(i+1)/steps))
        time.sleep(sleep)
    dev.enable_output(False)

def test_v_i(addr):
    dev = DPS150(addr)
    dev.open()
    test_current_ramp(dev)
    test_voltage_ramp(dev)
    dev.close()

def test_loop_run(addr):
    dev = DPS150(addr)
    dev.open(auto_read=True)
    dev.close()

if __name__ == "__main__":
    addr = None # Auto find it
    test_v_i(addr)
    # test_loop_run(addr)