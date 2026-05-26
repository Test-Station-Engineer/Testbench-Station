import socket
import threading
import sys
import time
import signal
import os
import argparse

import serial  # pyserial
from serial.tools import list_ports

# =========================
# DEVICE CONFIG
# =========================
TARGET_VID = 0x10C4
TARGET_PID = 0xEA60
TARGET_SN = "0001"

HOST = "127.0.0.1"
PORT = 5555

# LOCK_PATH = "/tmp/node_serial_monitor.lock"
# On Windows, you might want something like:
LOCK_PATH = os.path.join(os.environ["TEMP"], 
                         "node_serial_monitor.lock")

SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.1  # seconds

# -------------------------
# Argparse
# -------------------------
parser = argparse.ArgumentParser()
parser.add_argument(
    "--oneshot",
    action="store_true",
    help="Exit automatically when all TCP clients disconnect",
)
args = parser.parse_args()

# -------------------------
# Global state
# -------------------------
clients: set[socket.socket] = set()
clients_lock: threading.Lock = threading.Lock()
running: bool = True

# -------------------------
# Lock handling
# -------------------------
'''def acquire_lock():
    if os.path.exists(LOCK_PATH):
        return False
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True'''

def acquire_lock():
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)   # check if process exists
        except (OSError, ValueError):
            # Stale lock file, remove it
            try:
                os.unlink(LOCK_PATH)
            except OSError as e:
                print(f"Warning: could not remove stale lock file: {e}")
                pass
        else:
            return False

    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    try:
        os.unlink(LOCK_PATH)
    except OSError:
        pass

# -------------------------
# Utilities
# -------------------------
def find_device_port():
    ports = list_ports.comports()
    for p in ports:
        if (p.vid == TARGET_VID
            and p.pid == TARGET_PID
            and p.serial_number == TARGET_SN):
            return p.device
    # return None
    raise RuntimeError("Target serial device not found")


# -------------------------
# TCP server
# -------------------------
def tcp_accept_thread():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(0.5)

    print(f"[monitor] TCP listening on {HOST}:{PORT}")

    while running:
        try:
            conn, addr = server.accept()
            conn.setblocking(False)
            with clients_lock:
                clients.add(conn)
            print(f"[monitor] Client connected: {addr}")
        except socket.timeout:
            continue
        except OSError:
            break

    server.close()


def broadcast(data: bytes):
    dead = []
    with clients_lock:
        for c in clients:
            try:
                c.sendall(data)
            except OSError:
                dead.append(c)

        for c in dead:
            try:
                c.close()
            except OSError:
                pass
            clients.remove(c)

    # New one adds global running access, 
    # checks arg.oneshot, 
    # and not clients



# -------------------------
# Operator Input Thread
# -------------------------
def operator_input_thread(ser):
    """Allows an operator to type commands and send them to the serial port"""
    global running 

    while running:
        try:
            line = input()
            ser.write(b"\x03")
            time.sleep(0.05)
        except EOFError:
            break
        except KeyboardInterrupt:
            running = False
            break

        if not running: break

        try: ser.write(line.encode("ascii") + b"\r\n")
        except OSError: break


# -------------------------
# Serial reader
# -------------------------
def serial_reader(port):
    global running

    ser = serial.Serial(
        port=port,
        baudrate=SERIAL_BAUD,
        timeout=SERIAL_TIMEOUT,
    )

    print(f"[monitor] Opened serial port {port}")

    try:
        while running:
            data = ser.read(4096)
            if not data:
                continue

            input_thread = threading.Thread(
                target=operator_input_thread,
                args =(ser,),
                daemon=True
            )
            input_thread.start()

            # Operator visibility
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            except Exception:
                pass

            # Fan-out to clients
            broadcast(data)

    finally:
        running = False
        ser.close()
        print("[monitor] Serial port closed")


# -------------------------
# Signal handling
# -------------------------
def handle_signal(signum, frame):
    global running
    running = False


# -------------------------
# Main
# -------------------------
def main():
    if not acquire_lock():
        print("[monitor] Another instance is already running")
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        port = find_device_port()

        t_tcp = threading.Thread(
            target=tcp_accept_thread,
            daemon=True
        )
        t_tcp.start()

        serial_reader(port)

    finally:
        release_lock()
        with clients_lock:
            for c in clients:
                try:
                    c.close()
                except OSError:
                    pass
        print("[monitor] Exiting")


if __name__ == "__main__":
    main()
