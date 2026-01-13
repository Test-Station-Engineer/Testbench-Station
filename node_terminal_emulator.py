import serial
import serial.tools.list_ports
import threading

import sys
import time

TARGET_VID = 0x10C4
TARGET_PID = 0xEA60
TARGET_SN = "0001"   # From USB\VID_10C4&PID_EA60\0001

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
                # print(data.decode(errors="replace"), end="")
                sys.stdout.write(data.decode(errors="replace"))
                sys.stdout.flush()
        except Exception as e:
            print(f"\nReader error: {e}")
            break

def main():
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
    except KeyboardInterrupt:
        ser.close()
        print("Closed.")


if __name__ == "__main__":
    main()
