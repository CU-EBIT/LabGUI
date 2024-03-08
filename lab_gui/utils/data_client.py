import socket
from datetime import datetime
import pickle
import struct
import threading
import time

# Adds prints if things go wrong
DEBUG = False

# Address to use, ensure that you set this in your implementation!
ADDR = None

# Tuple of (address, port) for log access
DATA_LOG_HOST = None

class DoubleValue:
    '''Implementation of a value containing a 64 bit floating point number'''
    def __init__(self) -> None:
        self.id = 1
        self.time = 0.0
        self.value = 0.0

    def pack(self):
        return struct.pack("<bdd", self.id, self.time, self.value)

    def unpack(self, bytes):
        self.id, self.time, self.value = struct.unpack("<bdd", bytes)

    def size(self):
        return 17 # 1 + 8 + 8

    def valid_value(value):
        return isinstance(value, float)

class IntegerValue:
    '''Implementation of a value containing a 32 bit integer'''
    def __init__(self) -> None:
        self.id = 2
        self.time = 0.0
        self.value = 0

    def pack(self):
        return struct.pack("<bdi", self.id, self.time, self.value)

    def unpack(self, bytes):
        self.id, self.time, self.value = struct.unpack("<bdi", bytes)

    def size(self):
        return 13 # 1 + 8 + 4

    def valid_value(value):
        return isinstance(value, int)

class BooleanValue:
    '''Implementation of a value containing a boolean as an 8-bit value'''
    def __init__(self) -> None:
        self.id = 3
        self.time = 0.0
        self.value = False

    def pack(self):
        return struct.pack("<bd?", self.id, self.time, self.value)

    def unpack(self, bytes):
        self.id, self.time, self.value = struct.unpack("<bd?", bytes)

    def size(self):
        return 10 # 1 + 8 + 1

    def valid_value(value):
        return isinstance(value, bool)

class StringValue:
    '''Implementation of a value containing a C compatible string'''
    def __init__(self) -> None:
        self.id = 4
        self.time = 0.0
        self.value = ""

    def pack(self):
        size = len(self.value)
        extra = f"{size}s"
        fmt = "<bdh"+extra
        return struct.pack(fmt, self.id, self.time, size + 1, self.value.encode())+b'\0'

    def unpack(self, bytes):
        _, _, size = struct.unpack("<bdh", bytes[0:11])
        extra = f"{size - 1}s"
        fmt = "<bdh"+extra
        self.id, self.time, _, self.value = struct.unpack(fmt, bytes[0:-1])
        self.value = self.value.decode('utf-8')

    def size(self):
        size = len(self.value) + 1 # 1 for null terminator
        return 11 + size # 1 + 8 + 2 + length of string

    def valid_value(value):
        return isinstance(value, str)

# Order of value types for lookup by index
TYPES = [   
            DoubleValue,  # in ID order, note that
            IntegerValue, # index here is id - 1
            BooleanValue, 
            StringValue,
        ]

# Order of value types for automatic type detection for packing
PACK = [   
            BooleanValue, # Re-ordered for ensuring bools and ints go first
            IntegerValue,
            DoubleValue, 
            StringValue,
        ]

def pack_data(timestamp, value):
    '''Packs the given value as the appropriate value type, returns none if no types match'''
    for _type in PACK:
        if _type.valid_value(value):
            time_num = timestamp.timestamp()
            var = _type()        
            var.time = time_num
            var.value = value
            return var.pack()
    return None

def unpack_data(bytes):
    '''Unpacks the given data to a value type, throws exceptions if type is not found'''
    id = int(bytes[0]) - 1
    var = TYPES[id]()
    var.unpack(bytes)
    return var

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

# Server -> client messages
SETSUCCESS = SUCCESS + DALIM + SET
ALLSUCCESS = SUCCESS + DALIM + SET
MODE_ERR_MSG = MODE_ERR + DALIM + MODE_ERR
KEY_ERR_MSG = KEY_ERR + DALIM + KEY_ERR
HELLO_FROM_SERVER = HELLO + DALIM + HELLO
CLOSED = SUCCESS + DALIM + CLOSE

# Client -> server messages
_open_cmd = OPEN + DELIM + FILLER + OPEN
_close_cmd = CLOSE + DELIM + FILLER + CLOSE
# _hello = HELLO + DELIM + HELLO
all_request = ALL + DELIM + FILLER + ALL

