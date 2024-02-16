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
FILLER = b"??"
BUFSIZE = 1024

# Server -> client messages
SETSUCCESS = SUCCESS + DALIM + SET
ALLSUCCESS = SUCCESS + DALIM + ALL
MODE_ERR_MSG = MODE_ERR + DALIM + MODE_ERR
KEY_ERR_MSG = KEY_ERR + DALIM + KEY_ERR
HELLO_FROM_SERVER = HELLO + DALIM + HELLO
CLOSED = SUCCESS + DALIM + CLOSE

ADDR = ("127.0.0.1", 20002)

class BaseDataServer:
    '''Python server implementation'''
    def __init__(self, addr=ADDR) -> None:
        self.addr = addr
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
        }

    def run(self):
        '''run loop entry point for the server, probably best to run via a separate thread'''
        self._running_ = True

        while(self._running_):
            self.connection = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            # Bind to self for listening
            self.connection.bind(self.addr)
            self.run_loop()
            # Close connection when done
            self.connection.close()

    def on_open(self, address, _):
        '''processes the OPEN comand, presently doesn't do anything'''
        # TODO Decide if we want multiple threads for python version?
        self.connection.sendto(OPEN+DALIM+str(self.addr[1]).encode(), address)

    def on_close(self, address, _):
        '''processes the CLOSE comand, presently doesn't do anything'''
        # TODO Decide if we want multiple threads for python version?
        self.connection.sendto(CLOSED, address)

    def on_clear(self, address, _):
        '''processes the CLEAR command, and clears the values map'''
        self.values.clear()

    def on_hello(self, address, _):
        '''processes the HELLO command and responds with a pong'''
        self.connection.sendto(HELLO_FROM_SERVER, address)

    def on_get(self, address, data):
        '''processes the GET command, and responds with the value in the map, or KEY_ERR'''
        key = data[2:]
        value = self.values[key] if key in self.values else KEY_ERR
        msg = key+DALIM+value
        size = len(msg)
        var = struct.pack('<bb', size&31, size >> 5)
        msg = var + msg
        # Sending a reply to client
        self.connection.sendto(msg, address)

    def on_get_all(self, address, _):
        '''processes the ALL command, and responds with all values in the map, and then ALLSUCCESS'''
        for key in self.values.keys():
            value = self.values[key] if key in self.values else KEY_ERR
            msg = key+DALIM+value
            size = len(msg)
            var = struct.pack('<bb', size&31, size >> 5)
            msg = var + msg
            # Sending a reply to client
            self.connection.sendto(msg, address)
        self.connection.sendto(ALLSUCCESS, address)

    def on_set(self, address, data):
        '''processes the SET command, and responds with SETSUCCESS'''
        s_args = data.split(DALIM)
        try:
            key = s_args[0][2:]
            self.values[key] = s_args[1]
            # print(f'set {key} {unpack_value(data)} from: {address}')
            self.connection.sendto(SETSUCCESS, address)
        except Exception as err:
            print(f'error setting value {err}')

    def run_loop(self):
        '''The contents of the run loop, this waits for messages and responds to them accordingly'''
        bytesAddressPair = self.connection.recvfrom(BUFSIZE)
        try:
            message = bytesAddressPair[0]
            address = bytesAddressPair[1]

            args = message.split(DELIM)
            mode = args[0]
            if len(args) > 1:
                data = args[1]
            else:
                data = b''

            if mode in self.functions:
                self.functions[mode](address, data)
            else:
                self.connection.sendto(MODE_ERR, address)

        except Exception as err:
            print(err)

    def make_thread(self):
        '''Makes a daemon thread that runs our run loop when started'''
        thread = threading.Thread(target=self.run, daemon=True)
        return thread

if __name__ == "__main__":
    # construct a server
    server = BaseDataServer()
    # have it make a thread, and start it
    thread = server.make_thread()
    print("Starting Data Server")
    thread.start()
    # Then wait for enter to be pressed before stopping
    input("Enter to exit")
    server._running_ = False
    time.sleep(0.1)