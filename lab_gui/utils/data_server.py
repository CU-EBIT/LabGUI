#!/usr/bin/env python3

import socket
import threading
import time
import struct
import os
import json

import numpy as np
import datetime
from dateutil import parser

# Some standard message components
DELIM = b'\x1e\x1e'
DALIM = b'\x1d\x1d'
GET = b'get'
SET = b'set'
ALL = b'all'
CLEAR = b'clear'
OPEN = b'open'
CLOSE = b'close'
HELLO = b'hello'
KEY_ERR = b'key_err!'
MODE_ERR = b'mode_err!'
UNPACK_ERR = b'unpack_err'
SUCCESS = b'success!'
CALLBACK = b'callback'
FILLER = b"??"
BUFSIZE = 1024

SAVE_DIR = "./_data_cache/"
BACK_DIR = "./_data_cache_old/"
MAX_FILESIZE = 20*1024*1024

# Server -> client messages
SETSUCCESS = SUCCESS + DALIM + SET
ALLSUCCESS = SUCCESS + DALIM + ALL
MODE_ERR_MSG = MODE_ERR + DALIM + MODE_ERR
KEY_ERR_MSG = KEY_ERR + DALIM + KEY_ERR
HELLO_FROM_SERVER = HELLO + DALIM + HELLO
CLOSED = SUCCESS + DALIM + CLOSE
CALLBACK_SUCCESS = CALLBACK + DALIM + SUCCESS

ADDR = ("0.0.0.0", 0)
LOG_ADDR = ("0.0.0.0", 0)
callback_targets = {}

class ServerProvider:
    PORT = 30001
    server_key = "default"

    def __init__(self) -> None:
        self._running_ = False

        self.server_tcp = None
        self.server_udp = None
        self.server_log = None

    def start(self):
        self.addr = ("0.0.0.0", ServerProvider.PORT)
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.connection.bind(self.addr)
        self.port = self.connection.getsockname()[1]

    def run(self):
        UDP_REQ = GET + DALIM + b'udp' + DELIM + ServerProvider.server_key.encode() + DELIM
        TCP_REQ = GET + DALIM + b'tcp' + DELIM + ServerProvider.server_key.encode() + DELIM
        LOG_REQ = GET + DALIM + b'log' + DELIM + ServerProvider.server_key.encode() + DELIM

        head_len = len(UDP_REQ)

        self._running_ = True
        self.start()
        while self._running_:
            data, addr = self.connection.recvfrom(1024)
            if len(data) < head_len:
                continue
            try:
                header = data[0:head_len]
                msg = b''
                port = -1
                if header == UDP_REQ and self.server_udp != None:
                    msg =  ServerProvider.server_key.encode() + DALIM + str(self.server_udp.port).encode()
                    port = int(data[head_len:].decode())
                elif header == TCP_REQ and self.server_tcp != None:
                    msg =  ServerProvider.server_key.encode() + DALIM + str(self.server_tcp.port).encode()
                    port = int(data[head_len:].decode())
                elif header == LOG_REQ and self.server_log != None:
                    msg =  ServerProvider.server_key.encode() + DALIM + str(self.server_log.port).encode()
                    port = int(data[head_len:].decode())
                else:
                    msg = b'err'
            except Exception as err:
                print(f"Error reading request: {err}")
            try:
                if msg != b'' and port != -1:
                    connection = socket.socket()
                    addr = (addr[0], port)
                    print(f"Sending: {msg} to {addr}")
                    connection.settimeout(0.25)
                    connection.connect(addr)
                    connection.sendto(msg, addr)
                    connection.shutdown(socket.SHUT_RDWR)
                    connection.close()
            except Exception as err:
                print(f"Error sending info: {err}")

