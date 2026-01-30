import serial
import time
from serial.tools import list_ports

def open_com_by_serial(ftdi_serial, baud=115200, timeout=1):
    """
    Opens a USB-serial device by its FTDI serial number.
    Returns a Serial object.
    """
    port_name = None
    for p in list_ports.comports():
        if p.serial_number == ftdi_serial:
            port_name = p.device
            break
    if port_name is None:
        raise RuntimeError(f"Device {ftdi_serial} not found")
    
    ser = serial.Serial(
        port=port_name,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout
    )
    return ser

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
    ser = open_com_by_serial(FTDI_SERIAL, baud=115200)

    # Send message
    send_rs485_message(ser, TX_MESSAGE)

    # Close port
    close_port(ser)

    print("Message sent successfully.")

if __name__ == "__main__":
    main()