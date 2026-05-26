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
TARGET_VID = 0x10C4
TARGET_PID = 0xEA60
TARGET_SN = "0001"

# Linak Smart Desk Interface (VID/PID shared by all Linak SMDs)
# TARGET_VID = 0x303A
# TARGET_PID = 0x1001

HOST = "127.0.0.1"
PORT = 5555

# Checks Windows, else checks Linux/Mac temp folder
LOCK_PATH = os.path.join(os.environ.get("TEMP", "/tmp"),
                         "node_serial_monitor.lock")

SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.1

# =========================
# Argparse
# =========================
parser = argparse.ArgumentParser()
parser.add_argument(
    "--oneshot",
    action="store_true",
    help="Exit automatically when all TCP clients disconnect",
)
parser.add_argument(
    "--lock",
    action="store_true",
    help="Enable single-instance lock",
)
parser.add_argument(
    "--vid",
    type=lambda x: int(x, 0),  # supports hex like 0x2341
    default=None,
    help="USB vendor ID",
)

parser.add_argument(
    "--pid",
    type=lambda x: int(x, 0),  # supports hex like 0x0043
    default=None,
    help="USB product ID",
)

parser.add_argument(
    "--sn",
    type=str,
    help="USB serial number",
)
parser.add_argument(
    "--port",
    type=int,
    default=5555,
    help="TCP port to listen on",
)
args = parser.parse_args()
ENABLE_LOCKING = args.lock

# =========================
# Global state
# =========================
serial_handle = None            # NOTE Added for TCP serial Tx
serial_lock = threading.Lock()  # NOTE Added for TCP serial Tx

clients = set()
clients_lock: threading.Lock = threading.Lock()
running = threading.Event()
running.set()

# =========================
# Lock handling
# =========================
'''def acquire_lock(): # NOTE Keeping here for learning purposes, had help with the new one
    if not ENABLE_LOCKING:
        return False
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r") as f:
                pid = int(f.read().strip()) 
            os.kill(pid, 0) # Check if process is alive
        except (OSError, ValueError):
            # Stale lock file, remove it
            try:
                os.unlink(LOCK_PATH)
            except OSError as e:
                print(f"Warning: could not remove stale lock file: {e}")
                pass
        else:
            return True # NOTE Might be reversed

    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    return False'''
def acquire_lock():
    if not ENABLE_LOCKING:
        return None

    try:
        # O_CREAT | O_EXCL guarantees atomic creation
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        return fd

    except FileExistsError:
        # Lock file exists — check whether owner is alive
        try:
            with open(LOCK_PATH, "r") as f:
                pid = int(f.read().strip())

            os.kill(pid, 0)

            # Process exists
            return None

        except (OSError, ValueError):
            # Stale lock
            try:
                os.unlink(LOCK_PATH)
            except OSError:
                return None

            # Retry once
            return acquire_lock()
        
'''
def release_lock():
    if not ENABLE_LOCKING:
        return
    try:
        os.unlink(LOCK_PATH)
    except OSError:
        pass
'''
def release_lock(fd):
    if fd is not None:
        os.close(fd)
        try:
            os.unlink(LOCK_PATH)
        except FileNotFoundError:
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
def tcp_accept_thread(port_id: int = PORT):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # server.bind((HOST, PORT))
    server.bind((HOST, port_id))
    server.listen()
    server.settimeout(0.5)

    # print(f"[monitor] TCP listening on {HOST}:{PORT}")
    print(f"[monitor] TCP listening on {HOST}:{port_id}")

    while running.is_set():
        try:
            conn, addr = server.accept()
            # conn.setblocking(False)         # NOTE Suggestion: I need to learn more about this, removing for TCP Tx.
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

    while running.is_set():
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            # Previous version didn't set running to False on EOFError, only did break
            running.clear()
            break

        try:
            with serial_lock:
                ser.write(b"\x03")

            time.sleep(0.05)
            # Then send operator command
            with serial_lock:
                ser.write(line.encode("ascii") + b"\r\n")
        except OSError:
            running.clear()
            break


# =========================
# Serial reader
# =========================
def serial_reader(port):
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
        running.clear()
        ser.close()
        print("[monitor] Serial port closed")


# =========================
# Signal handling
# =========================
def handle_signal(signum, frame):
    running.clear()

# =========================
# Main
# =========================
def main(vid = None, pid = None, serial_number = None, tcp_port: int = PORT) -> bool:
    lock_fd = acquire_lock()
    if ENABLE_LOCKING and lock_fd is None:
        print("[monitor] Another instance is already running")
        sys.exit(1)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        port = find_device_port(vid=vid,pid=pid,serial_number=serial_number)
        # port = find_device_port()

        t_tcp = threading.Thread(
            # target=tcp_accept_thread(tcp_port),
            target=tcp_accept_thread,
            args=(tcp_port,),
            daemon=True
        )
        t_tcp.start()

        serial_reader(port)

    finally:
        release_lock(lock_fd)
        with clients_lock:
            for c in list(clients): # NOTE Added list() here to avoid "Set changed size during iteration" if clients disconnect while we're closing them
                try:
                    c.close()
                except OSError:
                    pass
        print("[monitor] Exiting")


if __name__ == "__main__":
    if args.vid is None and args.pid is None and args.sn is None:
        print("[monitor] Warning: No device identifiers specified, will attempt to Default set serial device")
        main(pid=TARGET_PID, vid=TARGET_VID)
    else: main(vid = args.vid, pid = args.pid, serial_number = args.sn)
    