class BaseDataServer:
    '''Python server implementation'''

    values = {}
    pending_save = {}
    save_lock = threading.Lock()
    provider_server = ServerProvider()
    provider_thread = threading.Thread(target=provider_server.run, daemon=True)

    def __init__(self, addr=ADDR, tcp=False) -> None:
        self.tcp = tcp
        
        if self.tcp:
            self.connection = socket.socket()
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.connection.bind(addr)
            self.port = self.connection.getsockname()[1]
            addr = (addr[0], self.port)
            self.connection.listen(256)
        else:
            self.connection = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.connection.bind(addr)
            self.port = self.connection.getsockname()[1]
            addr = (addr[0], self.port)

        self.addr = addr
    
        self._running_ = False

        self.cb_timeouts = {}

        # These are what are done on recieving messages
        # Adding extra things here can be used to make things
        # other than just getting/setting work.
        self.functions = {
            GET: self.on_get,
            SET: self.on_set,
            ALL: self.on_get_all,
            CLEAR: self.on_clear,
            CLOSE: self.on_close,
            OPEN: self.on_open,
            HELLO: self.on_hello,
            CALLBACK: self.on_callback,
        }

    def close(self):
        if self.connection is not None:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.connection.close()
            except:
                pass
        self.connection = None

    def run(self):
        '''run loop entry point for the server, probably best to run via a separate thread'''
        self._running_ = True
        print(f'Starting Data Server! {self.port}')
        while(self._running_):
            self.run_loop()

    def on_callback(self, address, data, conn):
        try:
            args = data.split(DALIM)
            key = args[0][2:]
            port_arg = args[1]

            if(port_arg[0] == b'x'[0]):
                port = int(args[1][1:].decode().replace('\x00', ''))
                addr = (address[0], port)
                for _, targets in callback_targets.items():
                    if addr in targets:
                        targets.remove(addr)
            else:
                port = int(args[1].decode().replace('\x00', ''))
                rate = int(args[2].decode().replace('\x00', '')) if len(args) > 2 else 100
                targets = []
                if key in callback_targets:
                    targets = callback_targets[key]
                else:
                    callback_targets[key] = targets
                addr = (address[0], port)
                if not addr in targets:
                    # print(f"New Callback: {key} {addr}")
                    targets.append((addr, rate))
        except Exception as err:
            print(f"Error with callback set {err}")
        resp = CALLBACK_SUCCESS
        if conn != None:
            conn.send(resp)
        else:
            self.connection.sendto(resp, address)

    def on_open(self, address, _, conn):
        '''processes the OPEN comand, presently doesn't do anything'''
        # TODO Decide if we want multiple threads for python version?
        resp = OPEN+DALIM+str(self.addr[1]).encode()
        if conn != None:
            conn.send(resp)
        else:
            self.connection.sendto(resp, address)

    def on_close(self, address, _, conn):
        '''processes the CLOSE comand, presently doesn't do anything'''
        # TODO Decide if we want multiple threads for python version?
        resp = CLOSED
        if conn != None:
            conn.send(resp)
        else:
            self.connection.sendto(resp, address)

    def on_clear(self, address, _, conn):
        '''processes the CLEAR command, and clears the values map'''
        BaseDataServer.values.clear()

    def on_hello(self, address, _, conn):
        '''processes the HELLO command and responds with a pong'''
        resp = HELLO_FROM_SERVER
        if conn != None:
            conn.send(resp)
        else:
            self.connection.sendto(resp, address)

    def pack_get(self, key, value):        
        msg = key+DALIM+value
        size = len(msg)
        var = struct.pack('<bb', size&31, size >> 5)
        msg = var + msg
        return msg

    def on_get(self, address, data, conn):
        '''processes the GET command, and responds with the value in the map, or KEY_ERR'''
        key = data[2:]
        value = BaseDataServer.values[key] if key in BaseDataServer.values else KEY_ERR
        msg = self.pack_get(key, value)
        # Sending a reply to client
        resp = msg
        if conn != None:
            conn.send(resp)
        else:
            self.connection.sendto(resp, address)

    def on_get_all(self, address, _, conn):
        '''processes the ALL command, and responds with all values in the map, and then ALLSUCCESS'''
        if not self.tcp or conn == None:
            self.connection.sendto(MODE_ERR_MSG, address)
            return
        resp = b''
        for key in BaseDataServer.values.keys():
            value = BaseDataServer.values[key] if key in BaseDataServer.values else KEY_ERR
            msg = key+DALIM+value
            size = len(msg)
            var = struct.pack('<bb', size&31, size >> 5)
            msg = var + msg
            if len(msg) + len(resp) > BUFSIZE:
                conn.send(resp)
                resp = b''
            resp = resp + msg
        msg = ALLSUCCESS
        if len(msg) + len(resp) > BUFSIZE:
            conn.send(resp)
            resp = msg
        resp = resp + msg
        conn.send(resp)

    def on_set(self, address, data, conn):
        '''processes the SET command, and responds with SETSUCCESS'''
        s_args = data.split(DALIM)
        had = False
        try:
            key = s_args[0][2:]
            value = s_args[1]
            resp = SETSUCCESS
            if key in BaseDataServer.values and BaseDataServer.values[key][0] != value[0]:
                resp = KEY_ERR_MSG
            else:

                if DataSaver.get_value_len(value) != len(value):
                    time.sleep(0.1)
                    print("???", value, conn.recv(64))
                    
                if conn != None:
                    conn.send(resp)
                else:
                    self.connection.sendto(resp, address)

                BaseDataServer.values[key] = value
                with BaseDataServer.save_lock:
                    to_log = []
                    if key in BaseDataServer.pending_save:
                        to_log = BaseDataServer.pending_save[key]
                    else:
                        BaseDataServer.pending_save[key] = to_log
                    to_log.append(value)
                    
                if key in callback_targets:
                    targets = callback_targets[key]
                    for pair in targets:
                        addr, _ = pair
                        # TODO rate throttle the callbacks using _ above
                        connection = socket.socket()
                        connection.settimeout(0.1)
                        try:
                            connection.connect(addr)
                            msg = self.pack_get(key, value)
                            connection.sendto(msg, addr)
                            self.cb_timeouts[addr] = 0
                        except TimeoutError:
                            # Timeout could just mean latency on client end, so don't cleanup here
                            if addr in self.cb_timeouts:
                                self.cb_timeouts[addr] += 1
                            else:
                                self.cb_timeouts[addr] = 1
                            if self.cb_timeouts[addr] > 10:
                                print(f"Removing {addr} due to timeout")
                                targets.remove(pair)
                                for key2, list in callback_targets.items():
                                    if key != key2 and addr in list:
                                        list.remove(addr)
                        except Exception as err:
                            # Other errors we can remove the client.
                            print(f"Removing {addr} due to error {err}")
                            targets.remove(pair)
                            for key2, list in callback_targets.items():
                                if key != key2 and addr in list:
                                    list.remove(addr)
                        try:
                            connection.shutdown(socket.SHUT_RDWR)
                            connection.close()
                        except Exception:
                            pass
                    if len(targets) == 0:
                        del callback_targets[key]
        except Exception as err:
            print(f'error setting value {err}')
        if had:
            print(f"Finished Set {key}")

    def run_loop(self):
        '''The contents of the run loop, this waits for messages and responds to them accordingly'''

        args = []
        address = ''
        try:
            if self.tcp:
                conn, address = self.connection.accept()
                message = conn.recv(BUFSIZE)
            else:
                conn = None
                bytesAddressPair = self.connection.recvfrom(BUFSIZE)
                message = bytesAddressPair[0]
                address = bytesAddressPair[1]
            if message == b'':
                return

            args = message.split(DELIM)
            mode = args[0]
            if len(args) > 1:
                data = args[1]
            else:
                data = b''

            if mode in self.functions:
                self.functions[mode](address, data, conn)
            else:
                self.connection.sendto(MODE_ERR, address, conn)

        except Exception as err:
            if self._running_:
                print(f"Error in server run loop: {err}, {args}, {address}")

    def make_thread(self):
        '''Makes a daemon thread that runs our run loop when started'''
        thread = threading.Thread(target=self.run, daemon=True)
        if self.tcp:
            BaseDataServer.provider_server.server_tcp = self
        else:
            BaseDataServer.provider_server.server_udp = self
        return thread
    
