import socket
import subprocess
import sys
import time
import os
import select

MONITOR_HOST = "127.0.0.1"
MONITOR_PORT = 5555

MONITOR_SCRIPT = "node_serial_monitor.py"

MONITOR_START_TIMEOUT = 2.0
MONITOR_RETRY_DELAY = 0.2

RECV_TIMEOUT_SEC = 3.0


def try_connect_to_monitor() -> socket.socket | None:
    try:
        s = socket.create_connection(
            (MONITOR_HOST, MONITOR_PORT),
            timeout=0.5,
        )

        s.setblocking(False)
        return s

    except OSError as e:
        print(f"[parser] Monitor connection failed: {e}")
        return None

def ensure_monitor_running(detach_monitor: bool = True) -> socket.socket:
    """
    Connect to existing monitor or launch one.
    """

    sock = try_connect_to_monitor()

    if sock:
        return sock

    print("[parser] Monitor not running, starting it...")

    creationflags = 0

    if os.name == "nt":
        if detach_monitor:
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP |
                subprocess.DETACHED_PROCESS |
                0
            )
        else:
            creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0)

    subprocess.Popen(
        [sys.executable, MONITOR_SCRIPT],
        stdout=None,
        stderr=None,
        creationflags=creationflags,
    )

    # Retry loop
    deadline = time.monotonic() + MONITOR_START_TIMEOUT
    while time.monotonic() < deadline:
        sock = try_connect_to_monitor()

        if sock:
            # print(sock)
            return sock

        time.sleep(MONITOR_RETRY_DELAY)

    raise RuntimeError("Monitor failed to start")

def wait_for_response(
    sock: socket.socket,
    message: bytes,
    timeout=RECV_TIMEOUT_SEC
) -> bool:

    start = time.monotonic()
    buffer = bytearray()

    if message is None:
        raise ValueError("message must not be None")

    if isinstance(message, str):
        message = message.encode("utf-8")

    while time.monotonic() - start < timeout:

        r, _, _ = select.select([sock], [], [], 0.1)

        if not r:
            continue

        try:
            data = sock.recv(4096)

            if not data:
                return False

            buffer.extend(data)

        except BlockingIOError:
            continue

        if message in buffer:
            return True

    return False

def shutdown_monitor(sock: socket.socket):
    try:
        sock.sendall(b"__EXIT__")
    except OSError:
        pass