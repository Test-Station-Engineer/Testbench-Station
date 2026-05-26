import serial
import time
from serial.tools import list_ports

from frontend import prompt

# NOTE New
from services.unused.node_serial_monitor_old import SerialMonitor, find_device_port
import serial
# =========================

def open_com_by_serial(ftdi_serial, baud=115200, timeout=1):
    """
    Opens a USB-serial device by its FTDI serial number.
    Returns a Serial object or None if ignored.
    """
    while True:
        port_name = None

        for p in list_ports.comports():
            if p.serial_number == ftdi_serial:
                port_name = p.device
                break

        if port_name is not None:
            # Device found → open and return
            return serial.Serial(
                port=port_name,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout
            )

        # Device NOT found → show prompt
        result = prompt.abort_retry_ignore_prompt(
            title="RS485 Device Not Found",
            message=(
                f"Device {ftdi_serial} not found.\n\n"
                "Make sure the RS485 cable is connected and powered.\n"
                "You may need to reset the cable.\n\n"
                "Retry to search again, Abort to stop, or Ignore to continue without it."
            )
        )

        if result == "retry":
            continue  # loop again and rescan ports

        elif result == "abort":
            raise RuntimeError(f"Device {ftdi_serial} not found")

        elif result == "ignore":
            return None  # or handle differently if needed

def send_rs485_message(ser, message, rts_pre_delay=0.005, rts_post_delay=0.05):
    """
    Sends a message over RS-485 using RTS to toggle TX/RX direction.
    'ser' is a Serial object already opened.
    """
    try:
        ser.rts = True              # Enable transmitter
        time.sleep(rts_pre_delay)

        ser.write(message)          # Send message
        ser.flush()                 # Flush serial buffer

        time.sleep(rts_post_delay)  # Ensure last byte is transmitted
    finally:
        ser.rts = False             # Return to receive mode

def close_port(ser):
    if ser and ser.is_open:
        ser.close()

def main():
    FTDI_SERIAL = "BG01EHULA"
    TX_MESSAGE = b"Testing: IF YOU'RE SEEING THIS MESSAGE, THAT MEANS THAT THIS DEVICE PASSED THE TEST FOR RS-485 COMMUNICATION! YOU MAY CONTINUE!\r\n"

    # Open the port
    rs485_serial = open_com_by_serial(FTDI_SERIAL, baud=115200)

    # # Send message (moved below for timing with monitor)
    # send_rs485_message(ser, TX_MESSAGE)

    # NOTE Monitor Serial Stuff
    port = find_device_port()
    monitor_serial = serial.Serial(port, 115200, timeout=0.1)

    monitor = SerialMonitor(monitor_serial)
    monitor.start()

    send_rs485_message(rs485_serial, TX_MESSAGE)

    if monitor.wait_for(target="RX: Testing:", timeout=10):
        print("✅ PASS")
        passed: bool = True
    else:
        print("❌ FAIL")
        passed: bool = False
    # =========================

    close_port(rs485_serial) # Close rs485 port

    # print("Message sent successfully.")
    return passed

if __name__ == "__main__":
    main()