class DataSaver:

    def get_value_len(value):  
        try:
            from .data_client import TYPES
        except:
            from data_client import TYPES      
        id = value[0]
        TYPE = TYPES[id - 1]
        tst = TYPE()
        length = tst.size()
        return length

    def __init__(self) -> None:
        self.save_delay = 0.25
        self._running_ = False
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
        if not os.path.exists(BACK_DIR):
            os.makedirs(BACK_DIR)

    def run(self):
        self._running_ = True
        while self._running_:
            time.sleep(self.save_delay)
            values = []
            with BaseDataServer.save_lock:
                for key, values in BaseDataServer.pending_save.items():
                    if not len(values):
                        continue
                    key = key.decode()
                    filename = SAVE_DIR + key + ".dat"
                    try:
                        file = open(filename, 'ab')
                        while(len(values)):
                            value = values.pop(0)
                            # Ensure lenghth is correct
                            size = DataSaver.get_value_len(value)
                            if size != len(value):
                                print(f"Value size error? {size} != {len(value)}, {key}, {value}")
                                continue
                            file.write(value)
                        file.close()
                        file_stats = os.stat(filename)
                        if file_stats.st_size > MAX_FILESIZE:
                            filename_bak = BACK_DIR + key + ".dat"
                            print("Moving file ", filename, filename_bak)
                            if os.path.exists(filename_bak):
                                os.replace(filename, filename_bak)
                            else:
                                os.rename(filename, filename_bak)
                            os.remove(filename)
                    except Exception as err:
                        print(f"Error while saving value: {err}")
                        pass

    def make_thread(self):
        '''Makes a daemon thread that runs our run loop when started'''
        thread = threading.Thread(target=self.run, daemon=True)
        return thread
    
