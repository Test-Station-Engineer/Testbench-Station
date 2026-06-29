from .services import parse_monitor as parser

import sys
from socket import socket
from serial.tools import list_ports
from dataclasses import dataclass
import threading

VID = 0x303A
PID = 0x1001

PORT = 5555

ANCHOR = b"occupied false"

TIMEOUT = 180

@dataclass
class DeviceInfo:
    com_port: str
    serial_number: str | None

@dataclass
class TestResult:
    device: DeviceInfo
    passed: bool
    error: str | None = None

def enumerate_devices() -> list[DeviceInfo]:
    """Finds all serial devices matching VID/PID."""
    devices: list[DeviceInfo] = []
    for p in list_ports.comports():
        if p.vid == VID and p.pid == PID:
            devices.append(
                DeviceInfo(
                    com_port=p.device,
                    serial_number=p.serial_number
                )
            )
    return devices


def ensure_verbose_monitor(sock: socket):
    '''Sends a "v\r\n" command to the monitor to enable verbose mode, then waits for confirmation. 
    \nHas a retry loop to account for if verbosity was pre-enabled and made false by this running the first time.'''
    attempts: int = 0
    while attempts < 5:
        sock.sendall(b"v\r\n")
        if parser.wait_for_response(
            sock, 
            message=b"sensors verbose true", 
            timeout=0.25
        ):
            return
        attempts += 1
    raise ValueError("Verbose mode failed to enable or detect enabling, check monitor if open")


def test_device(
    device: DeviceInfo,
    tcp_port: int,
    results: list[TestResult],
    lock: threading.Lock,
):
    """Thread worker for a single device."""
    
    serial_port = device.serial_number
    sock: socket | None = None
    
    try:
        print(
            f"[{device.com_port}] "
            f"Starting monitor on TCP {tcp_port}"
        )
        sock: socket = parser.ensure_monitor_running(
            vid=VID, 
            pid=PID, 
            port=tcp_port, 
            serial_port=serial_port,
            detach_monitor=True,
        )
        print(f"[{device.com_port}] Connected")

        ensure_verbose_monitor(sock)

        print(f"[{device.com_port}] Waiting for occupancy shift...")

        passed = parser.wait_for_response(sock, message=ANCHOR, timeout=TIMEOUT)

        result = TestResult(device=device, passed=passed)

    except Exception as e:

        result = TestResult(
            device=device,
            passed=False,
            error=str(e)
        )
    
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
    
    with lock:
        results.append(result)

def print_summary(results: list[TestResult]):
    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    passed_count = 0

    for result in results:
        name = result.device.com_port

        if result.device.serial_number:
            name += f" ({result.device.serial_number})"

        if result.passed:
            print(f"[PASS] {name}")
            passed_count += 1
        else:
            if result.error:
                print(f"[FAIL] {name} :: {result.error}")
            else:
                print(f"[FAIL] {name} :: Occupancy timeout")
    print()
    print(
        f"Passed {passed_count}/{len(results)} device(s)"
    )


def main():
    # sock: socket = parser.ensure_monitor_running(vid=VID, pid=PID, port=PORT)
    # print(sock)
    # ensure_verbose_monitor(sock)

    # try:
    #     print("[occupancy] Waiting for response...")
    #     passed = parser.wait_for_response(sock, message=ANCHOR, timeout=120)
    # finally:
    #     sock.close()
    # if passed:
    #     print("[occupancy] PASS: Occupancy shift observed")
    #     sys.exit(0)
    # else:
    #     print("[occupancy] FAIL: No Occupancy shift received")
    #     sys.exit(1)
    devices = enumerate_devices()
    if not devices:
        print(
            f"No devices found "
            f"(VID=0x{VID:04X}, PID=0x{PID:04X})"
        )
        sys.exit(1)

    print()
    print(f"Found {len(devices)} matching device(s)")
    print()

    for d in devices:
        print(
            f"  - {d.com_port}"
            + (
                f" [{d.serial_number}]"
                if d.serial_number else ""
            )
        )

    print()

    threads: list[threading.Thread] = []

    results: list[TestResult] = []

    lock = threading.Lock() # NOTE Explain this

    # Launch one thread per device #
    for index, device in enumerate(devices):

        # Each monitor needs its own TCP port #
        monitor_port = PORT + index
        t = threading.Thread(
            target=test_device,
            args=(
                device,
                monitor_port,
                results,
                lock # NOTE Explain this
            ),
            daemon=True # NOTE Explain this
        )

        t.start()
        threads.append(t)

    # Wait for all threads to complete
    for t in threads:
        t.join() # NOTE Explain this

    print_summary(results)
    # Exit code #
    all_passed = all(r.passed for r in results) # NOTE Explain this
    sys.exit(0 if all_passed else 1) # NOTE Explain this

if __name__ == "__main__":
    main()
