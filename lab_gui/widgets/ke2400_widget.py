import threading
import serial
import time

import numpy

# QT Widgets
from ..utils.qt_helper import *

from .device_widget import DeviceReader
from .plot_widget import Plot
from .base_control_widgets import SingleInputWidget, SubControlWidget, ValuesAndPower, make_client, try_init_value, get_tracked_value, _red_, _green_

from ..modules.module import BetterAxisItem

class KE2400Mode(SubControlWidget):
    def __init__(self, parent, name, label='', add_to_frame=True, **kargs):
        super().__init__(**kargs)
        self.parent = parent
        self.client = self.parent.client
        
        # Make the controls for sweeping
        # IV Curve controls
        self.outer_layout = QVBoxLayout()
        self.outer_layout.setSpacing(0)
        self.inner_layout = QHBoxLayout()
        self.inner_layout.setSpacing(0)

        if add_to_frame:
            self.frame.setLayout(self.outer_layout)
            self.dock.setTitle(name)

        self.active = False

        self.active_btn = QCheckBox("Active")
        header = QHBoxLayout()
        header.addWidget(QLabel(label))
        header.addWidget(self.active_btn)
        self.outer_layout.addLayout(header)

        self.active_btn.clicked.connect(self.activate)

    def set_locked_texture(self, button):
        button.setStyleSheet(f"background-color : {_red_}")

    def set_unlocked_texture(self, button):
        button.setStyleSheet(f"background-color : {_green_}")

    def on_deactivate(self):
        self.active_btn.setChecked(False)
        self.active = False

    def on_activate(self):
        self.active_btn.setChecked(True)
        self.active = True

    def activate(self):
        for mode in self.parent.modes:
            if mode is not self and mode.is_active():
                mode.on_deactivate()
        self.on_activate()

    def is_active(self):
        return self.active

    def reset_setup(self):
        # Reset and clear
        cmd = b'*RST;'
        cmd = cmd + b'*ESE 1;'
        cmd = cmd + b'*CLS;'
        cmd = cmd + b':SYST:CLE;'
        cmd = cmd + b':TRAC:CLE;'
        cmd = cmd + b':SYST:PRES'
        cmd = cmd + b'\n'
        self.parent.device.write(cmd)

