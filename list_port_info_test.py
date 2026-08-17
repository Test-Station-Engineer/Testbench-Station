from serial import Serial
from serial.tools import list_ports

import pyvisa

load_mach_res = "USB0::62700::5665::SDL13GCC7R0069::0::INSTR"
    
for p in list_ports.comports():
    print(f"Device:       {p.device}")
    print(f"Description:  {p.description}")
    print(f"Manufacturer: {p.manufacturer}")
    print(f"Serial:       {p.serial_number}")
    print(f"VID:          {p.vid}")
    print(f"PID:          {p.pid}")
    print(f"HWID:         {p.hwid}")
    print(f"Product:      {p.product}")
    print(f"Interface:    {p.interface}")
    print()


rm = pyvisa.ResourceManager()

for resource in rm.list_resources("?*USB?*INSTR"):
    print(resource)