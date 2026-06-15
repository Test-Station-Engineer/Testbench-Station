from pymodbus.client import ModbusSerialClient

FTDI_SERIAL = "BG01NAGOA"


client = ModbusSerialClient(
    port="COM7",
    baudrate=9600,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

if not client.connect():
    raise Exception("Could not open serial port")

result = client.read_holding_registers(
    address=0x0000,     # F0-0 (percent*10)
    count=1,
    device_id=1         # <- correct for your version
)

if result.isError():
    print("Modbus error:", result)
else:
    # print("Result:", result)
    # print("Is error:", result.isError())
    # print("Registers:", getattr(result, "registers", None))
    # print("Type:", type(result))
    raw = result.registers[0]
    percent = raw / 100.0
    print(f"{percent} Volts")

client.close()