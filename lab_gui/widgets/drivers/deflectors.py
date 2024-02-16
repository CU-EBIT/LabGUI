import serial
import numpy as np
from scipy.interpolate import CubicSpline
import time

adc_map = {0:'a', 1:'b', 2:'c', 3:'d', 4:'e', 5:'f', 6:'g', 7:'h'}

def setXV(df, vx):
    print(f"Trying to set X {vx}")
    print(df.set_pair(0, vx))

def setYV(df, vy):
    print(f"Trying to set Y {vy}")
    print(df.set_pair(1, vy))
    
def setXV_2(df, vx):
    print(f"Trying to set X {vx}")
    print(df.set_pair(2, vx))

def setYV_2(df, vy):
    print(f"Trying to set Y {vy}")
    print(df.set_pair(3, vy))

class DeflectorSupply:
    
    def __init__(self):
        self.ser = None
        
        #calibration bit value sent with 'set_dac_bit'
        self.bcalset = [0,5000,32768,65535] 
        
        #calibration voltage corresponding to 'bcalset' read with Keithley
        self.calvolt = np.array([[.52,.21,.35,.28,.43,.25,.41,.44],
            [38.74,38.60,38.38,38.56,38.56,38.73,38.82,38.58],
            [251.74,252.04,251.46,251.12,251.73,252.42,252.09,251.90],
            [502.98,503.83,502.81,501.88,503.16,504.48,503.67,503.56]])
        
        self.dacspline = [CubicSpline(self.calvolt[:,0],self.bcalset),
        CubicSpline(self.calvolt[:,1],self.bcalset),
        CubicSpline(self.calvolt[:,2],self.bcalset),
        CubicSpline(self.calvolt[:,3],self.bcalset),
        CubicSpline(self.calvolt[:,4],self.bcalset),
        CubicSpline(self.calvolt[:,5],self.bcalset),
        CubicSpline(self.calvolt[:,6],self.bcalset),
        CubicSpline(self.calvolt[:,7],self.bcalset)]
        
    def open(self, com_port):
        self.ser = serial.Serial(com_port, 123, timeout=0.01)

    def close(self):
        self.ser.close()
        
    def write(self, cmd):
        self.ser.write(str.encode(cmd+'\n'))
        self.ser.flushOutput()
        
    def read(self):
        return self.ser.readline().decode().strip()
        
    def power_down_all(self):
        self.write('8')
        return self.read()
    
    def dac_bit2v(self, id, bval):
        pass
        
    def set_dac(self, id, val):
        if val<1:
            bval = 0
            self.write(f'D{id}{int(bval)}')
            self.read()
            return f'Value < 1V, set to 0 bit ({self.calvolt[0,id]} V min on this channel)'
        elif val>500:
            bval = 65535
            self.write(f'D{id}{int(bval)}')
            self.read()
            return f'Value > 500V, set to max bit'
        else:
            set = int(self.dacspline[id](val))
            self.write(f'D{id}{set}')
            self.read()
            return f'set dac to {val}V ({set})'
            # return f'DAC {out[0]} set to {val}V ({out[1:]} bit)'
    
    def set_dac_bit(self, id, bval):
        self.write(f'D{id}{int(bval)}')
        out = self.read()
        return f'DAC {out[0]} set to {out[1:]} bits'
    
    def read_adc(self, id):
        self.write(adc_map[id])
        return self.read()

    def set_pair(self, id, value):
        id_0 = id*2
        id_1 = id*2 + 1
        var = self.set_dac(id_0, value)
        time.sleep(0.01)
        var = var + '\n'+ self.set_dac(id_1, value)
        time.sleep(0.01)
        self.set_dac(id_0, value)
        time.sleep(0.01)
        self.set_dac(id_1, value)
        return var

if __name__ == "__main__":
    device = DeflectorSupply()
    device.open('COM10')
    for i in np.arange(0,10,0.5):
        print(f'Setting {i}')
        device.set_pair(1, i)
        if i < 5:
            time.sleep(0.1)
        time.sleep(0.1)
    for i in np.arange(11,0,-0.5):
        print(f'Setting {i}')
        device.set_pair(1, i)
        if i < 5:
            time.sleep(0.1)
        time.sleep(0.1)
    print('powering down')
    print(device.power_down_all())

'''
    for i in range(8):
        print(device.set_dac_bit(i,0))
    for i in range(8):   
        print(device.read_adc(i))
'''
    