class LogLoader:

    def __init__(self, key, dir=SAVE_DIR, old_dir=BACK_DIR, max_dt=1e30, min_free_space=500*1024**2) -> None:
        self.key = key
        self.new_dir = dir
        self.old_dir = old_dir
        self.file_end = 0
        self.values = []
        self.times = []
        self._np_v = None
        self._np_t = None
        self.max_dt = max_dt
        self.min_free_space = min_free_space

    def process_old_dir(self):
        # Check if a file was put in there.
        filename = self.old_dir + self.key + ".dat"
        save_dir = self.old_dir + self.key
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        if os.path.exists(filename):
            # Copy it to a folder
            # Name timestamp should be time for first entry in the file
            file = open(filename, 'rb')
            vars = file.read(16)
            file.close()
            vars = vars[1:9]
            stamp = struct.unpack("d", vars)[0]
            stamp = time.strftime('%Y-%m-%d_%H_%M_%S', time.localtime(stamp))
            new_filename =  save_dir + f"/{self.key}_{stamp}.dat"
            os.rename(filename, new_filename)

            import shutil
            _, _, free = shutil.disk_usage(new_filename)
            if free < self.min_free_space:
                files = os.listdir(save_dir)
                files.sort()
                oldest =  os.path.join(save_dir, files[0])
                print(f"Warning, Removed old log due to lack of disk space! {oldest}")
                os.remove(oldest)

    def _load_values(self, filename:str, file_end):
        import numpy as np
            
        file = open(filename, 'rb')
        file.seek(file_end)
        vars = file.read()
        file.close()

        if filename.endswith('.dat_z'):
            # These ones are compressed via zlib
            import zlib
            vars = zlib.decompress(vars)

        self.raw_values = vars
        id = vars[0]
        length = DataSaver.get_value_len(vars)

        number = len(vars) / length
        if number != int(number):
            raise RuntimeWarning("Wrong size in file!")

        # numpy stuff from Tim
        vars = np.fromiter(vars, dtype='uint8')
        vars = np.reshape(vars, (-1, length))

        _times = vars[:,1:9].copy(order="C")
        decode_time = lambda x: struct.unpack("d", x)[0]

        if id == 1:
            _values = vars[:,9:].copy(order="C")
            decode_value = lambda x: struct.unpack("d", x)[0]

        times = [decode_time(x) for x in _times]
        values = [decode_value(x) for x in _values]

        for t in times:
            self.times.append(t)
        for v in values:
            self.values.append(v)
            
        loaded_t = np.fromiter(times, dtype=np.float64)
        if id == 1:
            loaded_v = np.fromiter(values, dtype=np.float64)
        else:
            loaded_v = np.array(values)

        if self._np_t is None:
            self._np_t = loaded_t
            self._np_v = loaded_v
        else:
            self._np_t = np.hstack((self._np_t, loaded_t))
            self._np_v = np.hstack((self._np_v, loaded_v))

        if len(self._np_t) > 2:
            min_index = np.searchsorted(self._np_t, self._np_t[-1] - self.max_dt)
            self._np_t = self._np_t[min_index:]
            self._np_v = self._np_v[min_index:]
            self.times = self.times[min_index:]
            self.values = self.values[min_index:]

    def load_from_old_dir(self, start_time):
        save_dir = self.old_dir + self.key
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        files = os.listdir(save_dir)
        self.values = []
        self.times = []
        files.sort(reverse=True)

        to_load = []
        for file in files:
            stamp = file.replace(f"{self.key}_", "")
            stamp = stamp.removesuffix(".dat_z")
            stamp = stamp.removesuffix(".dat")
            stamp = time.mktime(time.strptime(stamp, '%Y-%m-%d_%H_%M_%S'))
            if stamp > start_time:
                to_load.append(f"{save_dir}/{file}")
            else:
                to_load.append(f"{save_dir}/{file}")
                break
        to_load.sort()
        for filename in to_load:
            self._load_values(filename, 0)

    def load(self, start_time=None):
        if start_time is None:
            start_time = time.time() - (12 * 3600)
        try:
            filename = self.new_dir + self.key + ".dat"
            file_size = os.stat(filename).st_size

            if self._np_t is not None:
                if self._np_t[0] > start_time:
                    self.load_from_old_dir(start_time)
                    self.file_end = 0

            if self.file_end > file_size:
                self.file_end = 0
            elif self.file_end == file_size:
                return self._np_t, self._np_v

            self._load_values(filename, self.file_end)
            self.file_end = file_size

            return self._np_t, self._np_v
        except Exception as err:
            print(err)
            return None, None

