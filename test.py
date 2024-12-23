# test.py

#Probably newest version
import controller
import coap_client
import load
import database
import json
import time
import sys
import coap_client_scan
import subprocess

import os
import csv

#import battery_backup as batt
from pynput import keyboard

stop_on_failure = True
update_golden = False
require_golden_match = False
debug_print = False
dfd_match_required = False

test_id = '1'
serial_number = ''
custom_sn = ''
mac_address = ''
board_version = ''

port = '/dev/ttyUSB0'
baud = 115200
timeout = 0 # use RX thread

scan_sn = False

maxw_save = None
cccv_save = None

CC_json = False
CV_json = False

# Battery Backup Settings
battery_backup_test = False
await_key: str = 'w'

#Commissioning
commissioning = False



def updateState(method,msg,state,description):
    print(method,msg)
    data = {
        "CurrentState":state,
        "Description":description
    }
    database.updateTestTable(data, test_id)

def updateLog(*args):
    desc = ''
    for arg in args:
        if desc == '':
            desc = str(arg)
        else:
            desc += ' '+str(arg)
    if desc != '':
        print(desc)
        database.updateTestLog(test_id,serial_number,board_version,desc)

test_config = None
def loadTestJSON():
    global test_config
    file_name = 'test.json'
    if CV_json:
        file_name = 'test_CV.json'
    if CC_json:
        file_name = 'test_CC.json'
    if battery_backup_test:
        file_name = 'test_battery_backup.json'
    try:
        with open(file_name) as f:
            test_config = json.load(f)
            updateLog(test_config)
            return True
    except:
        return False

ip = ''
def getIP():
    global ip
    updateLog('getIP','start')
    if scan_sn:
        if 'subnet' in test_config:
            coap_client_scan.subnet = test_config['subnet']
        else:
            host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE).stdout.decode('utf-8').split(' ')[0]
            host_ip_split = host_ip.split('.')
            host_ip_split[3] = '255'
            coap_client_scan.subnet = '.'.join(host_ip_split)
        print('scan subnet',coap_client_scan.subnet,'for sn',serial_number)
        coap_client_scan.serial_number = serial_number
        coap_client_scan.scan()
        for node in coap_client_scan.nodes:
            print(node['ip'],node['network']['serialnum'])
            if node['network']['serialnum'] == serial_number:
                ip = node['ip']
                print('scan found sn',serial_number,'at',ip)
                updateLog('getIP',ip)
                return True
    else:
        for i in range(0,20):
            controller.ip = ''
            ip = controller.getIP()
            if ip != '':
                updateLog('getIP',ip)
                return True
    updateLog('getIP','failed')
    return False

def testSubnet(subnet):
    ip_split = ip.split('.')
    subnet_split = subnet.split('.')
    if len(ip_split) != 4:
        updateLog('testSubnet','fail ip length')
        return False
    if len(subnet_split) != 4:
        updateLog('testSubnet','fail subnet length')
        return False
    for i in range(0,4):
        if subnet_split[i] == '255':
            return True
        if ip_split[i] != subnet_split[i]:
            updateLog('testSubnet','fail subnet mismatch')
            return False
    updateLog('testSubnet','ip == subnet')
    return True

def testCodeVersion(code_version):
    dfu = coap_client.getDFUVersion(ip)
    golden = coap_client.getGoldenVersion(ip)
    dfd = coap_client.getDFDVersion(ip)
    if dfu != code_version:
        updateLog('testCodeVersion','fail dfu',dfu)
        return False
    if golden != code_version:
        updateLog('testCodeVersion','fail golden',golden)
        if update_golden:
            updateLog('testCodeVersion','update golden')
            coap_client.putValue(ip,'/dfu','updt',0)
            elapsed = 0
            while elapsed < 100:
                time.sleep(1.0)
                elapsed += 1
                #print('\r waiting for reboot: ',str(elapsed),endl='') # Returns an error - Drew
            golden = coap_client.getGoldenVersion(ip)
            if require_golden_match == True:
                if  golden != code_version:
                    updateLog('testCodeVersion','fail golden',golden)
                    return False
        elif require_golden_match == True:
            return False
    if dfd_match_required and dfd != code_version:
        updateLog('testCodeVersion','fail dfd',dfd)
        return False
    return True

