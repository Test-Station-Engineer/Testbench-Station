# controller.py
import serial
import io
import time
import threading

detect_board_version = ''
board_version = ''
dfd_version = ''
expected_version = ''
dfu_version = ''
golden_version = ''
serial_number = ''
ip = ''
inx_ip = ''
tftp_ip = ''
cccv1 = ''
cccv2 = ''
maxwatt1 = 0
maxwatt2 = 0
pwm_frequency = 0

RELAY_24V_1        = 0
RELAY_OUTPUT1      = 1
RELAY_OUTPUT2      = 2
RELAY_24V_2        = 3

def initValues():
    global detect_board_version, board_version, dfd_version
    global dfu_version, golden_version, serial_number
    global ip, inx_ip, tftp_ip, cccv1, cccv2
    global maxwatt1, maxwatt2, pwm_frequency
    detect_board_version = ''
    board_version = ''
    dfd_version = ''
    expected_version = ''
    dfu_version = ''
    golden_version = ''
    serial_number = ''
    ip = ''
    inx_ip = ''
    tftp_ip = ''
    cccv1 = ''
    cccv2 = ''
    maxwatt1 = 0
    maxwatt2 = 0
    pwm_frequency = 0

ser = serial.Serial()
lines = []
rx_line = ''
print_rx = False # Set true to debug
rx_thread_running = False
rx_thread_started = False
def rxThreadFunction(name):
    global lines, rx_line
    while(rx_thread_running):
        if ser.is_open:
            c = ser.read().decode(errors='replace')
            #print(c, end='')
            if(c=='\r'):
                if len(rx_line) > 0 and rx_line.find('Writing EEPROM')<0 and \
                        rx_line.find('overwrite string')<0 and \
                        rx_line.find('Trap')<0 and rx_line.find('Prph')<0 and \
                        rx_line.find('strheap')<0 and rx_line.find('inserted word')<0:
                    if len(lines) > 30:
                        del lines[0] # pop a line to limit length of list
                    lines.append(rx_line.strip())
                    if print_rx:
                        print(' rx:',rx_line)
                if len(rx_line) > 0:
                    rx_line = ''
            elif(c!='\n'):
                rx_line = rx_line + c

rx_thread = threading.Thread(target=rxThreadFunction, args=(1,), daemon=True)

def open(port,baud,timeout):
    ser.baudrate = baud
    ser.port = port
    ser.timeout = timeout
    try:
        ser.open()
    except:
        print('Could not find Controller')
    return ser.is_open

def close():
    global rx_thread_running
    if ser.is_open:
        rx_thread_running = False
        ser.close()

def startRXThread():
    global rx_thread_running, rx_thread_started
    rx_thread_running = True
    if not rx_thread_started:
        rx_thread_started = True
        rx_thread.start()

def setPrintRX(enable):
    global print_rx
    print_rx = enable

def flushLines():
    global lines
    lines = []

def popFirstLine():
    global lines
    if len(lines) > 0:
        one = lines[0]
        del lines[0]
        return one
    else:
        return None

def readLines(num,timeout):
    counter = 0
    while(counter < timeout and len(lines)<num):
        counter = counter + 1
        time.sleep(0.001)

def readLine(do_print):
    timeout = 0
    pop_line = popFirstLine()
    #while(pop_line == None):
    #    pop_line = popFirstLine()
    #    #time.sleep(0.001)
    #    timeout = timeout + 1
    #    if(timeout > 2000):
    #        break
    line = ''
    if pop_line != None:
        line = pop_line
    if do_print:
        print(' read:',line)
    return line

def getLine():
    readLines(1,200)
    return readLine(False)

def writeConsole(msg):
    flushLines()
    console_msg = 'write_console '
    ser.write(console_msg.encode('utf-8')) # encode bytes
    ser.write(msg) # assume msg is bytes

def writeCMD(cmd):
    msg = cmd + '\r\n'
    writeConsole(msg.encode('utf-8'))

def writeConsoleReadCOM(msg):
    flushLines()
    console_msg = 'write_console_read_com '
    ser.write(console_msg.encode('utf-8')) # encode bytes
    ser.write(msg) # assume msg is bytes
    readLines(3,200)
    readLine(False)
    readLine(False)
    return readLine(False)