class IVCurveWidget(KE2400Mode):
    def __init__(self, parent, name, **kargs):
        super().__init__(parent, f"{name} IV Curve", label="Sweep Control", **kargs)

        self.i_cmpl_key = f'{name}_I_Compl'
        self.v_0_key = f'{name}_V_0'
        self.v_1_key = f'{name}_V_1'
        self.measure_n = f'{name}_N'

        try_init_value(self.i_cmpl_key, 1e-1)
        try_init_value(self.v_0_key, -10)
        try_init_value(self.v_1_key, 10)
        inited = try_init_value(self.measure_n, 100)

        for key, value in kargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.do_sweep = False
        def apply():
            if self.parent.paused:
                return
            with self.parent.lock:
                self.set_locked_texture(self.applyBtn)
                self.do_sweep = True

        self.applyBtn = QPushButton("Apply")
        self.applyBtn.clicked.connect(apply)
        self.set_unlocked_texture(self.applyBtn)

        line = SingleInputWidget(self, self.i_cmpl_key, "{:.2e}")
        self.inner_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.v_0_key, "{:.2f}")
        self.inner_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.v_1_key, "{:.2f}")
        self.inner_layout.addWidget(line)
        self._modules.append(line)
        line = SingleInputWidget(self, self.measure_n, "{}", typing=int)
        self.inner_layout.addWidget(line)
        self._modules.append(line)
        self.file_key = QLineEdit("IV_Curve")
        self.inner_layout.addWidget(self.file_key)

        self.inner_layout.addWidget(self.applyBtn)
        self.inner_layout.addStretch(0)

        self.outer_layout.addLayout(self.inner_layout)

    def frame_size(self):
        self.resize(400, 52)
    
    def on_deactivate(self):
        self.do_sweep = False
        super().on_deactivate()

    def on_run_loop(self):
        
        with self.parent.lock:
            try:
                if self.do_sweep:
                    device = self.parent.device
                    self.settings = self.parent.settings
                    
                    self.reset_setup()

                    # Auto range for voltage and current
                    cmd = b':SOUR:VOLT:RANG:AUTO ON\n'
                    device.write(cmd)
                    cmd = b':SENS:CURR:RANG:AUTO ON\n'
                    device.write(cmd)

                    if isinstance(self.settings.i_rang, str):
                        curr_range = self.settings.i_rang.upper()
                    else:
                        curr_range = self.settings.i_rang

                    _, cmpl = get_tracked_value(self.i_cmpl_key)
                    _, V_0 = get_tracked_value(self.v_0_key)
                    _, V_1 = get_tracked_value(self.v_1_key)
                    _, N = get_tracked_value(self.measure_n)

                    self.settings.I_cmpl = cmpl
                    self.settings.V_0 = V_0
                    self.settings.V_1 = V_1
                    self.settings.N = N

                    self.parent.saver.save(True)

                    if curr_range != 'AUTO':
                        curr_range = float(curr_range)
                        cmd = b':SENS:CURR:RANG:AUTO OFF\n'
                        device.write(cmd)
                        cmd = f':SENS:CURR:PROT {curr_range:.0E}\n'.encode()
                        device.write(cmd)
                        cmd = f':SENS:CURR:RANG {curr_range:.0E}\n'.encode()
                        device.write(cmd)
                    else:
                        cmd = f':SENS:CURR:PROT {cmpl:.0E}\n'.encode()
                        device.write(cmd)

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
                    # Add termination character
                    cmd = cmd + b'\n'
                    # Send command
                    device.write(cmd)

                    # Volt mode
                    cmd = b'SOUR:FUNC VOLT;'
                    # Start setting
                    cmd = cmd + f':SOUR:VOLT:STAR {V_0:.3e};'.encode()
                    # End setting
                    cmd = cmd + f':SOUR:VOLT:STOP {V_1:.3e};'.encode()
                    # Number of points
                    cmd = cmd + f':SOUR:SWE:POIN {N};'.encode()
                    # Sweep upwards
                    cmd = cmd + f':SOUR:SWE:DIR {DIR};'.encode()
                    # Linear spacing
                    cmd = cmd + b':SOUR:SWE:SPAC LIN'
                    # Add termination character
                    cmd = cmd + b'\n'
                    # Send command
                    device.write(cmd)

                    # disable display
                    cmd = b':DISPlay:ENABle OFF\n'
                    # Send command
                    # device.write(cmd)
                    # Enable output
                    cmd = b'OUTP ON\n'
                    # Send command
                    device.write(cmd)

                    # Arm for triggering
                    cmd = f':ARM:COUN 1;:TRIG:COUN {N};:SOUR:VOLT:MODE SWE;:SOUR:CURR:MODE SWE\n'.encode()
                    # Send command
                    device.write(cmd)

                    # Setup triggering
                    cmd = f'ARM:SOUR IMM;:ARM:TIM {ARM_T:.6f};:TRIG:SOUR IMM;:TRIG:DEL {TRIG_DELAY:.6f}\n'.encode()
                    # Send command
                    device.write(cmd)

                    # Initiate measurement
                    cmd = b':TRIG:CLE;:INIT\n'
                    # Send command
                    device.write(cmd)
                    
                    cmd = b':SYST:ERR?\n'
                    device.write(cmd)
                    time.sleep(0.1)
                    err = device.read_all().decode().strip()
                    cmd = b'*STB?\n'
                    device.write(cmd)
                    time.sleep(0.1)
                    stb = device.read_all().decode().strip()
                    if (stb != "0" and stb != ''):
                        print("Errored!")
                        cmd = b':SYST:ERR?\n'
                        device.write(cmd)
                        time.sleep(0.1)
                        err = device.read_all().decode().strip()
                        print(":SYST:ERR: ", err)
                        cmd = b'*ESR?\n'
                        device.write(cmd)
                        time.sleep(0.1)
                        err = device.read_all().decode().strip()
                        print("*ESR ", err)
                        time.sleep(0.1)
                        # enable display
                        cmd = b':DISPlay:ENABle ON\n'
                        # Send command
                        device.write(cmd)
                        # Disable output
                        cmd = b'OUTP OFF\n'
                        # Send command
                        device.write(cmd)
                    else:
                        # Now wait for OPC
                        cmd = b'*OPC?\n'
                        device.timeout = 0.25
                        # Send command
                        device.write(cmd)
                        time.sleep(0.1)
                        resp = device.read_until("\r")
                        start = time.time()
                        while(resp.decode().strip() != "1") and time.time() - start < MAX_T and self.active:
                            time.sleep(0.1)
                            resp = device.read_until("\r")
                        print("Ready")
                        time.sleep(0.1)

                        # enable display
                        cmd = b':DISPlay:ENABle ON\n'
                        # Send command
                        device.write(cmd)
                        # Disable output
                        cmd = b'OUTP OFF\n'
                        # Send command
                        device.write(cmd)
                        time.sleep(0.1)

                        if self.active:
                        
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
                            while device.in_waiting and self.active:
                                read = device.read_all()
                                if read == b'1\r':
                                    read = b''
                                resp = resp + read
                                time.sleep(0.5)
                            if self.active:
                            
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
                                    self.parent.plot_data = [V_arr, I_arr, I_arr, True, 0]

                                    if self.parent.do_log:
                                        try:
                                            filenme = self.parent.get_log_file(self.file_key.text())
                                            with open(filenme, 'w') as file:
                                                file.write('Voltage (V)\tCurrent (A)\tTime (s)\n')
                                                for i in range(len(V_arr)):
                                                    file.write(f'{V_arr[i]:.6e}\t{I_arr[i]:.6e}\t{T_arr[i]:.6e}\n')
                                        except Exception as ferr:
                                            print(f"Error writing log {ferr}")
                                except Exception as err:
                                    print(len(resp), resp)
                                    print(f"Error unpacking values: {err}")
                                print("Finished!")
                    self.reset_setup()
            except Exception as err:
                print(err)
        
        with self.parent.lock:
            if self.do_sweep:
                self.do_sweep = False
                self.set_unlocked_texture(self.applyBtn)
        time.sleep(0.25)

