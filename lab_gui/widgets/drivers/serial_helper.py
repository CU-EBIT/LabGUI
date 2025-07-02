import serial.tools.list_ports

def find_devices(desc_matcher=lambda x:True, hwid_matcher=lambda x:True, verbose=False):
    ports = serial.tools.list_ports.comports()
    _ports = []
    for port, desc, hwid in sorted(ports):
            if verbose:
                print("{}: {} [{}]".format(port, desc, hwid))
            if desc_matcher(desc) and hwid_matcher(hwid):
                  if verbose:
                        print("Matched!")
                  _ports.append(port)
    return _ports

if __name__ == "__main__":
      find_devices(verbose=True)