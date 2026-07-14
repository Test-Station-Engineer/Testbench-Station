# load.py
# el_SDL1020X-E
import pyvisa as visa

found_device = False
is_open = False
device = 0
res_els = [
'USB0::62700::5665::SDL13GCC7R0064::0::INSTR',
'USB0::62700::5665::SDL13GCC7R0069::0::INSTR',
'ASRL4::INSTR',
'ASRL/dev/ttyUSB0::INSTR'
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
            #print(res)
            if res == res_el:
                device = rm.open_resource(res_el)
                found_device = True
                #print('Found Electronic Load')
                break
    if not found_device:
        print('\033[3;91mCould not find Electronic Load\033[0m')
        return False
    # device = rm.open_resource(res_el)
    device.timeout = 10000
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

"""def safeWrite(msg): # TODO TEST THIS LATER
    if not is_open:
        return 'Device not open'

    device.write(msg)
    device.query('*OPC?')  # wait until operation complete
    return 'OK'"""

def measureFloat(msg):
    if is_open:
        return float(query(msg))
    else:
        return 0

def measureVoltage():
    return measureFloat('MEAS:VOLT?')

def measurePower():
    return measureFloat('MEAS:POW?')

def measureCurrent():
    return measureFloat('MEAS:CURR?')

def setOutputOn(state: bool):
    if state:
        return write('INPUT ON')
    else:
        return write('INPUT OFF')

'''def setOutputOn(state: bool): # TODO TEST THIS LATER
    if not is_open:
        return 'Device not open'

    current = isOutputOn()

    if state and current:
        return 'Already ON'
    if not state and not current:
        return 'Already OFF'

    return write('INPUT ON' if state else 'INPUT OFF')'''

def setMode(mode: str):
    if mode == 'CRM':
        return write('MODE CRM')
    if mode == 'CV':
        return write('MODE CV')
    if mode == 'CCH':
        return write('MODE CCH')
    
'''def setMode(mode: str): # TODO TEST THIS LATER
    if not is_open:
        return 'Device not open'

    current = getMode()
    if current == mode:
        return 'Already in mode ' + mode

    return write(f'MODE {mode}')'''

def setVoltage(value):
#     write(':SOUR:FUNC VOLT')
#     return write(':SOUR:VOLT:LEV:IMM '+"{:.3f}".format(value))
    write('MODE CV')
    return write('VOLT '+"{:.3f}".format(value))

def setPower(value):
#     write(':SOUR:FUNC POW')
#     return write(':SOUR:POW:LEV:IMM '+"{:.3f}".format(value))
    write('MODE CPC')
    return write('POW '+"{:.3f}".format(value))

def setCurrent(value):
    # write(':SOUR:FUNC CURR')
    # return write(':SOUR:CURR:LEV:IMM '+"{:.3f}".format(value))
    write('MODE CCH')
    return write('CURR '+"{:.3f}".format(value))

def setResistance(value):
#     write(':SOUR:FUNC RES')
#     return write(':SOUR:RES:LEV:IMM '+"{:.3f}".format(value))
    if value < 200: write('MODE CRM')
    else: write('MODE CRH')
    return write('RES '+"{:.3f}".format(value))

# Extra helper functions #NOTE Need to incorporate these and test them later.

def isOutputOn():
    if is_open:
        try:
            query_result = query('INPUT?')
            print(f"\033[3;92mDEBUG: Received response from load machine device: '{query_result}'\033[0m")  # Debug print
            return query_result in ['1', 'ON']
        except:
            print("\033[3;91mError querying load machine output state.\033[0m")
            return False
    return False

def getMode():
    if is_open:
        return query('MODE?')
    return 'UNKNOWN'

def getVoltage():
    return measureFloat('VOLT?')

def getCurrentSetpoint():
    return measureFloat('CURR?')

def getPowerSetpoint():
    return measureFloat('POW?')

def getResistance():
    return measureFloat('RES?')

def clearStatus():
    if is_open:
        write('*CLS')  # clear status + error queue

def getErrors():
    if is_open:
        return query('SYST:ERR?')
    return 'Device not open'