# load.py
# el_SDL1020X-E
import pyvisa as visa

found_device = False
is_open = False
device = 0
res_els = [
'USB0::62700::5665::SDL13GCC7R0064::0::INSTR',
'USB0::62700::5665::SDL13GCC7R0069::0::INSTR'
]

def open():
    global is_open
    if is_open:
        return
    global found_device
    global device
    rm = visa.ResourceManager('@py')
    found_device = False
    for res in rm.list_resources():
        for res_el in res_els:
            if res == res_el:
                found_device = True
                #print('Found Electronic Load')
                break
    if not found_device:
        print('Could not find Electronic Load')
        return False
    device = rm.open_resource(res_el)
    is_open = True
    return True

def close():
    global is_open
    if is_open:
        is_open = False
        device.close()

def query(msg):
    if is_open:
        return device.query(msg).strip()
    else:
        return 'Device not open'

def write(msg):
    if is_open:
        #print(msg) # debug
        device.write(msg)
        return 'OK'
    else:
        return 'Device not open'

def measureFloat(msg):
    if is_open:
        return float(query(msg))
    else:
        return 0

def measureVoltage():
    return measureFloat('MEAS:VOLT:DC?')

def measurePower():
    return measureFloat('MEAS:POW:DC?')

def measureCurrent():
    return measureFloat('MEAS:CURR:DC?')

def setOutputOn(on):
    if on:
        return write(':SOUR:INP:STAT ON')
    else:
        return write(':SOUR:INP:STAT OFF')

def setVoltage(value):
    write(':SOUR:FUNC VOLT')
    return write(':SOUR:VOLT:LEV:IMM '+"{:.3f}".format(value))

def setPower(value):
    write(':SOUR:FUNC POW')
    return write(':SOUR:POW:LEV:IMM '+"{:.3f}".format(value))

def setCurrent(value):
    write(':SOUR:FUNC CURR')
    return write(':SOUR:CURR:LEV:IMM '+"{:.3f}".format(value))

def setResistance(value):
    write(':SOUR:FUNC RES')
    return write(':SOUR:RES:LEV:IMM '+"{:.3f}".format(value))