def testSerialNumber(sn):
    if not scan_sn:
        coap_client.setSN(ip,str(sn))
    get_sn = coap_client.getSN(ip)
    if get_sn != str(sn):
        updateLog('testSerialNumber','fail get',get_sn)
        return False
    return True

def testBoardVersion(bv):
    # no set board version
    get_bv = coap_client.getBoardVersion(ip)
    if get_bv != str(bv):
        updateLog('testBoardVersion','fail get',get_bv)
        return False
    return True

def testCMD(cmds):
    for cmd in cmds:
        coap_client.putValue(ip,'/network','cmd',str(cmd))
        time.sleep(1)
    return True


def testCCCV(cccv):
    global cccv_save
    cccv_save = cccv
    coap_client.putValue(ip,'/actuators/actuator1','cccv',str(cccv))
    if not battery_backup_test or not 'battery_backup_loads' in test_config or not cccv == 10: # Accounts for when you are doing a battery backup test
        coap_client.putValue(ip,'/actuators/actuator2','cccv',str(cccv))
    cccv1 = coap_client.getValue(ip,'/actuators/actuator1','cccv')
    cccv2 = coap_client.getValue(ip,'/actuators/actuator2','cccv')
    if cccv1 != str(cccv):
        updateLog('testCCCV','fail actuator1',cccv1)
        return False
    
    if not battery_backup_test or not 'battery_backup_loads' in test_config: # Accounts for when you are doing a battery backup test
        if cccv2 != str(cccv):
            updateLog('testCCCV','fail actuator2',cccv2)
            return False
    return True

def testMAXW(maxw):
    global maxw_save
    global commissioning
    maxw_save = maxw
    commissioned = False
    coap_client.putValue(ip,'/actuators/actuator1','maxw',str(maxw))
    coap_client.putValue(ip,'/actuators/actuator2','maxw',str(maxw))

    
    if "maxw_commission" in test_config and maxw == test_config['maxw_commission'] and commissioning:
        time.sleep(8.0) # This is done to save the max watt information to EEPROM - Drew
        commissioning = False # Will need to improve this later - Drew
        commissioned = True

    maxw1 = coap_client.getValue(ip,'/actuators/actuator1','maxw')
    maxw2 = coap_client.getValue(ip,'/actuators/actuator2','maxw')
    
    if maxw1 != str(maxw):
        updateLog('testMAXW','fail actuator1',maxw2)
        return False
    if maxw2 != str(maxw):
        updateLog('testMAXW','fail actuator2',maxw2)
        return False
    
    if commissioned:  # Need to refine this later - Drew
        updateLog('Max watt commissioned to',maxw1)

    return True

def testLoad(test_load):
    if 'cccv' in test_load:
        if test_load['cccv'] != cccv_save:
            if testCCCV(test_load['cccv']):
                updateLog('testCCCV','pass',test_load['cccv'])
    if 'maxw' in test_load:
        if test_load['maxw'] != maxw_save:
            if testCCCV(test_load['maxw']):
                updateLog('testMAXW','pass',test_load['maxw'])
    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and 'dim' in test_load and 'power' in test_load:
        coap_client.setDim(ip,3,test_load['dim'])
        dim1 = coap_client.getDim(ip,1)
        dim2 = coap_client.getDim(ip,2)
        if dim1 != test_load['dim']:
            updateLog('testLoad',1,'fail set dim',dim1)
            return False
        if dim2 != test_load['dim']:
            updateLog('testLoad',2,'fail set dim',dim2)
            return False

        if battery_backup_test: relays = ['output1'] # Accounts for when you are doing a battery backup test 
        else: relays = ['output1','output2']

        #print(relays)

        for relay in relays:
            controller.setRelays(relay)
            if 'CR' in test_load:
                load.setResistance(test_load['CR'])
            if 'CC' in test_load:
                load.setCurrent(test_load['CC'])
            if 'CV' in test_load:
                load.setVoltage(test_load['CV'])
            #coap_client.setDim(ip,3,'90') # Improve. Check to see if this is needed in all cases. - Drew
            #time.sleep(2.75)
            #coap_client.setDim(ip,3,'100')
            #time.sleep(3.0)
            load.setOutputOn(True)
            time.sleep(5.0)

            # print(coap_client.getDim(ip,1))

            power = load.measurePower()
            load.setOutputOn(False)
            if power < test_load['power']:
                updateLog('testLoad',relay,'fail power',power)
                return False
            updateLog('testLoad',relay,'pass power',power)
        return True
    return True

