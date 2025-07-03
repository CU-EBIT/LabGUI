import spidev
import time
import threading

class FloatCache:
    def __init__(self, size):
        self.cache_size = size
        self.n = 0
        self.cache = [0.0 for _ in range(self.cache_size)]
        self.V_sum = 0.0
        self.V = 0.0

    def get_value(self):
        return self.V
    
    def update(self, value):
        if self.cache_size <= 1:
            self.V = value
            return
        self.cache[self.n%self.cache_size] = value
        self.n = self.n + 1
        self.V_sum -= self.cache[self.n%self.cache_size]
        self.V_sum += value
        self.V = self.V_sum / (min(self.n, self.cache_size-1))

class MAX6675:
    def __init__(self, bus, addr, auto_run=True, cache_size=4):
        self.dev = spidev.SpiDev(bus, addr)
        self.auto_run = auto_run
        self.T_cache = FloatCache(cache_size)
        self.lock = threading.Lock()
        self.running = False
        if auto_run:
            self.running = True
            def loop():
                while self.running:
                    v = self._measure()
                    with self.lock:
                        self.T_cache.update(v)
                    time.sleep(0.2)
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
        # output is a short containing 4x t in C, starting at 0
        # struct.unpack('>h', bytes(vals))[0]

        # below is without the wrapped call to struct
        return ((vals[0]>>4)|vals[1])*0.25

    def get_temperature(self):
        if self.auto_run:
            with self.lock:
                return self.T_cache.get_value()
        t = time.time()
        if t - self.last_measure > 0.2:
            self.T_cache.update(self._measure())
            self.last_measure = t
        return self.T_cache.get_value()
        
if __name__ == "__main__":
    device = MAX6675(0,0)
    while True:
        try:
            print(device.get_temperature())
            time.sleep(0.5)
        except KeyboardInterrupt:
            break