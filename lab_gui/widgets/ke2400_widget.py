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
    def __init__(self, parent, port, name="KE2400", **args):
        super().__init__(parent, name=name, **args)

        self.i_cmpl_key = f'{name}_I_Compl'
        self.v_0_key = f'{name}_V_0'
        self.v_1_key = f'{name}_V_1'
        self.measure_n = f'{name}_N'

        self.port = port

        for key, value in args.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.client = BaseDataClient()
        self.client.set_float(self.i_cmpl_key, 1e-1)
        self.client.set_float(self.v_0_key, -10)
        self.client.set_float(self.v_1_key, 10)
        self.client.set_int(self.measure_n, 100)

        # Time domain controls
        time_outer = QVBoxLayout()
        time_outer.setSpacing(0)
        time_layout = QHBoxLayout()
        time_layout.setSpacing(0)

        self.do_sweep = False
        self.lock = threading.Lock()
        def apply():
            with self.lock:
                self.set_locked_texture()
                self.do_sweep = True

        self.applyBtn = QPushButton("Apply")
        self.applyBtn.clicked.connect(apply)
        self.set_unlocked_texture()

        line = SingleInputWidget(self, self.i_cmpl_key, "{:.2e}")
        time_layout.addWidget(line)
        line = SingleInputWidget(self, self.v_0_key, "{:.2f}")
        time_layout.addWidget(line)
        line = SingleInputWidget(self, self.v_1_key, "{:.2f}")
        time_layout.addWidget(line)
        line = SingleInputWidget(self, self.measure_n, "{}")
        time_layout.addWidget(line)

        time_layout.addWidget(self.applyBtn)
        time_layout.addStretch(0)

        time_outer.addWidget(QLabel("Time Range Control"))
        time_outer.addLayout(time_layout)
        
        self._layout.addLayout(time_outer)


    def set_locked_texture(self):
        # icon = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
        # self.applyBtn.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.applyBtn.setStyleSheet(f"background-color : {_red_}")

    def set_unlocked_texture(self):
        # icon = QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning
        # self.applyBtn.setIcon(QtWidgets.QApplication.style().standardIcon(icon))
        self.applyBtn.setStyleSheet(f"background-color : {_green_}")

    def make_plot(self):
        self.plot_widget = Plot(x_axis=BetterAxisItem('bottom'))
        self.plot_widget.cull_x_axis = False
        self.plot_widget.show_avg = False
        self.plot_widget.label_x = "Voltage (V)"

    def set_data_key(self, _):

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
            self.device = serial.Serial(self.port)
            self.device.write(b"*IDN?\n")
            self.device.timeout = 0.25
            idn = self.device.read_until(b'\r').decode().strip()
            if not idn.startswith('KEITHLEY INSTRUMENTS INC.,MODEL 24'):
                print(f"Wrong device on {self.port}, expected a KEITHLEY INSTRUMENTS INC.,MODEL 24")
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
            if self.do_sweep:
                device = self.device
                
                # Auto range for voltage and current
                cmd = b':VOLT:RANG:AUTO ON;\n'
                device.write(cmd)
                cmd = b':CURR:RANG:AUTO ON;\n'
                device.write(cmd)

                _, cmpl = get_tracked_value(self.i_cmpl_key)
                _, V_0 = get_tracked_value(self.v_0_key)
                _, V_1 = get_tracked_value(self.v_1_key)
                _, N = get_tracked_value(self.measure_n)
                
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
                cmd = cmd + b':SOUR:SWE:DIR UP;'
                # Linear spacing
                cmd = cmd + b':SOUR:SWE:SPAC LIN;'
                # Add termination character
                cmd = cmd + b'\n'
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

                # Disable output
                cmd = b'OUTP OFF;\n'
                # Send command
                device.write(cmd)
                
                # Fetch data
                cmd = b':FETC?\n'
                device.timeout = 10
                # Send command
                device.write(cmd)
                resp = device.read_all()
                time.sleep(0.1)
                while device.in_waiting:
                    resp = resp + device.read_all()
                    time.sleep(0.1)
                resp = resp.decode().strip().split(',')

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
                    I_arr = numpy.array(V_arr)
                    self.plot_data = [V_arr, I_arr, I_arr, True, 0]
                except Exception as err:
                    print(len(resp), resp)
                    print(f"Error unpacking values: {err}")
                print("Finished!")

                self.do_sweep = False
                self.set_unlocked_texture()
        time.sleep(0.25)