def callback_request(key, port, closing=False, rate = 100):
    if closing:
        msg = f'{key}{DALIM.decode()}x{port}\0{DALIM.decode()}{rate}\0'.encode()
    else:
        msg = f'{key}{DALIM.decode()}{port}\0{DALIM.decode()}{rate}\0'.encode()
    s = len(msg)
    # We encode size in along with the message
    size = struct.pack("<bb", int(s&31), int(s>>5))
    return CALLBACK + DELIM + size + msg

def pack_value(timestamp, value):
    '''Packs the given value, if it doesn't use a standard type, it pickles it instead'''
    pack = (timestamp,value)
    packed = pack_data(timestamp, value)
    if packed is not None:
        return packed
    return pickle.dumps(pack)

def unpack_value(bytes):
    '''Unpacks a value from the bytes, returns if it did unpack, the key, and what unpacked'''
    # messages from server are split by DALIM
    args = bytes.split(DALIM)
    # If it said success, that means it wasn't a value response!
    if args[0] == SUCCESS:
        # All success can occur for different reason, so return ALL here
        if args[1] == ALL:
            return False, args[0], ALL
        # Otherwise was an unpack error
        return False, args[0], UNPACK_ERR
    # Server appends the size of the expected object to the front
    # so args[0][0:2] is the packaged expected size.
    key = args[0][2:].decode('utf-8')
    # If key wasn't correct/found, return that
    if key == KEY_ERR:
        return False, key, KEY_ERR
    data = args[1]
    # If data was "ALL", then it means it was an end of ALL message, so return that
    if data == ALL:
        return False, key, ALL
    # Otherwise if data was key error, return that
    if data == KEY_ERR:
        return False, key, KEY_ERR
    # Same for mode error
    elif data == MODE_ERR:
        return False, key, MODE_ERR
    # Finally try to unpack things
    try:
        try:
            # Try unpickling first
            value = pickle.loads(data)
            return True, key, value
        except Exception:
            # Not a pickle thing, lets try custom values
            unpacked = unpack_data(data)
            timestamp = datetime.fromtimestamp(unpacked.time)
            value = (timestamp, unpacked.value)
        return True, key, value
    except Exception as err:
        # Otherwise print error and return unpack error
        if DEBUG:
            print(f'Error unpacking value {key}: {err}, {bytes}')
        return False, key, UNPACK_ERR

def set_msg(key, timestamp, value):
    '''Packs the key, value and timestamp into a message for server'''
    packed = str.encode(key) + DALIM + pack_value(timestamp, value)
    s = len(packed)
    # We encode size in along with the message
    size = struct.pack("<bb", int(s&31), int(s>>5))
    msg = SET + DELIM + size + packed
    return msg


def get_msg(key):
    '''Packs key for a get query'''
    # Server doesn't presently use the size bytes here, hence FILLER
    return GET + DELIM + FILLER + str.encode(key)

class DataCallbackServer:
    def __init__(self, port = 0, client_addr=ADDR) -> None:
        '''addr is address/port tuple, custom_port would call select() if true'''
        self.connection = None
        self.addr = ("0.0.0.0", port)
        self.client_addr = client_addr
        self.connection = socket.socket()
        self.connection.bind(self.addr)
        self.port = self.connection.getsockname()[1]
        self.connection.listen(8)

        self.listeners = {}
        self.last_heard_times = {}

        self._running_ = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

        self.alive_thread = threading.Thread(target=self.check_alive, daemon=True)
        self.alive_thread.start()

    def __del__(self):
        self.close()

    def close(self):
        
        try:
            client = BaseDataClient(self.client_addr)
            client.init_connection()
            callback_set = callback_request("???", self.port, closing=True)
            client.send_msg(callback_set)
            client.close()
        except:
            pass

        self._running_ = False
        if self.connection is not None:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
            except:
                pass
        self.port = -1

    def add_listener(self, key, listener):
        if not key in self.listeners:
            self.listeners[key] = []
        self.last_heard_times[key] = 0
        listeners = self.listeners[key]
        if not listener in listeners:
            listeners.append(listener)
            return True
        return False

    def handle_msg(self, message):
        success, key, unpacked = unpack_value(message)
        self.last_heard_times[key] = time.time()
        if success and key in self.listeners:
            for listener in self.listeners[key]:
                listener(key, unpacked)

    def run(self):
        '''run loop entry point for the server, probably best to run via a separate thread'''
        self._running_ = True
        message = b''
        while(self._running_):
            try:
                conn, _ = self.connection.accept()
                message = conn.recv(BUFSIZE)
                if message == b'':
                    continue
                self.handle_msg(message)
            except Exception as err:
                if self._running_:
                    print(err, message)

    def check_alive(self):
        '''Every so often check that server still knows about us'''
        self._running_ = True
        while self._running_:
            time.sleep(1)
            keys = []
            now = time.time()
            for key, last_time in self.last_heard_times.items():
                if now - last_time > 10:
                    keys.append(key)
            if len(keys):
                client = BaseDataClient(self.client_addr)
                client.init_connection()
                for key in keys:
                    self.last_heard_times[key] = now
                    client.register_callback_server(key, self.port)
                client.close()

