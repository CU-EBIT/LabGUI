import nidaqmx
import time
import numpy as np

vfactor = 500
ifactor = 2.4

def calibration_curve(x,a,b):
    return a*x + b

output_calib = [
    (0.00201357,-0.04469823),
    (0.00333333, 0.00000000)
]
input_calib = [
    (500.19256377,10.26884113),
    (300.00000000,00.00000000)
]

current_scales = [
    1 / 2.4,
    1 / 2.4,
]

class GlassmanController:

    current_state = [0,0]
    digital_output = 0
    read_state = [0,0,0,0]
    read_timer = time.time() - 1
    in_ports = ["Dev2/ai0","Dev2/ai1","Dev2/ai2","Dev2/ai3"]
    out_ports = ["Dev2/ao0","Dev2/ao1"]
    dig_out_ports = ["Dev2/port1/line0:3"]
    class_samples = 256

    def __init__(self,port_in = in_ports,port_out = out_ports, dig_out_port=dig_out_ports) -> None:
        self.task_in = nidaqmx.Task("input_task")
        self.task_out = nidaqmx.Task("ao_task")
        self.task_out_d = nidaqmx.Task("do_task")
        from nidaqmx.constants import TerminalConfiguration
        for port in port_in:
            self.task_in.ai_channels.add_ai_voltage_chan(port, terminal_config=TerminalConfiguration.DIFF)
        for port in port_out:
            self.task_out.ao_channels.add_ao_voltage_chan(port)
        for port in dig_out_port:
            self.task_out_d.do_channels.add_do_chan(port)
        
    def __del__(self):
        self.task_in.close()
        self.task_out.close()
        self.task_out_d.close()

    def set_samples(self,samples):
        self.task_in.timing.cfg_samp_clk_timing(rate=25000,samps_per_chan=samples)
        self.class_samples = samples

    def toggle_HV(self,state,channel=0):
        channel = channel + 1 # Bits index from 1, not 0
        state_now = self.digital_output & channel
        enabled = state_now != 0
        # State now gives either 1 or 2 in this case, state is a boolean
        # not-0 is truthy, so below checks if they are the same truthness
        if enabled == state:
            return
        
        self.digital_output ^= channel
        print(self.digital_output)

        self.task_out_d.write([self.digital_output])
        self.task_out_d.stop()

    def set_voltage(self,voltage,channel=0):
        a, b = output_calib[channel]
        self.current_state[channel] = calibration_curve(voltage,a,b)
        self.task_out.write(self.current_state,auto_start=1)
        self.task_out.stop()

    def read(self):
        self.read_state = self.task_in.read(self.class_samples)
        self.read_timer = time.time()
        self.task_in.stop()
    def record(self,fac,index):
        if self.read_timer < time.time() - 0.005:
            self.read()
        return np.mean(self.read_state[index])/fac
    def read_v(self,channel=0,calibrated=True):
        v = self.record(1, channel*2)
        if not calibrated:
            return v
        a, b = input_calib[channel]
        return calibration_curve(v, a, b)
    def read_i(self,channel=0):
        return self.record(current_scales[channel],channel*2+1)    

def reject_outliers_2d(xdata,ydata,r = 2):

    sd = np.std(ydata)
    m = np.mean(ydata)

    i = 0
    while i < len(xdata):
        if ((ydata[i] > (m + r*sd)) or (ydata[i] < (m - r*sd))): 
            xdata = np.delete(xdata,[i])
            ydata = np.delete(ydata,[i])
        else:
            i += 1
    
    return xdata,ydata

def test_sweep():
    controller = GlassmanController()
    controller.toggle_HV(1)
    time.sleep(.1)
    controller.set_voltage(0)

    for i in range(10):
        controller.set_voltage(i * 100)
        time.sleep(0.1)
        feedback_v = controller.read_v()
        time.sleep(0.1)
        feedback_i = controller.read_i()
        print(feedback_v, feedback_i)
        time.sleep(2)

    for i in range(10, 0, -1):
        controller.set_voltage(i * 100)
        time.sleep(0.1)
        feedback_v = controller.read_v()
        time.sleep(0.1)
        feedback_i = controller.read_i()
        print(feedback_v, feedback_i)
        time.sleep(2)
        
    controller.set_voltage(0)
    time.sleep(.1)
    controller.toggle_HV(0)
    time.sleep(.1)

def calibrate_feedback(report_calibrated = True):

    import matplotlib.pyplot as plt
    from scipy.optimize import curve_fit
    import serial

    controller = GlassmanController()
    ser = serial.Serial('COM1', 9600, timeout=2)

    def tx(command):
        ser.write(str.encode(command+'\n'))
    tx(f'TRIG:COUN 1')
    tx(f'SYST:REM')
    controller.toggle_HV(1)
    time.sleep(0.1)
    controller.set_voltage(0)
    time.sleep(3)

    measured = np.zeros(100)
    feedback_v = np.zeros(100)

    for i in range(100):

        controller.set_voltage(50*i)
        time.sleep(2)

        tx('READ?')
        multimeter = float(ser.readline().decode().strip()) * 1000

        V = controller.read_v(report_calibrated)
        print(f'{multimeter:.2f}, {V:.2f}, {report_calibrated}')

        measured[i] = multimeter
        feedback_v[i] = V

        time.sleep(0.1) 

    controller.set_voltage(0)
    controller.toggle_HV(0)
    
    pars, _ = curve_fit(calibration_curve,feedback_v,measured,(0,1))

    plt.scatter(feedback_v,measured)
    plt.plot(feedback_v,calibration_curve(feedback_v,*pars))
    plt.xlabel("Feedback Voltage (V)")
    plt.ylabel("Measured Voltage (multimeter) (V)")
    print(pars)

    plt.show()