def writeCOMReadConsole(msg):
    flushLines()
    console_msg = 'write_com_read_console '
    ser.write(console_msg.encode('utf-8')) # encode bytes
    ser.write(msg) # assume msg is bytes
    readLines(3,200)
    readLine(False)
    readLine(False)
    return readLine(False)

def setLoadLED(enable):
    if enable:
        msg = 'set_load_led on\r\n'
    else:
        msg = 'set_load_led off\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(2,2000)

# rev6
def detectBoardVersion():
    global detect_board_version
    flushLines()
    msg = b'get_board_version\r\n'
    ser.write(msg)
    readLines(2,2000)
    readLine(False)
    detect_board_version = readLine(False)
    return detect_board_version

# board_version rev6
def getBoardVersion():
    global board_version
    flushLines()
    writeConsole(b'get_board_version\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('get')<0 and line.find('board')>-1 and len(line) > 14:
            board_version = line[14:].strip()
            return board_version
    return board_version

# DFD_Ver: 2out v
def getDFDVersion():
    global dfd_version
    flushLines()
    writeConsole(b'get_dfd_ver\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('DFD')>-1 and len(line) > 9:
            dfd_version = line[9:].strip()
            return dfd_version
    return dfd_version

# Expected_Ver: 2out
def getExpectedVersion():
    global expected_version
    flushLines()
    writeConsole(b'get_expected_ver\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('Expected')>-1 and len(line) > 14:
            expected_version = line[14:].strip()
            return expected_version
    return expected_version

# DFU_Ver: 2out v Jun 27 2023 11:56z37
def getDFUVersion():
    global dfu_version
    flushLines()
    writeConsole(b'get_dfu_ver\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('DFU')>-1 and len(line) > 9:
            dfu_version = line[9:]
            return dfu_version
    return dfu_version

# Golden_Ver: 2out v Jun 16 2023 12:50:09
def getGoldenVersion():
    global golden_version
    flushLines()
    writeConsole(b'get_golden_ver\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('Golden')>-1 and len(line) > 12:
            golden_version = line[12:].strip()
            return golden_version
    return golden_version

# Node SN : 12345
def getSN():
    global serial_number
    flushLines()
    writeConsole(b'get_sn\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
        if line.find('SN')>-1 and len(line) > 10:
            serial_number = line[10:].strip()
            return serial_number
    return serial_number

def setSN(new_sn):
    flushLines()
    msg = 'set_sn '+new_sn+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)

def isValidIPStr(ip_str):
    ip_str_split = ip_str.split(".")
    if len(ip_str_split) != 4:
        return False
    for oct in ip_str_split:
        if not oct.isnumeric():
            return False
        if int(oct)<0 or int(oct)>255:
            return False
    return True

# IP Address: 192.168.1.46
def getIP():
    global ip
    flushLines()
    #writeConsole(b'get_ip\r\n')
    writeConsole(b'show_ip\r\n')
    #readLines(4,2000)
    readLines(4,1000)
    for i in range(0,4):
        line = readLine(False)
        #if len(line) > 12:
            #ip = line[12:]
        if line.find(":")>-1:
            ip_str = line[line.find(":")+2:]
            if isValidIPStr(ip_str):
                ip = ip_str
    return ip

# INXIP: 10.10.0.50
def getINXIP():
    global inx_ip
    flushLines()
    writeConsole(b'get_inxip\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
    if len(line) > 7:
        inx_ip = line[7:]
    return inx_ip 

def setINXIP(new_ip):
    flushLines()
    msg = 'set_inxip '+new_ip+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)

# TFTP Server IP 10.10.0.50
def getTFTPIP():
    global tftp_ip
    flushLines()
    writeConsole(b'get_tftp_ip\r\n')
    readLines(3,2000)
    for i in range(0,3):
        line = readLine(False)
    if len(line) > 15:
        tftp_ip = line[15:]
    return tftp_ip 

def setTFTPIP(new_ip):
    flushLines()
    msg = 'set_tftp_ip '+new_ip+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)

# DRV1: 0
def getCCCV(channel):
    global cccv1, cccv2
    flushLines()
    msg = 'get_cccv '+str(channel)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)
    for i in range(0,channel+2):
        line = readLine(False)
    cccv_stage = ''
    if len(line) > 6:
        cccv_stage = line[6:]
        if channel == 1:
            cccv1 = cccv_stage
        elif channel == 2:
            cccv2 = cccv_stage
    return cccv_stage

def setCCCV(channel,stage):
    flushLines()
    msg = 'set_cccv '+str(channel)+' '+str(stage)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(8,2000)

# write_console get_max_watt
# get_max_watt
#
# Maxw1: 713
# Maxw2: 713
def getMaxWatt(channel):
    global maxwatt1, maxwatt2
    flushLines()
    msg = 'get_max_watt '+str(channel)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)
    for i in range(0,channel+2):
        line = readLine(False)
    maxwatt = 0
    if len(line) > 6:
        try:
            maxwatt = float(line[6:])/10
        except:
            a = 1
        if channel == 1:
            maxwatt1 = maxwatt
        elif channel == 2:
            maxwatt2 = maxwatt
    return maxwatt

def setMaxWatt(channel,maxwatt):
    flushLines()
    msg = 'set_max_watt '+str(channel)+' '+str(maxwatt*10)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(5,2000)

# write_console get_dim
# get_dim
# dim1: 61
# dim2z 10
def getDim(channel):
    flushLines()
    msg = 'get_dim\r\n'
    readLines(4,2000)
    for i in range(0,4):
        line = readLine(False)
        if line.find('dim'+str(channel))>-1 and len(line)>6:
            line = line[6:].strip()
            dim = 0
            try:
                dim = int(line)
            except:
                print("Did not find dim in controller console")
                dim = 0
            return dim
    return 0

def setDim(channel,dim):
    flushLines()
    dim = min(100,max(0,dim))
    msg = 'set_dim '+str(channel)+' '+str(dim)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,2000)

def setDimRetry(channel,dim,retries):
    for i in range(0,retries):
        setDim(channel,dim)
        if getDim(channel) == dim:
            return True
    return False

def setRelays(channel):
    flushLines()
    msg = 'set_relays '+str(channel)+'\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(1,2000)

def setMux(channel):
    flushLines()
    msg = 'set_mux '+str(channel)+'\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(1,200)

def getMux():
    flushLines()
    msg = 'get_mux_channel\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(3,200) # Need to check to see if this is right - Drew
    for i in range(0,3):
        line = readLine(False)
        #print(line)
        if line.find('Mux channel') > -1 and len(line) > 21:
            #print("Found")
            mux_channel = line[21:].strip()
            mux_channel=int(mux_channel)
            return mux_channel
        
def setPush4BTNOn():
    flushLines()
    msg = 'set_push_4BTN_On\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(1,2000)

def setPush4BTNOff():
    flushLines()
    msg = 'set_push_4BTN_Off\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(1,2000)

def getV010V():
    flushLines()
    msg = 'get_0-10V\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(3,200)
    readLine(False)
    line = readLine(False)
    val = 0
    try:
        val = float(line)
    except:
        a = 1
    return val

def setAux(channel,enable,response):
    flushLines()
    if enable:
        msg = 'set_aux'+str(channel)+' true\r\n'
    else:
        msg = 'set_aux'+str(channel)+' false\r\n'
    ser.write(msg.encode('utf-8'))
    readLines(3,50)
    line = readLine(False)
    for i in range(0,3): 
        if line.find(response) > -1:
            return line
        line = readLine(False)
    return line

def setPWMFrequency(frequency):
    flushLines()
    msg = 'set_pwmfreq '+str(frequency)+'\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(3,2000)

# PWM Frequency 25000Hz
def getPWMFrequency():
    global pwm_frequency
    flushLines()
    msg = 'get_pwmfreq\r\n'
    writeConsole(msg.encode('utf-8'))
    readLines(4,3000)
    for i in range(0,4):
        line = readLine(False)
        if line.find('PWM') > -1 and len(line)>14:
            line = line[14:-2]
            try:
                pwm_frequency = float(line)
            except:
                a = 1
    return pwm_frequency

def resetConsole():
    flushLines()
    writeConsole(b' ') # reset console
    readLines(3,200)
    flushLines()
