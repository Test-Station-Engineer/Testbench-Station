# pyvisa_test.py

import pyvisa as visa
rm = visa.ResourceManager('@py')
print(rm.list_resources())

from serial.tools import list_ports

print("VISA backend:", rm)
print("VISA resources:")
for r in rm.list_resources():
    print("  ", r)

print("\nPySerial ports:")
for p in list_ports.comports():
    print(
        f"  device={p.device!r}, "
        f"description={p.description!r}, "
        f"manufacturer={p.manufacturer!r}, "
        f"product={p.product!r}, "
        f"serial={p.serial_number!r}, "
        f"VID={p.vid!r}, "
        f"PID={p.pid!r}"
    )