def calibrate_applied(set_calibrated = True):

    import matplotlib.pyplot as plt
    from scipy.optimize import curve_fit

    import serial
    controller = GlassmanController()
    ser = serial.Serial('COM1', 9600, timeout=2)
    def tx(command):
        ser.write(str.encode(command+'\n'))

    controller.toggle_HV(1)
    time.sleep(0.1)
    controller.set_voltage(0)
    time.sleep(3)

    measured = np.zeros(100)
    feedback_v = np.zeros(100)

    for i in range(100):

        if set_calibrated:
            set_V = 50 * i
            controller.set_voltage(set_V)
        else:
            set_V = i / 10.
            controller.set_voltage(set_V, 1, 0)

        time.sleep(2)

        tx('READ?')
        multimeter = float(ser.readline().decode().strip()) * 1000

        V = set_V
        print(multimeter, V)

        measured[i] = multimeter
        feedback_v[i] = V

        time.sleep(0.1) 

    pars, _ = curve_fit(calibration_curve,measured,feedback_v,(0,1))

    controller.set_voltage(0)
    controller.toggle_HV(0)
    plt.scatter(feedback_v,measured)
    plt.plot(feedback_v,calibration_curve(feedback_v,*pars))
    plt.xlabel("Feedback Voltage (V)")
    plt.ylabel("Measured Voltage (multimeter) (V)")
    print(pars)

    plt.show()

def leakage_test(voltage,t=60,sample_rate=0.5):

    import matplotlib.pyplot as plt
    import serial

    controller = GlassmanController()

    controller.toggle_HV(1)

    for i in np.arange(0,voltage,100):
        time.sleep(0.5)
        controller.set_voltage(i)
    
    time.sleep(0.5)

    controller.set_voltage(voltage)

    time.sleep(5)

    print("Ramp Complete")

    ser = serial.Serial('COM1', 9600, timeout=2)
    def tx(command):
        ser.write(str.encode(command+'\n'))
    
    

    counts = 0
    datax = []
    datay = []

    for i in np.arange(0,t,sample_rate):
        tx('READ?')
        sample = float(ser.readline().decode().strip())*1000

        if(sample < 10000):
            print(sample,controller.read_v())
            datay.append(sample)
        else:
            print(f'{sample:.5f} (Overload)')
            datay.append(0)
        datax.append(i)

        time.sleep(sample_rate)
        if(sample < -750):
            counts += 1
    
    print(f'Counts: {counts}')

    controller.toggle_HV(0)

    plt.scatter(datax,datay)
    plt.xlabel("Time (s)")
    plt.ylabel("Current (pA)")
    plt.show()

def arcing_test(voltage,sample_rate=0.1,save=True):
    import serial
    import os

    controller = GlassmanController()

    controller.toggle_HV(1)

    for i in np.arange(0,voltage,100):
        time.sleep(0.5)
        controller.set_voltage(i)
    
    time.sleep(0.5)

    controller.set_voltage(voltage)

    time.sleep(5)

    print("Ramp Complete")

    print(controller.read_v())

    ser = serial.Serial('COM1', 9600, timeout=2)
    def tx(command):
        ser.write(str.encode(command+'\n'))

    tx('SYST:RMT')

    counts = 0
    datax = []
    datay = []

    if save:
        subdir = time.strftime("%Y-%m-%d")
        dir = os.path.join("../sweeps/",subdir)
        if not os.path.exists(dir):
            os.makedirs(dir)
    
        filename = f'arcing-test_{time.strftime("%H-%M-%S")}.log'
        filename = os.path.join(dir,filename)
        file = open(filename,'w')
    
    counts = 0

    while True:

        try:       
            i = controller.read_i()
            v = controller.read_v()

            print(i,v)
            if save:
                file.write(f'{i:.3f}\t{v:.3f}\n')
            
            if(i > 0.15 or i < -.15):
                counts += 1

            time.sleep(sample_rate)
        except KeyboardInterrupt:
            break

    controller.toggle_HV(0)
    if save:
        file.write(f'Counts: {counts}\n')
        file.close()
    print(f'\nCounts: {counts}')

def settle_test(voltage, step):    
    controller = GlassmanController()
    controller.toggle_HV(1)
    controller.set_voltage(voltage)
    time.sleep(10)
    for i in range(voltage, 0, -step):
        controller.set_voltage(i)
        start = time.time() + 1
        while(time.time() < start):
            print(controller.read_v(), time.time())

def run_controller():
    controller = GlassmanController()
    controller.toggle_HV(1)
    while True:
        try: 
            voltage = float(input("Enter Voltage: "))
            controller.set_voltage(voltage)
        except KeyboardInterrupt:
            break
    controller.toggle_HV(0)
    del controller

if __name__ == "__main__":
    run_controller()