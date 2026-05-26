import serial
import serial.tools.list_ports
import threading

import sys
import time

import os 
import signal
import tempfile
import atexit

from datetime import datetime

# NOTE New
from threading import Lock, Condition 
rx_buffer = ""
rx_buffer = rx_buffer[-4096:]
rx_lock = Lock()
rx_cond = Condition(rx_lock)

TARGET_MESSAGE = "RX: Testing: IF YOU'RE SEEING THIS MESSAGE"

TARGET_VID = 0x10C4
TARGET_PID = 0xEA60
TARGET_SN = "0001"   # From USB\VID_10C4&PID_EA60\0001

# Lock file (single instance)
# =========================
LOCK_PATH = os.path.join(
    tempfile.gettempdir(),
    "node_terminal_emulator.lock"
)

lock_fd = None

def acquire_lock():
    global lock_fd
    try:
        lock_fd = os.open(
            LOCK_PATH,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY
        )
        os.write(lock_fd, str(os.getpid()).encode())
    except FileExistsError:
        print("node_terminal_emulator already running.")
        sys.exit(0)

def release_lock():
    global lock_fd
    try:
        if lock_fd is not None:
            os.close(lock_fd)
        if os.path.exists(LOCK_PATH):
            os.unlink(LOCK_PATH)
    except Exception:
        pass

atexit.register(release_lock)

def handle_signal(_signum, _frame):
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

ENABLE_LOGGING = True
log_file = None


# Logging utilities NOTE Not used yet, enable with ENABLE_LOGGING = True above
# =========================
def open_log(test_id):
    global log_file
    os.makedirs("logs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = open(f"logs/{test_id}_{ts}.log", "w", buffering=1)

def close_log():
    global log_file
    if log_file:
        log_file.close()
        log_file = None

def print_and_log(line: str):
    print(line)
    if ENABLE_LOGGING and log_file:
        log_file.write(line + "\n")
# =========================

# Basic terminal emulator to connect to a node over serial and print output
# =========================
def find_device_port():
    """Return COM port matching VID, PID, and serial."""
    ports = serial.tools.list_ports.comports() 
    for p in ports:
        if (p.vid == TARGET_VID 
            and p.pid == TARGET_PID
            and p.serial_number == TARGET_SN):
            return p.device 
    return None 

def reader_thread(ser):
    """Reads data from the serial port and writes it to the console."""
    while True:
        try:
            data = ser.read(ser.in_waiting or 1)
            if data:
                text = data.decode(errors="replace")
                # print(data.decode(errors="replace"), end="")
                sys.stdout.write(text)
                sys.stdout.flush()

                # NOTE New
                with rx_cond:
                    rx_buffer += text
                    # Prevent runaway memory growth
                    if len(rx_buffer) > 8192:
                        rx_buffer = rx_buffer[-4096:]
                    
                    rx_cond.notify_all()

        except Exception as e:
            print(f"\nReader error: {e}")
            break
# =========================

# Event/Buffer stuff
# =========================
def wait_for_message(target = TARGET_MESSAGE, timeout=5, clear_on_match=True):
    """
    Wait until `target` substring appears in serial input.
    Returns True if found, False if timeout.
    """
    global rx_buffer

    end_time = time.time() + timeout

    with rx_cond:
        while True:
            if target in rx_buffer:
                if clear_on_match:
                    rx_buffer = ""
                return True

            remaining = end_time - time.time()
            if remaining <= 0:
                return False

            rx_cond.wait(timeout=remaining)

'''regex version - not currently used but could be useful for more complex parsing in the future
import re

def wait_for_regex(pattern, timeout=5):
    global rx_buffer
    end_time = time.time() + timeout

    compiled = re.compile(pattern)

    with rx_cond:
        while True:
            match = compiled.search(rx_buffer)
            if match:
                return match.group(0)

            remaining = end_time - time.time()
            if remaining <= 0:
                return None

            rx_cond.wait(timeout=remaining)'''

def main():

    acquire_lock()

    port = find_device_port()

    if not port:
        print("Device not found.")
        return
    
    print(f"Opening {port}...")

    ser = serial.Serial(
        port=port,
        baudrate=115200,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=0.1
    )

    print("Connected. Listening...\n")

    thread = threading.Thread(target=reader_thread, args=(ser,), daemon=True)
    thread.start()

    # Allow typing into the device as well
    try:
        while True:
            cmd = input()

            # Send Ctrl+C to enter command mode, then wait a bit
            ser.write(b"\x03")
            time.sleep(0.05)

            # Send the command
            ser.write((cmd + "\r").encode())
            #ser.flush()
    # except KeyboardInterrupt:
    #     ser.close()
    #     print("Closed.")
    finally:
        # close_log()
        ser.close()
        print("Closed.")


if __name__ == "__main__":
    main()
