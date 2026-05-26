from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port="COM6",
    baudrate=9600,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

client.connect()

for addr in range(0, 20):
    result = client.read_holding_registers(address=addr, count=1, device_id=1)
    if not result.isError() and result.registers:
        print(f"Address {addr:04X} → {result.registers[0]}")
    else:
        print(f"Address {addr:04X} → empty")

client.close()