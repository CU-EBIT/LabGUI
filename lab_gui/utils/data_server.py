import socket
import threading
import time
import struct

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
    def __init__(self, addr=ADDR, tcp=False) -> None:
        self.tcp = tcp
        self.addr = addr
        
        if self.tcp:
            self.connection = socket.socket()
            self.connection.bind(addr)
            self.connection.listen(256)
        else:
            self.connection = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            self.connection.bind(addr)
        self.values = {}
        self._running_ = False

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
            port = int(args[1].decode())
            targets = []
            if key in callback_targets:
                targets = callback_targets[key]
            else:
                callback_targets[key] = targets
            addr = (address[0], port)
            if not addr in targets:
                print(f"New Callback: {key} {addr}")
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
        self.values.clear()

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
        value = self.values[key] if key in self.values else KEY_ERR
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
        for key in self.values.keys():
            value = self.values[key] if key in self.values else KEY_ERR
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
        try:
            key = s_args[0][2:]
            value = s_args[1]
            resp = SETSUCCESS
            if key in self.values and self.values[key][0] != value[0]:
                resp = KEY_ERR_MSG
            else:
                self.values[key] = value
                if key in callback_targets:
                    targets = callback_targets[key]
                    for addr in targets:
                        try:
                            connection = socket.socket()
                            connection.connect(addr)
                            connection.settimeout(0.1)
                            msg = self.pack_get(key, value)
                            connection.sendto(msg, addr)
                            connection.shutdown(socket.SHUT_RDWR)
                            connection.close()
                            pass
                        except Exception as err:
                            targets.remove(addr)
            if conn != None:
                conn.send(resp)
            else:
                self.connection.sendto(resp, address)
        except Exception as err:
            print(f'error setting value {err}')

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

def make_server_threads():
    server_tcp = BaseDataServer(tcp=True, addr=("0.0.0.0", 30002))
    server_udp = BaseDataServer(tcp=False, addr=("0.0.0.0", 20002))

    thread_tcp = server_tcp.make_thread()
    thread_tcp.start()

    thread_udp = server_udp.make_thread()
    thread_udp.start()

    return (server_tcp, thread_tcp), (server_udp, thread_udp)

if __name__ == "__main__":
    # construct a server
    (server_tcp, _), (server_udp, _) = make_server_threads()
    # Then wait for enter to be pressed before stopping
    input("")
    server_tcp._running_ = False
    server_udp._running_ = False
    server_tcp.close()
    time.sleep(0.5)