import sys
import time
import serial
from serial.tools import list_ports

# # CP210X USB‑to‑UART Bridge (common, adjust if needed)
# TARGET_VID = 0x10C4
# TARGET_PID = 0xEA60
# TARGET_SN = "0001"

try:
    from . import parse_monitor as parser
except ImportError:
    import services.parse_monitor as parser

# =====================
# Configuration
# =====================
# RS485_VID = 403
# RS485_PID = 6001
SHUTDOWN_MONITOR: bool = False
MONITOR_VID = 0x303A
MONITOR_PID = 0x1001
MONITOR_TCP_PORT = 5555

RS485_SN: str = "BG01EHULA"
RS485_BAUD_RATE = 115200

RTS_PRE_DELAY = 0.005
RTS_POST_DELAY = 0.05

RS485_MESSAGE = ( # Default message if not overwritten
    b"IF YOU'RE SEEING THIS MESSAGE, THAT MEANS THE RS485 LINK WORKS\r\n"
)
ANCHOR = b"IF YOU'RE SEEING THIS MESSAGE"

# =========================
# RS‑485 transmit logic
# =========================
# def find_ftdi_port(serial_number: str) -> str:
#     com_ports = list_ports.comports()
#     for p in com_ports:
#         if p.serial_number == serial_number:
#             return p.device
#     raise RuntimeError("FTDI adapter not found")

def find_rs485_port(serial_number: str) -> str:
        if serial_number is None:
            raise ValueError("At least one identifier must be specified")
        ports_list = list_ports.comports()
        for p in ports_list:
            if p.serial_number == serial_number:
                return p.device
        raise RuntimeError("Target serial device not found")

def send_rs485_message(message: bytes):
    """
    Opens FTDI, asserts RTS, transmits message.
    """
    rs485_port = find_rs485_port(serial_number=RS485_SN)
    print(f"[rs485] Found device on {rs485_port}")
    with serial.Serial(rs485_port, RS485_BAUD_RATE, timeout=1) as ser:
        ser.rts = False
        time.sleep(0.05)

        ser.rts = True
        time.sleep(RTS_PRE_DELAY)

        ser.write(message)
        ser.flush()

        time.sleep(RTS_POST_DELAY)
        ser.rts = False
    time.sleep(0.2)

# =====================
# Main test flow
# =====================
def main(message: bytes = RS485_MESSAGE):
    print("[rs485] Connecting to monitor...")
    sock = parser.ensure_monitor_running(
        vid=MONITOR_VID,
        pid=MONITOR_PID,
        port=MONITOR_TCP_PORT,
        detach_monitor=True,
    )

    try:
        print("[rs485] Transmitting RS‑485 message...")
        send_rs485_message(message)

        print("[rs485] Waiting for response...")
        passed = parser.wait_for_response(sock, message=ANCHOR)

    finally:
        try:
            if SHUTDOWN_MONITOR:
                parser.shutdown_monitor(sock)
        finally:
            sock.close()

    if passed:
        print("[rs485] PASS: RS‑485 message observed")
        # sys.exit(0)
        return True
    else:
        print("[rs485] FAIL: No RS‑485 message received")
        # sys.exit(1)
        return False
    # return passed

if __name__ == "__main__":
    main()