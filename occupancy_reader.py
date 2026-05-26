from services import parse_monitor as parser

import sys

from socket import socket

VID = 0x303A
PID = 0x1001

ANCHOR = b"occupied false"

def ensure_verbose_monitor(sock: socket):
    '''Sends a "v\r\n" command to the monitor to enable verbose mode, then waits for confirmation. 
    \nHas a retry loop to account for if verbosity was pre-enabled and made false by this running the first time.'''
    attempts: int = 0
    while attempts < 5:
        sock.sendall(b"v\r\n")
        if parser.wait_for_response(sock, message=b"sensors verbose true", timeout=0.25):
            return
        else:
            attempts += 1
            continue
    raise ValueError("Verbose mode failed to enable or detect enabling, check monitor if open")
        
def main():
    sock: socket = parser.ensure_monitor_running()
    ensure_verbose_monitor(sock)

    try:
        print("[occupancy] Waiting for response...")
        passed = parser.wait_for_response(sock, message=ANCHOR, timeout=120)
    finally:
        sock.close()
    if passed:
        print("[occupancy] PASS: Occupancy shift observed")
        sys.exit(0)
    else:
        print("[occupancy] FAIL: No Occupancy shift received")
        sys.exit(1)

if __name__ == "__main__":
    main()