class LogServer:

    HEADER = b'\0\0start\0\0'
    FOOTER = b'\0\0end\0\0'
    MAX_PACKET_SIZE = 32768

    def make_request_message(key, start_hours=1, end_hours=0, since=None, until=None, as_timestamps=True):
        resp = {'key':key, "as_timestamps":as_timestamps}
        now = time.time()
        if since is not None:
            resp['since'] = since
        elif start_hours != 1:
            resp['since'] = now - start_hours * 3600
        if until is not None:
            resp['until'] = until
        elif end_hours != 0:
            resp['until'] = now - end_hours * 3600
        return json.dumps(resp)

    def __init__(self, addr=LOG_ADDR) -> None:
        self.addr = addr
        self.connection = socket.socket()
        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.connection.bind(addr)
        self.connection.listen(256)
        self.port = self.connection.getsockname()[1]
        self._running_ = False
        self.log_lock = threading.Lock()
        self.logs = {}

    def split(self, resp):
        import zlib
        resp = zlib.compress(resp)
        resps = []
        PADDED_SIZE = LogServer.MAX_PACKET_SIZE - (len(LogServer.HEADER) + len(LogServer.FOOTER))
        resps.append(LogServer.HEADER)
        while len(resp) > PADDED_SIZE:
            split = resp[0:PADDED_SIZE]
            resp = resp[PADDED_SIZE:]
            resps.append(split)
        if len(resp) > 0:
            resps.append(resp)
        resps.append(LogServer.FOOTER)
        return resps
    
    def update_values(self, key, last_point=None, end=None, skip_points=1, as_timestamps=True):
        with self.log_lock:
            if key in self.logs:
                log = self.logs[key]
            else:
                log = LogLoader(key, SAVE_DIR, BACK_DIR)
                self.logs[key] = log
                log.process_old_dir()
        
        now = time.time()
        if end is None:
            end = now + 1e6
        else:
            try:
                _time = float(end)
                end = _time
            except:
                pass
            if isinstance(end, float):
                end = end
            else:
                end = parser.parse(end).timestamp()
        
        start = now - 3600
        if last_point is not None:
            try:
                _time = float(last_point)
                last_point = _time
            except:
                pass
            if isinstance(last_point, float):
                start = last_point
            else:
                start = parser.parse(last_point).timestamp()
        
        def get_values_from_log():
            x, y = log.load(start_time=start)
            
            if x is None:
                return None, None
            
            not_found = len(x) == 0 or start < x[0] or start > x[-1]
            if not_found:
                # Try another pass incase we need to load older logs
                x, y = log.load(start_time=start)
            return x, y

        x, y = get_values_from_log()
        
        if x is None:
            with self.log_lock:
                del self.logs[key]
            return b'error!'

        [start, end] = np.searchsorted(x, [start, end])
        
        x = x[start:end]
        y = y[start:end]

        if skip_points > 1 and len(x) > skip_points:
            x = x[::skip_points]
            y = y[::skip_points]

        values = []
        if as_timestamps:
            values = np.array([x, y]).tolist()
        else:
            for i in range(len(x)):
                values.append([datetime.datetime.fromtimestamp(x[i]).isoformat(), y[i]])

        return json.dumps(values).encode()

    def read_loop(self):
        try:
            conn, _ = self.connection.accept()  # accept new connection
            # receive data stream. it won't accept data packet greater than MAX_PACKET_SIZE bytes
            data = conn.recv(LogServer.MAX_PACKET_SIZE)
        except Exception as err:
            print("Error in recv?", err)
            conn.close()
            return
        if len(data) == 0:
            # if data is not received break
            conn.close()  # close the connection
            return
        try:

            if data.startswith(HELLO):
                conn.send(HELLO_FROM_SERVER)
                conn.close()  # close the connection
                return
            
            data = data.decode()

            values = json.loads(data)

            # Key not found exception caught below.
            key = values['key']

            skip_points = 1
            if 'skip_points' in values:
                skip_points = values['skip_points']

            last_point = None
            end = None
            if 'since' in values:
                last_point = values['since']
            if 'until' in values:
                end = values['until']
            as_timestamps = True if not 'as_timestamps' in values else values['as_timestamps']
            resp = self.update_values(key, last_point, end, skip_points=skip_points, as_timestamps=as_timestamps)

            for resp in self.split(resp):
                conn.send(resp)
            else:
                conn.send(b'error!')
        except Exception as err:
            print(f'Error in logs request {err}, {data}')
            conn.send(b'error!')
        conn.close()

    def log_monitor_loop(self):
        self._running_ = True
        while(self._running_):

            with self.log_lock:
                files = os.listdir(BACK_DIR)
                for file in files:
                    if file.endswith(".dat"):
                        key = file.replace(".dat", '')
                    else:
                        key = file
                    if not key in self.logs:
                        log = LogLoader(key, SAVE_DIR, BACK_DIR)
                        self.logs[key] = log
                for log in self.logs.values():
                    log.process_old_dir()

            for _ in range(600):
                time.sleep(0.1)
                if not self._running_:
                    break

    def run(self):
        self._running_ = True
        print(f'Starting Log Server! {self.port}')

        while(self._running_):
            try:
                self.read_loop()
            except Exception as err:
                print(f"Exception in log run loop, {err}")

    def make_thread(self):
        '''Makes a daemon thread that runs our run loop when started'''
        thread = threading.Thread(target=self.run, daemon=True)
        self.thread_2 = threading.Thread(target=self.log_monitor_loop, daemon=True)
        self.thread_2.start()
        
        BaseDataServer.provider_server.server_log = self
        return thread

