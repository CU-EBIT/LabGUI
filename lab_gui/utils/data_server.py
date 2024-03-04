#!/usr/bin/env python3

import socket
import threading
import time
import struct
import os

# Some standard message components
DELIM = b':__:'
DALIM = b'_::_'
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

ADDR = ("0.0.0.0", 30002)
callback_targets = {}

class BaseDataServer:
    '''Python server implementation'''

    values = {}
    pending_save = {}
    save_lock = False

    def lock_save():
        while BaseDataServer.save_lock:
            time.sleep(0.00001)
        BaseDataServer.save_lock = True

    def unlock_save():
        BaseDataServer.save_lock = False

    def __init__(self, addr=ADDR, tcp=False) -> None:
        self.tcp = tcp
        self.addr = addr
        
        if self.tcp:
            self.connection = socket.socket()
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.connection.bind(addr)
            self.connection.listen(256)
        else:
            self.connection = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.connection.bind(addr)
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
        print('Starting Data Server!')
        while(self._running_):
            self.run_loop()

    def on_callback(self, address, data, conn):
        try:
            args = data.split(DALIM)
            key = args[0][2:]
            port_arg = args[1]

            if(port_arg[0] == b'x'[0]):
                port = int(args[1][1:].decode())
                addr = (address[0], port)
                for _, targets in callback_targets.items():
                    if addr in targets:
                        targets.remove(addr)
            else:
                port = int(args[1].decode())
                targets = []
                if key in callback_targets:
                    targets = callback_targets[key]
                else:
                    callback_targets[key] = targets
                addr = (address[0], port)
                if not addr in targets:
                    # print(f"New Callback: {key} {addr}")
                    targets.append(addr)
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
                if conn != None:
                    conn.send(resp)
                else:
                    self.connection.sendto(resp, address)

                BaseDataServer.values[key] = value
                to_log = []
                BaseDataServer.lock_save()
                if key in BaseDataServer.pending_save:
                    to_log = BaseDataServer.pending_save[key]
                else:
                    BaseDataServer.pending_save[key] = to_log
                BaseDataServer.unlock_save()
                to_log.append(value)
                if key in callback_targets:
                    targets = callback_targets[key]
                    for addr in targets:
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
                                targets.remove(addr)
                                for key2, list in callback_targets.items():
                                    if key != key2 and addr in list:
                                        list.remove(addr)
                        except Exception as err:
                            # Other errors we can remove the client.
                            print(f"Removing {addr} due to error {err}")
                            targets.remove(addr)
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
        return thread
    
class DataSaver:

    def __init__(self) -> None:
        self.save_delay = 1
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
            BaseDataServer.lock_save()
            for key, values in BaseDataServer.pending_save.items():
                if not len(values):
                    continue
                key = key.decode()
                filename = SAVE_DIR + key + ".dat"
                try:
                    file = open(filename, 'ab')
                    while(len(values)):
                        value = values.pop(0)
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
                except:
                    pass
            BaseDataServer.unlock_save()

    def make_thread(self):
        '''Makes a daemon thread that runs our run loop when started'''
        thread = threading.Thread(target=self.run, daemon=True)
        return thread
    
class LogLoader:

    def __init__(self, key, dir=SAVE_DIR) -> None:
        self.filename = dir + key + ".dat"
        self.values = []

    def load(self):
        from data_client import TYPES
        import numpy as np
        try:
            file = open(self.filename, 'rb')
            vars = file.read()
            self.raw_values = vars
            id = vars[0]
            TYPE = TYPES[id - 1]
            tst = TYPE()
            length = tst.size()
            number = len(vars) / length
            if number != int(number):
                raise RuntimeWarning("Wrong size in file!")
            number = int(number)

            # numpy stuff from Tim
            vars = np.array(list(vars), dtype='uint8')
            vars = np.reshape(vars, (-1, length))

            _times = vars[:,1:9].copy(order="C")
            _values = vars[:,9:].copy(order="C")

            decode_time = lambda x: struct.unpack("d", x)[0]
            decode_value = lambda x: struct.unpack("d", x)[0]

            times = np.array([decode_time(x) for x in _times])
            values = np.array([decode_value(x) for x in _values])

            return times, values
        except Exception as err:
            print(err)
            return None, None

def make_server_threads():
    server_tcp = BaseDataServer(tcp=True, addr=("0.0.0.0", 30002))
    server_udp = BaseDataServer(tcp=False, addr=("0.0.0.0", 20002))
    saver = DataSaver()

    thread_tcp = server_tcp.make_thread()
    thread_tcp.start()

    thread_udp = server_udp.make_thread()
    thread_udp.start()

    save_thread = saver.make_thread()
    save_thread.start()

    return (server_tcp, thread_tcp), (server_udp, thread_udp), (saver, save_thread)

if __name__ == "__main__":
    # construct a server
    (server_tcp, _), (server_udp, _), (saver, save_thread) = make_server_threads()
    # Then wait for enter to be pressed before stopping
    input("")
    server_tcp._running_ = False
    server_udp._running_ = False
    server_tcp.close()
    time.sleep(0.5)