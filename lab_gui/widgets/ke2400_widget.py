import threading
import serial
import time

import numpy

# QT Widgets
from ..utils.qt_helper import *

from .device_widget import DeviceReader
from .plot_widget import Plot
from .base_control_widgets import SingleInputWidget, get_tracked_value, _red_, _green_

from ..modules.module import BetterAxisItem
from ..utils.data_client import BaseDataClient

class KE2400(DeviceReader):
    def __init__(self, parent, port, baudrate=9600, name="KE2400", **args):

        self.i_cmpl_key = f'{name}_I_Compl'
        self.v_0_key = f'{name}_V_0'
        self.v_1_key = f'{name}_V_1'
        self.measure_n = f'{name}_N'

        self.baudrate = baudrate
        self.port = port

        for key, value in args.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.client = BaseDataClient()
        self.client.set_float(self.i_cmpl_key, 1e-1)
        self.client.set_float(self.v_0_key, -10)
        self.client.set_float(self.v_1_key, 10)
        self.client.set_float(self.measure_n, 100)
        self.cur_range = QLineEdit('AUTO')
        
        super().__init__(parent, name=name, **args)

        # Time domain controls
        time_outer = QVBoxLayout()
        time_outer.setSpacing(0)
        time_layout = QHBoxLayout()
        time_layout.setSpacing(0)

        self.do_sweep = False
        self.lock = threading.Lock()
        def apply():
            if self.paused:
                return
            with self.lock:
                self.set_locked_texture()
                self.do_sweep = True

        self.applyBtn = QPushButton("Apply")
        self.applyBtn.clicked.connect(apply)
        self.set_unlocked_texture()

        line = SingleInputWidget(self, self.i_cmpl_key, "{:.2e}")
        time_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.v_0_key, "{:.2f}")
        time_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.v_1_key, "{:.2f}")
        time_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.measure_n, "{}")
        time_layout.addWidget(line)
        self._modules.append(line)
        time_layout.addWidget(self.cur_range)

        time_layout.addWidget(self.applyBtn)
        time_layout.addStretch(0)

        time_outer.addWidget(QLabel("Time Range Control"))
        time_outer.addLayout(time_layout)
        
        self._layout.addLayout(time_outer)

    def collect_saved_values(self, values):
        # values['CURR_RANG'] = self.cur_range
        return super().collect_saved_values(values)

    def process_load_saved(self):
        self.client.set_float(self.i_cmpl_key, self.settings.I_cmpl)
        self.client.set_float(self.v_0_key, self.settings.V_0)
        self.client.set_float(self.v_1_key, self.settings.V_1)
        self.client.set_float(self.measure_n, self.settings.N )
        return super().process_load_saved()

    def set_locked_texture(self):
        self.applyBtn.setStyleSheet(f"background-color : {_red_}")

    def set_unlocked_texture(self):
        self.applyBtn.setStyleSheet(f"background-color : {_green_}")

    def make_plot(self):
        self.plot_widget = Plot(x_axis=BetterAxisItem('bottom'))
        self.plot_widget.cull_x_axis = False
        self.plot_widget.show_avg = False
        self.plot_widget.label_x = "Voltage (V)"

    def set_data_key(self, _):
        self.settings = self.plot_widget.settings

        to_remove = [
            'update_rate',
            'log_length',
            'reload_hours',
            'paused',
        ]
        
        for var in to_remove:
            if var in self.settings._names_:
                del self.settings._names_[var]

        self.settings._names_['V_0'] = 'Start V: '
        self.settings._names_['V_1'] = 'End V: '
        self.settings._names_['I_cmpl'] = 'Compliance Current: '
        self.settings._names_['N'] = 'Samples: '
        self.settings.log_scale = False

        try:
            print("Making settings")
            _, self.settings.I_cmpl = get_tracked_value(self.i_cmpl_key)
            _, self.settings.V_0 = get_tracked_value(self.v_0_key)
            _, self.settings.V_1 = get_tracked_value(self.v_1_key)
            _, self.settings.N = get_tracked_value(self.measure_n)
        except Exception as err:
            print(err)
            print(f"failed to init save state for {self.name}")

        self.settings._options_ = {}

        self.plot_widget._has_value = True
        self.plot_widget.update_values = lambda*_:_
        self.plot_widget.get_data = self.get_data

        self.plot_widget.keys = [["", "IV Curve", ""]]

    def close_device(self):
        if self.device is None:
            return
        self.device.close()
    
    def open_device(self):
        try:
            self.device = serial.Serial(self.port, baudrate=self.baudrate)
            self.device.write(b"*IDN?\n")
            self.device.timeout = 0.25
            time.sleep(0.1)
            idn = self.device.read_all().decode().strip()
            print(idn)
            if not idn.startswith('KEITHLEY INSTRUMENTS INC.,MODEL 24'):
                print(f"Wrong device on {self.port}, expected a KEITHLEY INSTRUMENTS INC.,MODEL 24, got {idn}")
                self.device = None
                return False

            self.valid = True
        except Exception as err:
            print(err)
            print('error opening SM7110?')
            self.device = None
        return self.device != None
    
    def do_device_update(self):
        with self.lock:
            try:
                if self.do_sweep:
                    device = self.device
                    
                    # Auto range for voltage and current
                    cmd = b':VOLT:RANG:AUTO ON;\n'
                    device.write(cmd)

                    curr_range = self.cur_range.text().upper()

                    if curr_range == 'AUTO':
                        cmd = b':CURR:RANG:AUTO ON;\n'
                        device.write(cmd)
                    else:
                        cmd = b':CURR:RANG:AUTO OFF;\n'
                        device.write(cmd)
                        cmd = f':CURR:RANG {curr_range};\n'.encode()
                        device.write(cmd)

                    _, cmpl = get_tracked_value(self.i_cmpl_key)
                    _, V_0 = get_tracked_value(self.v_0_key)
                    _, V_1 = get_tracked_value(self.v_1_key)
                    _, N = get_tracked_value(self.measure_n)

                    self.settings.I_cmpl = cmpl
                    self.settings.V_0 = V_0
                    self.settings.V_1 = V_1
                    self.settings.N = N

                    print(N, V_0, V_1, cmpl, curr_range)

                    DIR = 'UP' if V_1 > V_0 else 'DOWN'
                    if DIR == 'DOWN':
                        V_1, V_0 = V_0, V_1
                    
                    MAX_T = 30
                    ARM_T = 0.01
                    TRIG_DELAY = 0.0
                    # Set to voltage source mode
                    cmd = b'SOUR:FUNC VOLT;'
                    # Set source voltage to 0V
                    cmd = cmd + f':SOUR:VOLT 0.000000;'.encode()
                    # Set Current compliance
                    cmd = cmd + f':CURR:PROT {cmpl:6f};'.encode()
                    # Add termination character
                    cmd = cmd + b'\n'
                    # Send command
                    device.write(cmd)

                    # Volt mode
                    cmd = b'SOUR:FUNC VOLT;'
                    # Start setting
                    cmd = cmd + f':SOUR:VOLT:STAR {V_0:.6f};'.encode()
                    # End setting
                    cmd = cmd + f':SOUR:VOLT:STOP {V_1:.6f};'.encode()
                    # Number of points
                    cmd = cmd + f':SOUR:SWE:POIN {N};'.encode()
                    # Sweep upwards
                    cmd = cmd + f':SOUR:SWE:DIR {DIR};'.encode()
                    # Linear spacing
                    cmd = cmd + b':SOUR:SWE:SPAC LIN;'
                    # Add termination character
                    cmd = cmd + b'\n'
                    # Send command
                    device.write(cmd)

                    # disable display
                    cmd = b':DISPlay:ENABle OFF;\n'
                    # Send command
                    device.write(cmd)
                    # Enable output
                    cmd = b'OUTP ON;\n'
                    # Send command
                    device.write(cmd)

                    # Arm for triggering
                    cmd = f':ARM:COUN 1;:TRIG:COUN {N};:SOUR:VOLT:MODE SWE;:SOUR:CURR:MODE SWE;\n'.encode()
                    # Send command
                    device.write(cmd)

                    # Setup triggering
                    cmd = f'ARM:SOUR IMM;:ARM:TIM {ARM_T:.6f};:TRIG:SOUR IMM;:TRIG:DEL {TRIG_DELAY:.6f};\n'.encode()
                    # Send command
                    device.write(cmd)

                    # Initiate measurement
                    cmd = b':TRIG:CLE;:INIT;\n'
                    # Send command
                    device.write(cmd)

                    # Now wait for OPC
                    cmd = b'*OPC?\n'
                    device.timeout = 0.25
                    time.sleep(ARM_T * N)
                    # Send command
                    device.write(cmd)
                    time.sleep(0.1)
                    resp = device.read_until("\r")
                    start = time.time()
                    while(resp.decode().strip() != "1") and time.time() - start < MAX_T:
                        device.write(cmd)
                        time.sleep(0.1)
                        resp = device.read_until("\r")
                    print("Ready")
                    time.sleep(0.1)

                    # enable display
                    cmd = b':DISPlay:ENABle ON;\n'
                    # Send command
                    device.write(cmd)
                    # Disable output
                    cmd = b'OUTP OFF;\n'
                    # Send command
                    device.write(cmd)
                    time.sleep(0.1)
                    
                    # Fetch data
                    cmd = b':FETC?\n'
                    device.timeout = 10
                    # Send command
                    device.write(cmd)
                    time.sleep(0.5)
                    resp = device.read_all()
                    if resp == b'1\r':
                        resp = b''
                    time.sleep(0.5)
                    while device.in_waiting:
                        read = device.read_all()
                        if read == b'1\r':
                            read = b''
                        resp = resp + read
                        time.sleep(0.5)
                    resp = resp.decode().replace('1\r', '').strip().split(',')

                    I_arr = []
                    V_arr = []
                    R_arr = []
                    T_arr = []
                    S_arr = []
                    try:
                        for i in range(0, len(resp), 5):
                            V_arr.append(float(resp[i + 0]))
                            I_arr.append(float(resp[i + 1]))
                            R_arr.append(float(resp[i + 2]))
                            T_arr.append(float(resp[i + 3]))
                            S_arr.append(float(resp[i + 4]))

                        V_arr = numpy.array(V_arr)
                        I_arr = numpy.array(I_arr)
                        self.plot_data = [V_arr, I_arr, I_arr, True, 0]

                        if self.do_log:
                            try:
                                filenme = self.get_log_file("IV_Curve")
                                with open(filenme, 'w') as file:
                                    file.write('Voltage (V)\tCurrent (A)\n')
                                    for i in range(len(V_arr)):
                                        file.write(f'{V_arr[i]:.6e}\t{I_arr[i]:.6e}\n')
                            except Exception as ferr:
                                print(f"Error writing log {ferr}")
                    except Exception as err:
                        print(len(resp), resp)
                        print(f"Error unpacking values: {err}")
                    print("Finished!")
            except Exception as err:
                print(err)
        
        with self.lock:
            if self.do_sweep:
                self.do_sweep = False
                self.set_unlocked_texture()
        time.sleep(0.25)