class MeasureCurrentWidget(KE2400Mode):
    def __init__(self, parent, name, **kargs):
        super().__init__(parent, f'{name} Measure Current', label="Voltage Control",  **kargs)

        self.V_On = f'{name}_Voltage_Power'
        self.V_Set = f'{name}_Voltage_Set'
        self.I_Read = f'{name}_Current_Read'

        self.was_active = try_init_value(self.V_On, False)
        self.last_V_Set = try_init_value(self.V_Set, 0.0)
        try_init_value(self.I_Read, 0.0)

        self.V_line = ValuesAndPower(self, self.V_On, self.V_Set, self.I_Read, None, "{:.3f}", "{:.2e} A", None, [f"V", f"I"])
        self._modules.append(self.V_line)

        self.outer_layout.addLayout(self.V_line._layout)

    def on_run_loop(self):
        _, active = get_tracked_value(self.V_On)
        device = self.parent.device
        _, V_Set = get_tracked_value(self.V_Set)
        if active != self.was_active:
            self.was_active = active
            if active:
                self.reset_setup()
                # Set to voltage source mode
                cmd = b'SOUR:FUNC VOLT;'
                # Set source voltage to 0V
                cmd = cmd + f':SOUR:VOLT 0.000000;'.encode()
                # Set source voltage to fixed
                cmd = cmd + b':SOUR:VOLT:MODE FIX;'
                # Add termination character
                cmd = cmd + b':TRIG:COUN 1;\n'
                # Send command
                device.write(cmd)

                cmd = cmd + b':SENS:FUNC CURR\n'
                # Send command
                device.write(cmd)

                self.settings = self.parent.settings

                if isinstance(self.settings.i_rang, str):
                    curr_range = self.settings.i_rang.upper()
                else:
                    curr_range = self.settings.i_rang

                self.parent.saver.save(True)

                if curr_range != 'AUTO':
                    curr_range = float(curr_range)
                    cmd = b':SENS:CURR:RANG:AUTO OFF\n'
                    device.write(cmd)
                    cmd = f':SENS:CURR:PROT {curr_range:.0E}\n'.encode()
                    device.write(cmd)
                    cmd = f':SENS:CURR:RANG {curr_range:.0E}\n'.encode()
                    device.write(cmd)
                else:
                    cmd = f':SENS:CURR:PROT {self.settings.I_cmpl:.0E}\n'.encode()
                    device.write(cmd)

                self.last_V_Set = V_Set
                cmd = f':SOUR:VOLT:LEV {V_Set:.6f}\n'.encode()
                device.write(cmd)

                # Enable output
                cmd = b'OUTP ON\n'
                # Send command
                device.write(cmd)
            else:
                # Disable output
                cmd = b'OUTP OFF\n'
                # Send command
                device.write(cmd)
                self.reset_setup()

        if not active:
            time.sleep(0.25)
        else:
            if self.last_V_Set != V_Set:
                cmd = f':SOUR:VOLT:LEV {V_Set:.6f}\n'.encode()
                device.write(cmd)
                self.last_V_Set = V_Set
            cmd = b'READ?\n'
            device.write(cmd)
            time.sleep(0.05)
            data = device.read_until("\r").decode().strip()
            try:
                I = float(data.split(',')[1])
                if abs(I) < 2:
                    self.client.set_float(self.I_Read, I)
                else:
                    print(f"Error with current: {I}")
            except:
                print(data)

    def frame_size(self):
        self.V_line.set_label_sizes(3, 9, 12, 12)
        self.resize(400, 52)