def testLoads(test_loads):
    test_pass = True
    for test_load in test_loads:
        if not testLoad(test_load):
            test_pass = False
    if test_pass:
        updateLog('testLoads','pass')
        return True 
    updateLog('testLoads','fail')
    return False

# clean up function before return
def returnTestSensor1(ret):
    coap_client.putValue(ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
    coap_client.putValue(ip,'/actuators/actuator1','motdsbl','3') # disable motion
    return ret

def testSensor1(do_test):
    coap_client.putValue(ip,'/sensors/sensor1','eventrisefall','on,off') # change sensor 1 events
    coap_client.putValue(ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
    coap_client.putValue(ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    coap_client.putValue(ip,'/actuators/actuator1','motdsbl','33') # enable motion
    coap_client.setDim(ip,3,0) # clear dim
    controller.setAux(1,False,'') # set Aux1 low
    time.sleep(5.0) # wait for event
    controller.setAux(1,True,'') # set Aux1 high, test rising edge of sensor1
    time.sleep(5.0) # wait for event
    dim1 = coap_client.getDim(ip,1) # dim1 should be 100%
    dim2 = coap_client.getDim(ip,2) # dim2 should be 100%
    if dim1 != 100:
        updateLog('testSensor1','high',1,'fail set dim DREW UPDATE',dim1)
        return returnTestSensor1(False) # DREW note turn aux 1 off if fail
    if dim2 != 100:
        updateLog('testSensor1','high',2,'fail set dim',dim2)
        return returnTestSensor1(False)
    controller.setAux(1,False,'') # set Aux1 low, test falling edge of sensor1
    time.sleep(0.3) # wait for  event
    dim1 = coap_client.getDim(ip,1) # dim1 should be 0%
    dim2 = coap_client.getDim(ip,2) # dim2 should be 0%
    if dim1 != 0:
        updateLog('testSensor1','low',1,'fail set dim',dim1)
        return returnTestSensor1(False)
    if dim2 != 0:
        updateLog('testSensor1','low',2,'fail set dim',dim2)
        return returnTestSensor1(False)
    return returnTestSensor1(True)

def testPDLine(do_test):
    coap_client.putValue(ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
    coap_client.putValue(ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    controller.setPush4BTNOff() # press off button, but ignore event
    coap_client.setDim(ip,3,0) # clear dim, in case off button did not work
    updateLog('Starting PDLine Testing')
    attempts = 0
    while attempts != 10:
        time.sleep(0.25)
        controller.setPush4BTNOn()
        dim1 = coap_client.getDim(ip,1) # dim1 should be 0%
        dim2 = coap_client.getDim(ip,2)
        attempts += 1
        if dim1 == 100 and dim2 == 100:
            updateLog('Attempts:',attempts,dim1,dim2)
            break

    updateLog('Attempts taken for dim 100:', attempts)
    if dim1 != 100:
        updateLog('testPDLine','On',1,'fail set dim',dim1)
        return False
    if dim2 != 100:
        updateLog('testPDLine','On',2,'fail set dim',dim2)
        return False
    attempts = 0
    while attempts != 10:
        time.sleep(0.25)
        controller.setPush4BTNOff()
        dim1 = coap_client.getDim(ip,1) # dim1 should be 0%
        dim2 = coap_client.getDim(ip,2)
        attempts += 1
        if dim1 == 0 and dim2 == 0:
            updateLog('Attempts:',attempts,dim1,dim2)
            break

    if dim1 != 0:
        updateLog('testPDLine','Off',1,'fail set dim',dim1)
        return False
    if dim2 != 0:
        updateLog('testPDLine','Off',2,'fail set dim',dim2)
        return False
    return True

#def switch_test_prompt(keyboard_key: str):
#    print("Press and hold switch test button. Then press ", keyboard_key, " on keyboard when ready.")
#    keyboard.wait(keyboard_key)
#    print("Keep button held")

def send_test_prompt(key, prompt: str,response:str):

    json_key_mapping = { # This is used in send_test_prompt
        "enter": keyboard.Key.enter,
        "space": keyboard.Key.space,
        # Add other keys as needed
    }

    if len(key) > 1:
            # Assuming keyboard.Key has attributes that correspond to the keyboard_key
        #print(key)
        keyboard_key = json_key_mapping.get(key)
        if keyboard_key is None:
            print(f"Key '{key}' does not exist in keyboard.Key.")
            print("Keyboard key is ",keyboard_key)

    else: keyboard_key = key

    print(prompt)

    def on_press(key_input):
        try:
            if key_input == keyboard_key:  # Check if the pressed key matches
                print("Key pressed:", keyboard_key)
                return False  # Stop listener
        except AttributeError:
            pass  # Handle special keys (like Shift, Ctrl, etc.)

    # Set up the listener
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()  # Wait until the key is pressed

    print(response)

def testBatteryLoad(upper_load,lower_load,key,wait_time):

    if not testCCCV(10):
        return False
    coap_client.setDim(ip,3,90)
    #time.sleep(1)
    coap_client.setDim(ip,3,100)

    time.sleep(wait_time)

    if not testLoad(upper_load):
        return False

    if not testCCCV(10): 
        return False
    coap_client.setDim(ip,3,90)
    #time.sleep(1)
    coap_client.setDim(ip,3,100)
    
    send_test_prompt(key,f"Press and hold switch test button. Then press {key} on keyboard when ready.", "Keep button held.")

    time.sleep(wait_time)
    if not testLoad(lower_load): 
        return False
    print("Release button")
    time.sleep(5)
    if not testLoad(upper_load):
        return False
    

# TESTING FEATURE
    coap_client.setDim(ip,3,0)
    if not testCCCV(255): #Replaced cv 0
        return False
    #if not testCCCV(0): 
        #return False
    #coap_client.setDim(ip,3,0) # Commented out

    print("Dim:",coap_client.getDim(ip,1),coap_client.getDim(ip,2),"; CCCV:", coap_client.getCCCV(ip,1),coap_client.getCCCV(ip,2))
    time.sleep(wait_time)


    #send_test_prompt(key, f"Unplug Channel 1, then press {key}","Testing Power Loss Backup")
    #time.sleep(wait_time)

    if not testLoad(lower_load): 
        return False
    
    #send_test_prompt(key, f"Plug in Channel 1, then press {key}","Testing Normal High Load")
    #time.sleep(wait_time)

    if not testCCCV(10): 
        return False
    if not testMAXW(test_config['maxw']): 
        return False
    coap_client.setDim(ip,3,100)
    if not testLoad(upper_load): 
        return False

    print("Remember to unplug pink battery backup connectors when finished testing.")
    return True

def testBatteryBackup(batt_test_load):
    if "Low Load" in batt_test_load: low_load = batt_test_load["Low Load"]
    else: 
        print("No Low Load in json file")
        return False

    if "High Load" in batt_test_load: high_load = batt_test_load["High Load"]
    else:
        print("No High Load in json file")
        return False

    if "await_key" in test_config: await_key = test_config["await_key"]
    else: await_key = 'p'

    if "await_time" in test_config: batt_wait_time = test_config["await_time"]
    else: batt_wait_time = 2

    if not testBatteryLoad(high_load,low_load,await_key,batt_wait_time):
        return False

    return True

def runTest():
    global mac_address
    global commissioning
    global battery_backup_test

    coap_client.putValue(ip,'/network','cmd','set_ws 0')
    coap_client.putValue(ip,'/network','cmd','set_max_amp 3 2500')
    
    if not battery_backup_test:
        sn = coap_client.getSN(ip)
        mac_address = coap_client.getMAC(ip)
        updateLog('SN: ',sn, 'MAC: ',mac_address)
    
    if 'subnet' in test_config:
        if testSubnet(test_config['subnet']):
            updateState('runTest','pass - subnet','Pass','subnet')
        else:
            updateState('runTest','fail - subnet','Fail','subnet')
            if stop_on_failure:
                return False
    if 'code_version' in test_config:
        if testCodeVersion(test_config['code_version']):
            updateState('runTest','pass - code_version','Pass','code_version')
        else:
            updateState('runTest','fail - code_version','Fail','code_version')
            if stop_on_failure:
                return False
    if serial_number != '' or serial_number != '0':
        if testSerialNumber(serial_number):
            updateState('runTest','pass - serial_number','Pass','serial_number')
        else:
            updateState('runTest','fail - serial_number','Fail','serial_number')
            if stop_on_failure:
                return False
    if board_version != '':
        if testBoardVersion(board_version):
            updateState('runTest','pass - board_version','Pass','board_version')
        else:
            updateState('runTest','fail - board_version','Fail','board_version')
            if stop_on_failure:
                return False
    if 'cccv' in test_config:
        if testCCCV(test_config['cccv']):
            updateState('runTest','pass - cccv','Pass','cccv')
        else:
            updateState('runTest','fail - cccv','Fail','cccv')
            if stop_on_failure:
                return False
    if 'maxw' in test_config:
        if testMAXW(test_config['maxw']):
            updateState('runTest','pass - maxw','Pass','maxw')
        else:
            updateState('runTest','fail - maxw','Fail','maxw')
            if stop_on_failure:
                return False
    if 'load' in test_config:
        if testLoad(test_config['load']):
            updateState('runTest','pass - load','Pass','load')
        else:
            updateState('runTest','fail - load','Fail','load')
            if stop_on_failure:
                return False
    if 'loads' in test_config:
        if testLoads(test_config['loads']):
            updateState('runTest','pass - loads','Pass','loads')
        else:
            updateState('runTest','fail - loads','Fail','loads')
            if stop_on_failure:
                return False
    if 'sensor1' in test_config: # Unsure why this has a parameter
        if testSensor1(test_config['sensor1']):
            updateState('runTest','pass - sensor1','Pass','sensor1')
        else:
            updateState('runTest','fail - sensor1','Fail','sensor1')
            if stop_on_failure:
                return False
    if 'pdline' in test_config:
        if testPDLine(test_config['pdline']): # Unsure why this has a parameter
            print('pass','pdline')
            updateState('runTest','pass - pdline','Pass','pdline')
        else:
            updateState('runTest','fail - pdline','Fail','pdline')
            if stop_on_failure:
                return False

    if 'battery_backup_loads' in test_config:
        battery_backup_test = True
        mac_address = ''

        if (testBatteryBackup(test_config["battery_backup_loads"])):
            print('pass','battbackup')
            updateState('runTest','pass - battbackup','Pass','battbackup')
        else:
            updateState('runTest','fail - battbackup','Fail','battbackup')
            if stop_on_failure:
                return False

    if 'maxw_commission' in test_config:
        commissioning = True
        testMAXW(test_config['maxw_commission']) # sets both channels to commission requirement @ end of test - Drew
    if 'cmd' in test_config:
        if testCMD(test_config['cmd']):
            updateState('runTest','pass - cmd','Pass','cmd')
        else:
            updateState('runTest','fail - cmd','Fail','cmd')
            if stop_on_failure:
                return False
    return True

def start():
    if not database.connect():
        updateState('start','failed - cannot connect to database','Failed','Cannot connect to database')
        return False
    if not loadTestJSON():
        updateState('start','failed - cannot load test.json','Failed','Cannot load test.json')
        return False
    if not controller.open(port,baud,timeout):
        updateState('start','failed - cannot open controller port','Failed','Cannot open controller port')
        return False
    controller.print_rx = debug_print # debug
    controller.startRXThread()
    if not getIP():
        updateState('start','failed - cannot get node ip','Failed','Cannot get node ip')
        return False
    if not load.open():
        updateState('start','failed - cannot open electronic load','Failed','Cannot open electronic load')
        return False
    return True

def stop():
    controller.close()
    load.close()

def checkScanSN(arg):
    global scan_sn
    if arg == '-s':
        scan_sn = True
        return True
    return False

def checkVerbose(arg):
    global debug_print
    if arg == '-v':
        debug_print = True
        print('verbose controller print rx')
        return True
    return False

def checkSkipDB(arg):
    if arg == 'skip_db':
        database.skip_db = True
        print('skip_db')
        return True
    return False

def checkCCCV(arg):
    global CC_json, CV_json
    if arg == 'CC':
        CC_json = True
        print('CC_json')
    elif arg == 'CV':
        CV_json = True
        print('CV_json')

def checkCustomDevice(arg):
    global battery_backup_test
    global custom_sn
    if arg[:2] == 'BB':
        battery_backup_test = True
        custom_sn = arg
        print("Recorded Serial Number will be: ", custom_sn)



def checkArg(arg):
    return checkSkipDB(arg) or checkVerbose(arg) or checkCCCV(arg) or checkCustomDevice(arg)
    
###################

def write_to_csv(csv_file_path = "experimentation.csv", sn_to_csv = None,mac_to_csv = None):
    # Check if the CSV file exists; if not, create it
    if not os.path.isfile(csv_file_path):
        with open(csv_file_path, 'w', newline='') as csvfile:
            fieldnames = ['Serial Number', 'MAC Address']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
    with open(csv_file_path, 'r') as csvfile:
        lines = csvfile.readlines()
        for line in lines:
            if sn_to_csv in line: 
                print("SERIAL NUMBER ALREADY IN FILE")
                sn_to_csv = ''
            if mac_to_csv in line:
                if not mac_to_csv == '' or None:
                    print("MAC ADDRESS ALREADY IN FILE")
                mac_to_csv = ''
    if sn_to_csv is not mac_to_csv:
        with open(csv_file_path, 'a', newline='') as csvfile:
                    fieldnames = ['Serial Number', 'MAC Address']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    # Check if the file is empty; if yes, write the header
                    file_empty = csvfile.tell() == 0
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    if file_empty:
                        writer.writeheader()
                        
                    writer.writerow({'Serial Number': sn_to_csv, 'MAC Address': mac_to_csv})

        print("Data has been written to", csv_file_path)
    else: print("NO DATA HAS BEEN WRITTEN.")

###################

def main(argv, arc):
    global test_id, serial_number, board_version
    #print(argv, arc)
    if arc > 1:
        if not checkArg(argv[1]):
            test_id = argv[1]
            print('test_id',test_id)
    if arc > 2:
        if not checkArg(argv[2]):
            serial_number = argv[2]
            print('serial_number',serial_number)
    if arc > 3:
        if not checkArg(argv[3]) and not checkScanSN(argv[3]):
            board_version = argv[3]
            print('board_version',board_version)
    for i in range(4,8):
        if arc > i:
            if not checkArg(argv[i]) and not checkScanSN(argv[i]):
                pass
    final_pass = False
    if start():
        updateState('main','test start','Started','Test started')
        if runTest():
            updateState('main','test end - pass','Completed','Pass')
            final_pass = True
        else:
            updateState('main','test end - fail','Completed','Fail')
    stop()
    if final_pass:
        print('final - pass')

        if "append_to_file" in test_config:
            if battery_backup_test:
                serial_number = custom_sn
            write_to_csv(test_config["append_to_file"],serial_number,mac_address)
    else:
        print('final - fail')
    print('done')

if __name__ == '__main__':
    main(sys.argv, len(sys.argv))