def make_server_threads(addr_tcp=("0.0.0.0", 0), addr_udp=("0.0.0.0", 0)):
    server_tcp = BaseDataServer(tcp=True, addr=addr_tcp)
    server_udp = BaseDataServer(tcp=False, addr=addr_udp)
    saver = DataSaver()

    thread_tcp = server_tcp.make_thread()
    thread_tcp.start()

    thread_udp = server_udp.make_thread()
    thread_udp.start()

    save_thread = saver.make_thread()
    save_thread.start()

    return (server_tcp, thread_tcp), (server_udp, thread_udp), (saver, save_thread)

def make_log_thread(addr=("0.0.0.0", 0)):
    server = LogServer(addr)
    thread = server.make_thread()
    thread.start()
    return (server, thread)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog='Data Server',
        description='Server for holding/providing data values for LabGUI')
    
    parser.add_argument('-m', '--mode')
    parser.add_argument('-k', '--key')
    parser.add_argument('-l', '--log_port')
    parser.add_argument('-t', '--tcp_port')
    parser.add_argument('-u', '--udp_port')

    args = parser.parse_args()

    port_log = 0 if not args.log_port else int(args.log_port)
    port_tcp = 0 if not args.tcp_port else int(args.tcp_port)
    port_udp = 0 if not args.udp_port else int(args.udp_port)
    if args.key:
        ServerProvider.server_key = args.key

    addr_log = ("0.0.0.0", port_log)
    addr_tcp = ("0.0.0.0", port_tcp)
    addr_udp = ("0.0.0.0", port_udp)

    if args.mode == 'logs':
        (server, thread) = make_log_thread(addr_log)
        # Now start the provider thread who says where the server is
        if ServerProvider.server_key != "None":
            print("Starting Provider thread")
            BaseDataServer.provider_thread.start()
        # Then wait for enter to be pressed before stopping
        input("")
        server._running_ = False
        time.sleep(0.5)
    elif args.mode == 'tests':
        if not args.key:
            ServerProvider.server_key = 'local_test'
        (server_tcp, _), (server_udp, _), (saver, save_thread) = make_server_threads(addr_tcp, addr_udp)
        (server, thread) = make_log_thread(addr_log)
        # Now start the provider thread who says where the server is
        if ServerProvider.server_key != "None":
            print("Starting Provider thread")
            BaseDataServer.provider_thread.start()
        # Then wait for enter to be pressed before stopping
        input("")
        server_tcp._running_ = False
        server_udp._running_ = False
        server._running_ = False
        server_tcp.close()
        time.sleep(0.5)
    else:
        # construct a server
        (server_tcp, _), (server_udp, _), (saver, save_thread) = make_server_threads(addr_tcp, addr_udp)
        (server, thread) = make_log_thread(addr_log)
        # Now start the provider thread who says where the server is
        if ServerProvider.server_key != "None":
            print("Starting Provider thread")
            BaseDataServer.provider_thread.start()
        # Then wait for enter to be pressed before stopping
        input("")
        server_tcp._running_ = False
        server_udp._running_ = False
        server._running_ = False
        server_tcp.close()
        time.sleep(0.5)