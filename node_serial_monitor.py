import socket
import threading
import sys
import time
import signal
import argparse

import serial
from serial.tools import list_ports


class SerialTcpMonitor:
    def __init__(
        self,
        host: str = "127.0.0.1",
        tcp_port: int = 5555,
        baudrate: int = 115200,
        serial_timeout: float = 0.1,
        enable_operator_input: bool = True,
        log_to_file: bool = False,
        log_file_path: str = "serial_monitor.log",
    ):
        self.host = host
        self.tcp_port = tcp_port
        self.baudrate = baudrate
        self.serial_timeout = serial_timeout
        self.enable_operator_input = enable_operator_input

        self.log_to_file = log_to_file
        self.log_file_path = log_file_path
        self.log_handle = None

        self.serial_handle = None
        self.serial_lock = threading.Lock()

        self.clients = set()
        self.clients_lock = threading.Lock()

        self.running = threading.Event()
        self.running.set()

    # =========================
    # Utilities
    # =========================
    @staticmethod
    def find_device_port(vid=None, pid=None, serial_number=None) -> str:
        if vid is None and pid is None and serial_number is None:
            raise ValueError("At least one identifier must be specified")

        for p in list_ports.comports():
            if (
                (vid is None or p.vid == vid)
                and (pid is None or p.pid == pid)
                and (serial_number is None or p.serial_number == serial_number)
            ):
                return p.device

        raise RuntimeError("Target serial device not found")

    # =========================
    # TCP server
    # =========================
    def tcp_accept_thread(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server.bind((self.host, self.tcp_port))
        server.listen()
        server.settimeout(0.5)

        print(f"[monitor] TCP listening on {self.host}:{self.tcp_port}")

        try:
            while self.running.is_set():
                try:
                    conn, addr = server.accept()

                    with self.clients_lock:
                        self.clients.add(conn)

                    print(f"[monitor] Client connected: {addr}")

                    t = threading.Thread(
                        target=self.tcp_client_reader,
                        args=(conn, addr),
                        daemon=True,
                    )
                    t.start()

                except socket.timeout:
                    continue

                except OSError:
                    break

        finally:
            server.close()

    def broadcast(self, data: bytes):
        dead = []

        with self.clients_lock:
            for c in self.clients:
                try:
                    c.sendall(data)

                except OSError:
                    dead.append(c)

            for c in dead:
                try:
                    c.close()
                except OSError:
                    pass

                self.clients.remove(c)

    def tcp_client_reader(self, conn, addr):
        print(f"[monitor] RX thread started for {addr}")

        try:
            while self.running.is_set():
                data = conn.recv(4096)

                if not data:
                    break

                if data == b"__EXIT__":                     # NOTE Added for shutdown handling. I don't like it.
                    print("[monitor] Shutdown requested")   # NOTE Added for shutdown handling. I don't like it.
                    self.running.clear()                    # NOTE Added for shutdown handling. I don't like it.
                    break                                   # NOTE Added for shutdown handling. I don't like it.

                print(f"[tcp rx] {addr}: {data!r}")

                with self.serial_lock:
                    if self.serial_handle:
                        self.serial_handle.write(data)

        except OSError:
            pass

        finally:
            print(f"[monitor] Client disconnected: {addr}")

            with self.clients_lock:
                if conn in self.clients:
                    self.clients.remove(conn)

            try:
                conn.close()
            except OSError:
                pass

    # =========================
    # Operator input
    # =========================
    def operator_input_thread(self):
        while self.running.is_set():
            try:
                line = input()

            except (EOFError, KeyboardInterrupt):
                self.running.clear()
                break

            try:
                with self.serial_lock:
                    if self.serial_handle:
                        self.serial_handle.write(b"\x03")

                time.sleep(0.05)

                with self.serial_lock:
                    if self.serial_handle:
                        self.serial_handle.write(
                            line.encode("ascii") + b"\r\n"
                        )

            except OSError:
                self.running.clear()
                break

    # =========================
    # Serial reader
    # =========================
    def serial_reader(self, port):
        ser = serial.Serial(
            port=port,
            baudrate=self.baudrate,
            timeout=self.serial_timeout,
        )

        self.serial_handle = ser
        print(f"[monitor] Opened serial port {port}")

        if self.log_to_file:
            self.log_handle = open(self.log_file_path, "ab")
            print(f"[monitor] Logging serial output to {self.log_file_path}")


        if self.enable_operator_input:
            input_thread = threading.Thread(
                target=self.operator_input_thread,
                daemon=True,
            )
            input_thread.start()

        try:
            while self.running.is_set():
                data = ser.read(4096)

                if not data:
                    continue

                # Local console visibility          # NOTE Replaced with write_output() helper method
                # try:                              # NOTE Replaced with write_output() helper method
                #     sys.stdout.buffer.write(data) # NOTE Replaced with write_output() helper method
                #     sys.stdout.buffer.flush()     # NOTE Replaced with write_output() helper method

                # except Exception:                 # NOTE Replaced with write_output() helper method
                #     pass                          # NOTE Replaced with write_output() helper method
                self.write_output(data)

                # Send to TCP clients
                self.broadcast(data)

        finally:
            self.running.clear()

            try:
                ser.close()
            except OSError:
                pass

            self.serial_handle = None
            print("[monitor] Serial port closed")

    # =========================
    # Write Output
    # =========================
    def write_output(self, data: bytes):
        # Console output
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except Exception:
            pass

        # Optional log file output
        if self.log_handle:
            try:
                self.log_handle.write(data)
                self.log_handle.flush()
            except Exception:
                pass

    # =========================
    # Shutdown
    # =========================
    def stop(self):
        self.running.clear()

        with self.clients_lock:
            for c in list(self.clients):
                try:
                    c.close()
                except OSError:
                    pass

        if self.serial_handle:
            try:
                self.serial_handle.close()
            except OSError:
                pass

    # =========================
    # Main
    # =========================
    def run(self, vid=None, pid=None, serial_number=None):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        try:
            port = self.find_device_port(
                vid=vid,
                pid=pid,
                serial_number=serial_number,
            )

            t_tcp = threading.Thread(
                target=self.tcp_accept_thread,
                daemon=True,
            )
            t_tcp.start()

            self.serial_reader(port)

        finally:
            self.stop()
            print("[monitor] Exiting")

    def handle_signal(self, signum, frame):
        self.running.clear()


# =========================
# CLI
# =========================
if __name__ == "__main__":
    # CP210X USB‑to‑UART Bridge (common, adjust if needed)
    # TARGET_VID = 0x10C4
    # TARGET_PID = 0xEA60
    # TARGET_SN = "0001"

    # Linak Smart Desk Interface (VID/PID shared by all Linak SMDs)
    TARGET_VID = 0x303A
    TARGET_PID = 0x1001

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--vid",
        type=lambda x: int(x, 0),
        default=None,
        help="USB vendor ID",
    )

    parser.add_argument(
        "--pid",
        type=lambda x: int(x, 0),
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
        help="TCP port",
    )

    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Disable local terminal input forwarding",
    )

    args = parser.parse_args()

    monitor = SerialTcpMonitor(
        tcp_port=args.port,
        enable_operator_input=not args.readonly,
    )
    if args.vid is None and args.pid is None and args.sn is None:
        print("No device identifiers specified, defaulting to VID/PID for stored CP210X USB-to-UART Bridge")
        args.vid = TARGET_VID
        args.pid = TARGET_PID
    monitor.run(
        vid=args.vid,
        pid=args.pid,
    )