class BaseDataClient:
    '''Python client implementation'''
    def __init__(self, addr=ADDR, custom_port=False) -> None:
        '''addr is address/port tuple, custom_port would call select() if true'''
        self.connection = None
        self.tcp = True
        self.addr = addr
        self.custom_port = -1
        self.root_port = addr[1]
        self.reads = {}
        self.values = {}
        self.cb_ports = []
        if custom_port:
            self.select()

    def __del__(self):
        if self.tcp and self.custom_port != -1:
            self.init_connection()
            self.close()

    def change_port(self, port):
        '''Changes the port we connect over'''
        self.close()
        self.addr = (self.addr[0], port)
        if port != self.root_port:
            self.custom_port = port

    def init_connection(self):
        '''Starts a new connection, closes existing one if present.'''
        if self.connection is not None:
            self.close()
        if self.tcp:
            self.connection = socket.socket()
            self.connection.connect(self.addr)
            self.connection.settimeout(0.5)
        else:
            self.connection = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.connection.settimeout(0.1)

    def close(self):
        if self.connection is not None:
            try:
                if self.addr[1] != self.root_port:
                    self.connection.sendto(_close_cmd, self.addr)
                self.connection.close()
                self.connection = None
            except Exception as err:
                print(f'error closing? {err}')
    
    def register_callback_server(self, key, port):
        try:
            callback_set = callback_request(key, port)
            if not port in self.cb_ports:
                self.cb_ports.append(port)
            self.send_msg(callback_set)
        except Exception as err:
            print(f'error registering a callback? {err} for {key}')

    def send_msg(self, msg):
        if self.connection == None or self.tcp:
            self.init_connection()
        self.connection.sendto(msg, self.addr)
        msgFromServer = self.connection.recvfrom(BUFSIZE)
        return msgFromServer

    def select(self):
        '''This is the Python equivalent of the "connect" function in C++ version, it also ensures a new port'''
        if self.tcp and self.custom_port != -1:
            return True
        try:
            # ensure we are in the initial port
            # this also closes the connection if it existed
            self.change_port(self.root_port)
            msgFromServer = self.send_msg(_open_cmd)
            new_port = int(msgFromServer[0].split(DALIM)[1].decode())
            self.change_port(new_port)
            return True
        except Exception as err:
            print(f'error selecting? {err}')
            pass
        return False

    def get_value(self, key):
        '''Requests the value associated with `key` from the server'''

        bytesToSend = get_msg(key)
        unpacked = ''

        if self.tcp:
            try:
                msgFromServer = self.send_msg(bytesToSend)
                success, _key2, unpacked = unpack_value(msgFromServer[0])
                if unpacked == KEY_ERR:
                    if DEBUG:
                        print(f"Error getting {key}")
                    return None
                if success:
                    return unpacked
                else:
                    print(f"Unspecified Error getting {key}, {msgFromServer}")
                    return None
            except Exception as err:
                msg = f'Error getting value for {key}! {err}'
                # Timeouts can happen, so only print ones that did not
                if DEBUG and not 'timed out' in msg:
                    print(msg)
                return None
        else:
            _key = key
            # If we had already read it in error before, return that
            if _key in self.reads:
                return self.reads.pop(_key) 

            n = 0
            # Otherwise try a few times at reading, we can fail for UDP reasons
            while n < 10:
                n += 1
                # Send to server using created UDP socket
                try:
                    msgFromServer = self.send_msg(bytesToSend)
                    success, _key2, unpacked = unpack_value(msgFromServer[0])

                    if unpacked == KEY_ERR:
                        if DEBUG:
                            print(f"Error getting {key}")
                        return None
                    # If we request too fast, things get out of order.
                    # This allows caching the wrong reads for later
                    if _key2 != _key:
                        n-=1
                        self.reads[_key2] = unpacked
                        continue
                    if success:
                        return unpacked
                    # Try to reset connection if we failed to unpack
                    if unpacked == UNPACK_ERR:
                        if DEBUG:
                            print('resetting connection')
                        self.init_connection()
                except Exception as err:
                    msg = f'Error getting value for {key}! {err}'
                    # Timeouts can happen, so only print ones that did not
                    if DEBUG and not 'timed out' in msg:
                        print(msg)
                    pass
        if DEBUG:
            print(f'failed to get! {key} {unpacked}')
        return None

    def get_var(self, key, default=0):
        '''Attempts to get value from server, if not present, returns default and now'''
        resp = self.get_value(key)
        if resp is None:
            return datetime.now(), default
        return resp[0], resp[1]

    def get_int(self, key, default=0):
        '''int type casted unwrapped version of get_var'''
        time, var = self.get_var(key, default)
        return time, int(var)

    def get_bool(self, key, default=False):
        '''bool type casted unwrapped version of get_var'''
        time, var = self.get_var(key, default)
        return time, bool(var)
    
    def get_float(self, key, default=0):
        '''float type casted unwrapped version of get_var'''
        time, var = self.get_var(key, default)
        return time, float(var)

    def check_set(self, _, bytes):
        '''Checks if it was the set response message, also handles miss-applied get responses'''
        args = bytes.split(DALIM)
        data = args[0]
        if data == SUCCESS:
            return True
        # Otherwise might be a get value return
        _, _key2, unpacked = unpack_value(bytes[0])
        if _key2 in self.reads:
            if DEBUG:
                print('error, duplate return!')
            return False
        self.reads[_key2] = unpacked
        return False

    def set_int(self, key, value, timestamp = None):
        '''int casted version of set_value'''
        return self.set_value(key, int(value), timestamp)

    def set_bool(self, key, value, timestamp = None):
        '''bool casted version of set_value'''
        return self.set_value(key, bool(value), timestamp)
    
    def set_float(self, key, value, timestamp = None):
        '''float casted version of set_value'''
        return self.set_value(key, float(value), timestamp)

    def set_value(self, key, value, timestamp = None):
        '''attempts to send the `key`, `value` pair to the server. 
        uses datetime.now() for timestamp if not present, 
        returns if set successfully'''
        if timestamp is None:
            timestamp = datetime.now()
        # Package the key value pair and timestamp for server
        bytesToSend = set_msg(key, timestamp, value)
        # Ensure is in packet size range
        if(len(bytesToSend) > BUFSIZE):
            if DEBUG:
                print('too long!')
            return False
        try:
            # If so, try to sent to server
            if self.connection == None or self.tcp:
                self.init_connection()
            self.connection.sendto(bytesToSend, self.addr)
            msgFromServer = self.connection.recvfrom(BUFSIZE)
            # And see if the server responded appropriately
            if self.check_set(key, msgFromServer[0]):
                return True
        except:
            pass
        return False

    def get_all(self):
        '''Requests all values from server, returns a map of all found values. This map may be incomplete due to lost packets.'''
        self.values = {}
        if self.connection == None or self.tcp:
            self.init_connection()
        self.connection.sendto(all_request, self.addr)

        msg = b''
        if self.tcp:
            try:
                _msg = self.connection.recvfrom(BUFSIZE)[0]
                msg = _msg

                while _msg != b'':
                    _msg = self.connection.recvfrom(BUFSIZE)[0]
                    msg = msg + _msg
                
                done = False
                while not done:
                    next_dalim = msg.index(DALIM)
                    key = msg[0:next_dalim]
                    if key[2:] != b'success!':
                        if key == b'':
                            break
                        size = (key[0]&31) + ((key[1]&31) << 5)
                        value = msg[0: size + 2]
                        data = value
                        msg = msg[size + 2:]
                        success, key, unpacked = unpack_value(data)
                        if success:
                            self.values[key] = unpacked
                    else:
                        done = True
                    done = done or msg == b''
            except KeyboardInterrupt:
                pass
            except Exception as err:
                _msg = f'Error getting all value! {err}, {msg}'
                if 'timed out' in _msg:
                    done = True
                elif DEBUG:
                    print(_msg)
        return self.values