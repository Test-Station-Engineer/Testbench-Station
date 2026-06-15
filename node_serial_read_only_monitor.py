import socket
import threading
import sys
import time
import signal
import os
import argparse

import serial
from serial.tools import list_ports

# =========================
# DEVICE CONFIG
# =========================
# TARGET_VID = 0x10C4
# TARGET_PID = 0xEA60
# TARGET_SN = "0001"
TARGET_VID = 0x303A
TARGET_PID = 0x1001

HOST = "127.0.0.1"
PORT = 5555

# LOCK_PATH = "/tmp/node_serial_monitor.lock"
# On Windows, you might want something like:
LOCK_PATH = os.path.join(os.environ.get("TEMP", "/tmp"),
                         "node_serial_monitor.lock")

SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.1


serial_handle = None            # NOTE Added for TCP serial Tx
serial_lock = threading.Lock()  # NOTE Added for TCP serial Tx


# =========================
# Argparse
# =========================
parser = argparse.ArgumentParser()
parser.add_argument(
    "--oneshot",
    action="store_true",
    help="Exit automatically when all TCP clients disconnect",
)
args = parser.parse_args()

# =========================
# Global state
# =========================
clients = set()
clients_lock: threading.Lock = threading.Lock()
# running: bool = True # NOTE Threads that use this may not be synchronous, can cause problems down the line.
running = threading.Event()
running.set()

# =========================
# Lock handling
# =========================
'''def acquire_lock():
    if os.path.exists(LOCK_PATH):
        return False
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return True'''

def acquire_lock():
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # check if process still exists
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

# =========================
# Utilities
# =========================
def find_device_port(vid=None, pid=None, serial_number=None) -> str:
    if vid is None and pid is None and serial_number is None:
        raise ValueError("At least one identifier must be specified")

    for p in list_ports.comports():
        if (
            (vid is None or p.vid == vid) and
            (pid is None or p.pid == pid) and
            (serial_number is None or p.serial_number == serial_number)
        ):
            return p.device

    raise RuntimeError("Target serial device not found")

# =========================
# TCP server + broadcast
# =========================
def tcp_accept_thread():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(0.5)

    print(f"[monitor] TCP listening on {HOST}:{PORT}")

    # while running:
    while running.is_set():
        try:
            conn, addr = server.accept()
            # conn.setblocking(False)     # NOTE Suggestion: I need to learn more about this, removing for TCP Tx.
            with clients_lock:
                clients.add(conn)
            print(f"[monitor] Client connected: {addr}")

            t = threading.Thread(         # NOTE Added this for sending TCP messages back to serial
                target=tcp_client_reader, # NOTE Added this for sending TCP messages back to serial
                args=(conn, addr),        # NOTE Added this for sending TCP messages back to serial
                daemon=True,              # NOTE Added this for sending TCP messages back to serial
            )                             # NOTE Added this for sending TCP messages back to serial
            t.start()                     # NOTE Added this for sending TCP messages back to serial

        except socket.timeout:
            continue
        except OSError:
            break

    server.close()


def broadcast(data: bytes):
    # global running
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

        if args.oneshot and not clients:
            # running = False
            running.clear()

def tcp_client_reader(conn, addr):
    global serial_handle

    print(f"[monitor] RX thread started for {addr}")

    try:
        while running.is_set():
            data = conn.recv(4096)

            if not data:
                break

            print(f"[tcp rx] {addr}: {data!r}")

            with serial_lock:
                if serial_handle:
                    serial_handle.write(data)

    except OSError:
        pass

    finally:
        print(f"[monitor] Client disconnected: {addr}")

        with clients_lock:
            if conn in clients:
                clients.remove(conn)

        try:
            conn.close()
        except OSError:
            pass

# =========================
# Operator input thread
# =========================
def operator_input_thread(ser):
    """Allows an operator to type commands and send them to the serial port"""
    # global running

    # while running:
    while running.is_set():
        try:
            line = input()
            ser.write(b"\x03")
            time.sleep(0.05)
        except (EOFError, KeyboardInterrupt):
            # Previous version didn't set running to False on EOFError, only did break
            # running = False
            running.clear()
            break

        try:
            ser.write(line.encode("ascii") + b"\r\n")
        except OSError:
            # running = False
            running.clear()
            break


# =========================
# Serial reader
# =========================
def serial_reader(port):
    # global running
    global serial_handle

    ser = serial.Serial(
        port=port,
        baudrate=SERIAL_BAUD,
        timeout=SERIAL_TIMEOUT,
    )
    
    serial_handle = ser

    print(f"[monitor] Opened serial port {port}")

    input_thread = threading.Thread(
        target=operator_input_thread,
        args=(ser,),
        daemon=True,
    )
    input_thread.start()

    try:
        # while running:
        while running.is_set():
            data = ser.read(4096)
            if not data:
                continue

            # Operator visibility
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            except Exception:
                pass

            # Fan-out to clients
            broadcast(data)

    finally:
        # running = False
        running.clear()
        ser.close()
        print("[monitor] Serial port closed")


# =========================
# Signal handling
# =========================
def handle_signal(signum, frame):
    # global running
    # running = False
    running.clear()


# =========================
# Main
# =========================

def main(vid = None, pid = None, serial_number = None):
    if not acquire_lock():
        print("[monitor] Another instance is already running")
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        port = find_device_port(vid=vid,pid=pid,serial_number=serial_number)
        # port = find_device_port()

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
    main(vid=TARGET_VID, pid=TARGET_PID)
    