class KE2400(DeviceReader):
    def __init__(self, parent, port, baudrate=9600, name="KE2400", **args):

        self.i_cmpl_key = f'{name}_I_Compl'
        self.v_0_key = f'{name}_V_0'
        self.v_1_key = f'{name}_V_1'
        self.measure_n = f'{name}_N'

        self.baudrate = baudrate
        self.port = port
        self.lock = threading.Lock()

        for key, value in args.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.client = make_client()
        self.client.set_float(self.i_cmpl_key, 1e-1)
        self.client.set_float(self.v_0_key, -10)
        self.client.set_float(self.v_1_key, 10)
        self.client.set_int(self.measure_n, 100)
        
        super().__init__(parent, name=name, **args)
        
        self.modes = []

        mode = IVCurveWidget(self, name)
        self._modules.append(mode)
        self.modes.append(mode)
        mode = MeasureCurrentWidget(self, name)
        self._modules.append(mode)
        self.modes.append(mode)

    def post_added_to_dockarea(self):
        module = None
        print("Adding sub docks")
        for mode in self.modes:
            if module is None:
                self.parent.plot_widget.addDock(mode.dock, 'top', self.dock)
            else:
                self.parent.plot_widget.addDock(mode.dock, 'above', module.dock)
            module = mode
        self.modes[0].dock.raiseDock()
        self.modes[0].activate()

    def collect_saved_values(self, values):
        return super().collect_saved_values(values)

    def process_load_saved(self):
        self.client.set_float(self.i_cmpl_key, self.settings.I_cmpl)
        self.client.set_float(self.v_0_key, self.settings.V_0)
        self.client.set_float(self.v_1_key, self.settings.V_1)
        self.client.set_int(self.measure_n, self.settings.N)
        return super().process_load_saved()

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
        self.settings._names_['i_rang'] = 'Current Range: '
        self.settings._opt_fmts_['i_rang'] = '{}'
        self.settings._opt_ufmts_ = {}
        self.settings._opt_ufmts_['i_rang'] = lambda x:x
        self.settings.log_scale = False

        try:
            print("Making settings")
            _, self.settings.I_cmpl = get_tracked_value(self.i_cmpl_key)
            _, self.settings.V_0 = get_tracked_value(self.v_0_key)
            _, self.settings.V_1 = get_tracked_value(self.v_1_key)
            _, self.settings.N = get_tracked_value(self.measure_n)
            self.settings.i_rang = "Auto"
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
            self.device = serial.Serial(self.port, baudrate=self.baudrate, timeout=0.25)
            # _write = self.device.write
            # def wrap(cmd):
            #     _write(cmd)
            #     print(cmd)
            # self.device.write = wrap
            self.device.flush()
            self.device.write(b"*IDN?\n")
            time.sleep(0.1)
            idn = self.device.read_all().decode().strip()
            print(idn)
            if not idn.startswith('KEITHLEY INSTRUMENTS INC.,MODEL 24'):
                print(f"Wrong device on {self.port}, expected a KEITHLEY INSTRUMENTS INC.,MODEL 24, got {idn}")
                self.device = None
                return False
            
            cmd = b'*RST;'
            cmd = cmd + b'*ESE 1;'
            cmd = cmd + b'*CLS;'
            cmd = cmd + b':SYST:CLE;'
            cmd = cmd + b':SYST:PRES;'
            cmd = cmd + b'\n'
            self.device.write(cmd)

            self.valid = True
        except Exception as err:
            print(err)
            print('error opening KE2400?')
            self.device = None
        return self.device != None
    
    def do_device_update(self):
        for mode in self.modes:
            if mode.is_active():
                mode.on_run_loop()
                break
