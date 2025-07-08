import spidev
import time
import numpy
import threading

class FloatCache:
    def __init__(self, size):
        self.cache_size = size
        self.n = 0
        self.cache = [0.0 for _ in range(self.cache_size)]
        self.V_sum = 0.0
        self.V = 0.0
        self.fails = 0

    def get_value(self):
        return self.V
    
    def update(self, value, validate=False, min_std=1):
        if self.cache_size <= 1:
            self.V = value
            return True
        N = self.cache_size
        N_i = min(self.n+1, N)
        if N_i == N and validate and self.fails < 20:
            std = max(numpy.std(self.cache), min_std)
            mean = self.V - value
            self.fails += 1
            if abs(mean - std) > 2*std:
                print("Too much variance", mean, std)
                return False
        self.V_sum -= self.cache[self.n%N]
        self.cache[self.n%N] = value
        self.V_sum += value
        self.n = self.n + 1
        self.V = self.V_sum / N_i
        self.fails = 0
        return True

class MAX6675:
    def __init__(self, bus, addr, auto_run=True, cache_size=8):
        self.dev = spidev.SpiDev(bus, addr)
        # Set speed to ensure full data is read
        self.dev.max_speed_hz = 2500000
        self.auto_run = auto_run
        # Cache T for averaging
        self.T_cache = FloatCache(cache_size)
        self.last_measure = 0
        self.lock = threading.Lock()
        self.running = False
        if auto_run:
            self.running = True
            def loop():
                while self.running:
                    t = time.time()
                    v = self._measure()
                    with self.lock:
                        if self.T_cache.update(v, validate=True, min_std=3):
                            self.last_measure = time.time()
                    dt = time.time() - t
                    # takes 220ms to do a full conversion according to docs
                    if dt < 0.25:
                        time.sleep(0.25 - dt)
            self.run_thread = threading.Thread(target=loop, daemon=True)
            self.run_thread.start()
        
    def __del__(self):
        # exit run thread if it is present
        if hasattr(self, 'run_thread') and self.running:
            self.running = False
            self.run_thread.join()

        # close this if we opened it before
        if hasattr(self, 'dev'):
            self.dev.close()

    def _measure(self):
        vals = self.dev.readbytes(2)
        v = vals[0] << 8 | vals[1]
        # this bit is D3 in documentation
        # if it is high, it means open circuit
        if v & 0x4:
            return float('NaN')
        # bottom 3 bits are: sign (always 0 according to docs), valid, id
        v >>= 3
        # output is a short containing 4x t in C, starting at 0
        return v*0.25

    def get_temperature(self):
        if self.auto_run:
            with self.lock:
                return self.T_cache.get_value()
        t = time.time()
        if t - self.last_measure >= 0.22:
            self.T_cache.update(self._measure())
            self.last_measure = t
        return self.T_cache.get_value()
        
if __name__ == "__main__":
    from datetime import datetime
    device = MAX6675(0,0)
    while True:
        try:
            print(device.get_temperature(), datetime.fromtimestamp(device.last_measure))
            time.sleep(0.5)
        except KeyboardInterrupt:
            break
