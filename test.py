# test.py

#Probably newest version
import controller
import coap_client
import load
import database
import yaml
import time
import sys
import coap_client_scan
import subprocess

import os
import csv
import random

from devices import functions_misc as misc
from devices import functions_els as els
from devices import functions_supernode as snode
from devices import functions_mini as mnode

stop_on_failure: bool = True
update_golden: bool = False
require_golden_match: bool = False
debug_print: bool = False
dfd_match_required: bool = False
test_id: str = '1'
serial_number: str = ''
custom_sn: str = ''
mac_address: str = ''
board_version: str = ''

#port: str = '/dev/ttyUSB0'
port: str = 'COM3'
baud: int = 115200
timeout: int = 0 # use RX thread

scan_sn: bool = True # Set to false by default if we implement COM-based discovery again (cut feature unfortunately)
database.skip_db = True

maxw_save = None
cccv_save = None

CC_yaml: bool = False
CV_yaml: bool = False
CUV_yaml: bool = False

# CUSTOM DEVICE SETTINGS
# Mini Node Settings
mini_node_test: bool = False
# ELS Node Settings
els_node_test: bool = False
# USBC Node Settings
usbc_node_test: bool = False
usbc_current_channel = ''
# Supernode Settings
supernode_test: bool = False
# Battery Backup Settings
battery_backup_test: bool = False

# Allows testbench to look for a device with leading digits provided in an arguement and 
# sets the serial number of that device to the serial number arguement
set_sn: bool = False
sn_leading_digits_to_set_sn: str

device: str = ''
node_channels: int = 2 # How many channels for a node. 2 by default

general_settings_config = None
scan_range_start = 2
scan_range_end = 255
test_config = None

prompt_continue_key: str = 'DOWN'
prompt_end_test_key: str = 'Esc'

csv_filename: str = ''

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

def load_yaml(file_path):
    """Load a YAML file safely, updating logs if successful."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
            updateLog(data)
            return data
    except yaml.YAMLError:
        print(f"Error: Failed to decode YAML from {file_path}.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return None

def load_settings():
    global general_settings_config
    folder_path = "config"
    file_name = os.path.join(folder_path, "general_settings.yaml")
    general_settings_config = load_yaml(file_name)
    if general_settings_config is not None: return True
    else: 
        print("General Settings wasn't loaded. Please troubleshoot.")
        return False

def load_test_config():
    global device, test_config

    folder_path = "config"
    file_name = os.path.join(folder_path, "test.yaml")  # default

    if CV_yaml:
        file_name = os.path.join(folder_path, "test_CV.yaml")
        device = "CV-RS485"
    elif CC_yaml:
        file_name = os.path.join(folder_path, "test_CC.yaml")
        device = "CC-0-10"
    elif CUV_yaml:
        device = 'CUV'
        file_name = os.path.join(folder_path, 'test_CUV.yaml')
    elif mini_node_test:
        file_name = os.path.join(folder_path, 'test_mini_node.yaml')
    elif battery_backup_test:
        # device = 'Battery Backup' # Redundant, done in CheckCustomDevice(arg)
        file_name = os.path.join(folder_path, 'test_battery_backup.yaml')
    elif supernode_test:
        if device == 'Supernode':
            file_name = os.path.join(folder_path, 'test_supernode.yaml')
        elif device == 'Supernode CV':
            file_name = os.path.join(folder_path, 'test_supernode_CV.yaml')
        elif device == 'Supernode CC':
            file_name = os.path.join(folder_path, 'test_supernode_CC.yaml')
    elif usbc_node_test:
        # device = 'USBC Node' # Redundant, done in CheckCustomDevice(arg)
        file_name = os.path.join(folder_path, 'test_usbc.yaml')
    elif els_node_test: 
        device = 'ELS Node'
    else:
        device = 'CC-0-10'
    test_config = load_yaml(file_name)
    if test_config is not None: return True
    else:
        print("test config not loaded. Please troubleshoot.")
        return False

ip = ''
def getIP():
    global ip, scan_range_start, scan_range_end
    updateLog('getIP','start')
    if mini_node_test: coap_client_scan.is_mini_node = True
    if scan_sn:
        if 'subnet' in general_settings_config: 
            coap_client_scan.subnet = general_settings_config['subnet']
            if 'scan_start' in general_settings_config: scan_range_start = general_settings_config['scan_start']
            if 'scan_end' in general_settings_config: scan_range_end = general_settings_config['scan_end']
        else:
            host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE).stdout.decode('utf-8').split(' ')[0]
            print("USING HOST IP. HOST IP IS: ",host_ip)
            host_ip_split = host_ip.split('.')
            host_ip_split[3] = '255'
            coap_client_scan.subnet = '.'.join(host_ip_split)
        if set_sn:
            print('scan subnet',coap_client_scan.subnet,'for device with leading sn digit(s):',sn_leading_digits_to_set_sn)
            coap_client_scan.serial_number = sn_leading_digits_to_set_sn
            coap_client_scan.scan_for_leading_digits = True
        else: 
            print('scan subnet',coap_client_scan.subnet,'for sn',serial_number)
            coap_client_scan.serial_number = serial_number
            coap_client_scan.scan(scan_range_start,scan_range_end)
            #coap_client_scan.scan()
        for node in coap_client_scan.nodes:
            print(node['ip'],node['network']['serialnum'])
            if node['network']['serialnum'] == serial_number:
                ip = node['ip']
                print('scan found sn',serial_number,'at',ip)
                updateLog('getIP',ip)
                return True
            # Sets serial number of given device with leading digits to serial number input arguement.
            elif set_sn and node['network']['serialnum'][:len(sn_leading_digits_to_set_sn)] == sn_leading_digits_to_set_sn:
                ip = node['ip']
                print('scan found sn leading digits',sn_leading_digits_to_set_sn,'at',ip)
                updateLog('getIP',ip)
                return True

    else: # Doesn't work currently since COM is not enabled
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
            print("IP Split:",ip_split)
            print("Subnet Split:",subnet_split)
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
                print('\r waiting for reboot: ',str(elapsed),endl='') # Returns an error - Drew
            golden = coap_client.getGoldenVersion(ip)
            if require_golden_match == True:
                if  golden != code_version:
                    updateLog('testCodeVersion','fail golden',golden)
                    return False
        elif require_golden_match == True:
            return False
    if dfd != code_version:
        updateLog('testCodeVersion','fail dfd',dfd)
        if dfd_match_required:
            return False
    else: print("DFD Version Correctly Matches DFU.")
    return True

def testSerialNumber(sn):
    if mini_node_test: mnode.serial_number_test(serial_number)
    if set_sn or not scan_sn:
        coap_client.setSN(ip,str(sn))
    get_sn = coap_client.getSN(ip)
    if get_sn != str(sn):
        updateLog('testSerialNumber','fail get',get_sn)
        return False
    if set_sn: print("Serial number set to",get_sn)
    return True

def testBoardVersion(bv):
    # no set board version
    if mini_node_test: 
        if not mnode.get_board_version(ip): return False
    else: 
        get_bv = coap_client.getBoardVersion(ip)
        if get_bv != str(bv):
            updateLog('testBoardVersion','fail get',get_bv)
            return False
    return True

def testTrigger(number_of_times_to_restart,seconds_to_wait_for_restart):
    times_restarted = 0
    while(times_restarted < number_of_times_to_restart):
        coap_client.putValue(ip,'/network','cmd','trigger 1')
        count = 0
        while(count<seconds_to_wait_for_restart):
            try:
                print("Attempt",times_restarted+1,"IP Address rediscovered:",coap_client.getValue(ip,'/network','madr'))
                break
            except:
                print("Awaiting ip...")
            time.sleep(1.0)
            print(count)
            count += 1
        if coap_client.getValue(ip,'/network','madr') != ip: return False
        times_restarted += 1
    return True

def testCMD(cmds):
    for cmd in cmds:
        coap_client.putValue(ip,'/network','cmd',str(cmd))
        time.sleep(1)
    return True


def testCCCV(cccv):
    global cccv_save
    cccv_save = cccv

    if supernode_test: coap_client.setCCCV(ip,0,cccv)
    else: coap_client.setCCCV(ip,3,cccv)

    if supernode_test:
        time.sleep(8.0)
            
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
    maxw_save = maxw

    coap_client.setMaxWatt(ip,0,maxw)
    if supernode_test:
        time.sleep(3.0)

    maxw1 = coap_client.getValue(ip,'/actuators/actuator1','maxw')
    maxw2 = coap_client.getValue(ip,'/actuators/actuator2','maxw')
    
    if maxw1 != str(maxw):
        updateLog('testMAXW','fail actuator1',maxw2)
        return False
    if maxw2 != str(maxw):
        updateLog('testMAXW','fail actuator2',maxw2)
        return False

    return True

def setMux(channel: int, verbose: bool = True, delay:float = 0.25):
    # If you want to improve the odds of it finding the mux, give it more time to read it in controller.py

    controller.setMux(channel-1)

    if verbose: print("Setting Mux to output on channel", channel)
    if delay: time.sleep(delay)
    #print("Mux channel",relay,"is",controller.getMux())
    current_mux = controller.getMux
    count: int = -1
    while current_mux != channel-1:
        current_mux = controller.getMux()
        if count == 50 or -1:
            print("Attempting to retrive mux")
            count = 0
        #print("MUX WAS NOT SET PROPERLY FOR CHANNEL",channel,"- CURRENT MUX IS",current_mux)
        count+=1
        time.sleep(delay)

def testLoad(test_load):
    ran_once : bool = False

    power_threshold: float = 0.0        # Comes from test parameters, power measured checks against this value
    turn_load_off_after: bool = True    # Whether or not to turn load machine off after a measurement is finalized
    invert_power_thresh: bool = False   # Used when checking if power is BELOW or equal to the threshold power instead of GREATER than or equal to it

    # Checks to see how power threshold should be compared to power measured
    if 'below_power' in test_load:
        invert_power_thresh = True
        power_threshold = float(test_load['below_power'])
    elif 'power' in test_load: 
        invert_power_thresh = False
        power_threshold = float(test_load['power'])
    else: 
        print(f"WARNING: LOAD {test_load} HAS NO POWER THRESHOLD LISTED")
        pass

    # Internal function to measure power
    def power_check(power_to_check_against: float, turn_off_load_after: bool = True, reverse_power_thresh: bool = False):
        """Measures power once, then if it is below expected, it will wait and measure again.
        \nIf it's still inadequate, it will pause and await user input.
        \nIf still inadequate, it will fail and turn load machine off, if input var is true."""
        
        power = load.measurePower()

        # If power to check against is less than power measured, wait, then measure again. Then await the user to measure a third time
        if reverse_power_thresh: test_value = power_to_check_against - power
        # If power measured is less than power required, wait, then measure again. Then await the user to measure a third time
        else: test_value = power - power_to_check_against

        #if power < test_load['power']: 
        if test_value < 0:
            if reverse_power_thresh: print(f"Failed initial power test at {power} watts. Expected at most {power_to_check_against} watts. Awaiting new measurement...")
            else: print(f"Failed initial power test at {power} watts. Expected at least {power_to_check_against} watts. Awaiting new measurement...")

            time.sleep(3.0)
            power = load.measurePower()

            # Second Power Check
            # If power to check against is less than power measured, wait, then measure again. Then await the user to measure a third time
            if reverse_power_thresh: test_value = power_to_check_against - power
            # If power measured is less than power required, wait, then measure again. Then await the user to measure a third time
            else: test_value = power - power_to_check_against

            #if power < test_load['power']: 
            if test_value < 0:
                misc.send_test_prompt(misc.key,f"TEST STATION PAUSED. PRESS {misc.key} TO CONTINUE.","CONTINUING TEST...")
                power = load.measurePower()

            # Sets load output off
            load.setOutputOn(False)

            # if power is less than required, fail it. Else, pass it
            if reverse_power_thresh: 
                test_value = power_to_check_against - power
                #print("power_to_check_against - power_measured =",power)

            else: 
                test_value = power - power_to_check_against
                #print("power_measured - power_to_check_against =",power)
                
            #if power < test_load['power']: 
            if test_value < 0:
                misc.updateLog('testLoad',relay,'fail power',power)
                return False
            else: 
                misc.updateLog('testLoad',relay,'pass power',power)
                return True
        misc.updateLog('testLoad',relay,'pass power',power)
        if turn_off_load_after: load.setOutputOn(False)
        return True

    if 'cccv' in test_load:
        if test_load['cccv'] != cccv_save:
            if testCCCV(test_load['cccv']):
                updateLog('testCCCV','pass',test_load['cccv'])
    if 'maxw' in test_load:
        if test_load['maxw'] != maxw_save:
            if testMAXW(test_load['maxw']):
                updateLog('testMAXW','pass',test_load['maxw'])

    if mini_node_test:
        if not ran_once: print("Starting Mini Node Load test")
        if not mnode.load_test(test_load): return False
        else: return True

    if els_node_test:
        print("Starting ELS load test")
        if not els.load_test(ip, test_load, test_config): return False
        else: return True

    if supernode_test:
        print("Starting Supernode load test")
        if not snode.load_test(test_load): return False
        else: return True

    # dim: int = 100
    # if 'dim' in test_load: dim = test_load['dim']
                
    # coap_client.setDim(ip,3,10)
    # time.sleep(1)
    # coap_client.setDim(ip,3,dim)

    # MIGHT NEED TO LOOK BACK AT PUTTING THIS IN IF DIM PROBLEMS PERSIST

    time.sleep(0.5)

    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and ('power' in test_load or 'below_power' in test_load):

        # SET RELAYS
        if battery_backup_test: relays = ['output1'] # Accounts for when you are doing a battery backup test 

        elif usbc_node_test: relays = [usbc_current_channel] # usbc_current_channel is set in the test_loads function

        else:
            # Dim set happens here
            dim: int = 100
            if 'dim' in test_load: dim = test_load['dim']
            coap_client.setDim(ip,3,10)
            time.sleep(1)
            coap_client.setDim(ip,3,dim)

            dim1 = coap_client.getDim(ip,1)
            dim2 = coap_client.getDim(ip,2)

            if dim1 != dim:
                updateLog('testLoad',1,'failed to set dim on channel 1 to',dim,"Current dim:",dim1)
                return False
            if dim2 != dim:
                updateLog('testLoad',2,'failed to set dim on channel 2 to',dim,"Current dim:",dim2)
                return False

            relays = ['output1','output2']

        #print(relays)

        for relay in relays:

            controller.setRelays(relay)

            if 'CR' in test_load: load.setResistance(test_load['CR'])
            if 'CV' in test_load: load.setVoltage(test_load['CV'])
            if 'CC' in test_load: 
                # Unncomment this if the load machine is crappy. (Sig SDL 1000x series for instance)
                # if test_load['CC'] > 3.5:
                #     load.setCurrent(test_load['CC']/2)
                #     time.sleep(0.5)
                load.setCurrent(test_load['CC'])

            # SET OUTPUT ON AND MEASURE POWER
            # time.sleep(1.0)
            if 'time_before_load_on' in test_load: time.sleep(test_load['time_before_load_on'])
            elif 'time_before_load_on' in test_config: time.sleep(test_config['time_before_load_on'])
            # Sets load output on.
            if not usbc_node_test or not ran_once: load.setOutputOn(True)

            if 'hold_load_time' in test_load: time.sleep(test_load['hold_load_time'])
            elif 'hold_load_time' in test_config: time.sleep(test_config['hold_load_time'])
            time.sleep(1.0)

            # This is where power is checked
            if invert_power_thresh: power_check(power_threshold,turn_load_off_after, invert_power_thresh)
            else: power_check(power_threshold,turn_load_off_after)

            ran_once = True

        return True
    
    if supernode_test: load.setOutputOn(False)

    return True

def testLoads(test_loads):
    global usbc_current_channel

    test_pass = True

    if mini_node_test: 
        print("Testing Mini Node Loads")
        if not mnode.loads_test(test_loads): return False
        return True
    
    elif usbc_node_test: 
        load.setOutputOn(True)
        usbc_channels = ['output1','output2']
        for index,channel in enumerate(usbc_channels): # usbc_channels defined as a global variable. Should be 2 channels until we make USBC supernodes
            usbc_current_channel = usbc_channels[index]
            print(usbc_current_channel)
            controller.setRelays(channel)
            for index,test_load in enumerate(test_loads):
                if not testLoad(test_load): test_pass = False
    
    else:
        for index,test_load in enumerate(test_loads):
            if not testLoad(test_load): test_pass = False

    load.setOutputOn(False)

    if test_pass:
        updateLog('testLoads','pass')
        return True
    updateLog('testLoads','fail')

    return False

# clean up function before return
def returnTestSensor1(ret):
    if not mini_node_test: coap_client.putValue(ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
    if not supernode_test: coap_client.putValue(ip,'/actuators/actuator1','motdsbl','3') # disable motion
    else: coap_client.putValue(ip,'/actuators/actuator1','motdsbl','0') # disable motion (supernode)
    return ret

def testSensor1(do_test):
    
    if mini_node_test:
        if mnode.sensor_test(): return True
        else: return False

    coap_client.putValue(ip,'/sensors/sensor1','eventrisefall','on,off') # change sensor 1 events
    coap_client.putValue(ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
    coap_client.putValue(ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    # coap_client.putValue(ip,'/policy','updown','10,10,90,5') # this should be default, but change if not
    coap_client.putValue(ip,'/actuators/actuator1','motdsbl','33') # enable motion

    if usbc_node_test: misc.send_test_prompt(misc.key,f'Connect control port of {device} to test station and press {misc.key}','')

    
    controller.setAux(1,False,'') # set Aux1 low

    # print(coap_client.getDim(ip,1))
    # print(coap_client.getDim(ip,2))
    coap_client.setDim(ip,3,0) # clear dim
    # print(coap_client.getDim(ip,1))
    # print(coap_client.getDim(ip,2))

    time.sleep(5.0) # wait for event
    controller.setAux(1,True,'') # set Aux1 high, test rising edge of sensor1
    time.sleep(5.0) # wait for event
    
    dim1 = coap_client.getDim(ip,1) # dim1 should be 100%
    dim2 = coap_client.getDim(ip,2) # dim2 should be 100%
    if dim1 <= 0:
        updateLog('testSensor1','high',1,'fail set dim',dim1)
        return returnTestSensor1(False) # DREW note turn aux 1 off if fail
    elif dim2 <= 0:
        updateLog('testSensor1','high',2,'fail set dim',dim2)
        return returnTestSensor1(False)
    else: updateLog('testSensor1','high','pass set dim', dim2)
    controller.setAux(1,False,'') # set Aux1 low, test falling edge of sensor1
    time.sleep(1.0) # wait for  event
    dim1 = coap_client.getDim(ip,1) # dim1 should be 0%
    dim2 = coap_client.getDim(ip,2) # dim2 should be 0%
    # count = 0
    # while dim1 != 0 and dim2 != 0:
    #     time.sleep(1)
    #     dim1 = coap_client.getDim(ip,1)
    #     dim2 = coap_client.getDim(ip,2)
    #     count += 1
    #     if count == 10: break
    if dim1 != 0:
        updateLog('testSensor1','low',1,'fail set dim',dim1)
        return returnTestSensor1(False)
    elif dim2 != 0:
        updateLog('testSensor1','low',2,'fail set dim',dim2)
        return returnTestSensor1(False)
    else: updateLog('testSensor1','low','pass set dim', dim2)
    return returnTestSensor1(True)

def testPDLine(do_test):
    if mini_node_test:
        if not mnode.wallswitch_test(mnode.drivers): return False
        else: return True
    if not supernode_test and not mini_node_test:
        coap_client.putValue(ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
        coap_client.putValue(ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    elif mini_node_test:
        if not coap_client.secure_setting(ip,'/drivers/0/wallswitch','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver console and press {misc.key} when it has been set.','')
        if mnode.remote_driver_exists: 
            if not coap_client.secure_setting(ip,'/drivers/1/wallswitch','enable','true'): misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver console and press {misc.key} when it has been set.','')
    else: 
        misc.send_test_prompt(misc.key,f'Connect control port of {device} to test station and press {misc.key}','')
    
    controller.setPush4BTNOff() # press off button, but ignore event
    coap_client.setDim(ip,0,0) # clear dim, in case off button did not work

    time.sleep(1.0) # CHECK TO SEE IF THIS IS NECESSARY
    updateLog('Starting PDLine Testing')
    attempts = 0
    while attempts != 10:
        time.sleep(0.25)
        controller.setPush4BTNOn()
        dim1 = coap_client.getDim(ip,1) # dim1 should be 0%
        dim2 = coap_client.getDim(ip,2)
        attempts += 1
        if dim1 == 100 and dim2 == 100:
            #updateLog('Attempts:',attempts,dim1,dim2)
            break

    updateLog('Attempts taken for dim 100:', attempts)
    if dim1 != 100:
        updateLog('testPDLine','On',1,'fail set dim',dim1)
        return False
    if dim2 != 100:
        if mini_node_test and not mnode.remote_driver_exists: pass
        else:
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
            #updateLog('Attempts:',attempts,dim1,dim2)
            break
    updateLog('Attempts taken for dim 0:', attempts)
    if dim1 != 0:
        updateLog('testPDLine','Off',1,'fail set dim',dim1)
        return False
    if dim2 != 0:
        updateLog('testPDLine','Off',2,'fail set dim',dim2)
        return False
    return True

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
    
    misc.send_test_prompt(key,f"Press and hold switch test button. Then press {key} on keyboard when ready.", "Keep button held.")

    time.sleep(wait_time)
    if not testLoad(lower_load): 
        return False
    print("Release button")
    time.sleep(5.0)
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
    time.sleep(wait_time*2)


    #misc.send_test_prompt(key, f"Unplug Channel 1, then press {key}","Testing Power Loss Backup")
    #time.sleep(wait_time)

    if not testLoad(lower_load): 
        return False
    
    #misc.send_test_prompt(key, f"Plug in Channel 1, then press {key}","Testing Normal High Load")
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
        print("No Low Load in yaml file")
        return False

    if "High Load" in batt_test_load: high_load = batt_test_load["High Load"]
    else:
        print("No High Load in yaml file")
        return False

    if "await_key" in test_config: await_key = test_config["await_key"]
    else: await_key = misc.key

    if "await_time" in test_config: batt_wait_time = test_config["await_time"]
    else: batt_wait_time = 2

    if not testBatteryLoad(high_load,low_load,await_key,batt_wait_time):
        return False

    return True

# def commission(commission_settings_list):
#     for index,setting in enumerate(commission_settings_list):
#         if index == 0: continue
#         if 'resource' in setting: resource = setting['resource']
#         else: print("No resource set for this setting")
#         if 'key' in setting: key = setting['key']
#         else: print("No key set for this setting")
#         if 'value' in setting: value = setting['value']
#         else: print("No value set for this setting")

#         if not coap_client.secure_setting(ip,resource,key,value,True): return False
#     return True

def commission(commission_settings):

    settings_list = commission_settings.get("settings", [])
    success = True  # track overall success
    
    for setting in settings_list:
        resource = setting.get("resource")
        key = setting.get("key")
        value = setting.get("value")

        if not resource:
            print("No resource set for this setting")
            success = False
            continue
        if not key:
            print("No key set for this setting")
            success = False
            continue
        if value is None:
            print("No value set for this setting")
            success = False
            continue

        # Apply the setting
        if not coap_client.secure_setting(ip, resource, key, value, True):
            print(f"Failed to apply {key}={value} on {resource}")
            success = False

    return success


def runTest():
    global device
    global mac_address
    global battery_backup_test
    #global node_channels node_channnels unimplemented
    if 'trigger_1_test' in test_config and test_config['trigger_1_test']:
        if 'chance_to_test_trigger_1' in test_config:
            chance = test_config['chance_to_test_trigger_1']
            if random.random() < chance/100: 
                print("Starting Trigger 1 Test")
                if 'number_of_trigger_1_attempts' in test_config: trigger_attempts = test_config['number_of_trigger_1_attempts']
                if 'seconds_to_wait_for_restart' in test_config: wait_for_seconds = test_config['seconds_to_wait_for_restart']
                if testTrigger(trigger_attempts,wait_for_seconds):
                    updateState('runTest','pass - trigger1','Pass','trigger1')
                else: 
                    updateState('runTest','fail - trigger1','Fail','trigger1')
            else: pass
    if 'update_db' in test_config and test_config['update_db']: coap_client.putValue(ip,'/network','cmd','update_db')
    time.sleep(8.0)
    if not battery_backup_test:
        sn = coap_client.getSN(ip)
        if mini_node_test: mac_address = coap_client.getValue(ip,'/network','mac')
        else: mac_address = coap_client.getMAC(ip)
        mac_address = str(mac_address.upper())
        updateLog('SN: ',sn, 'MAC: ',mac_address)

    if mini_node_test: 
        mnode.init(ip,test_config,serial_number)
        print("Initializing Mini Node Test")

    elif els_node_test: 
        print("Initializing ELS test")
        coap_client.putValue(ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ip,'/actuators/actuator1','dimels',100)
        coap_client.putValue(ip,'/actuators/actuator2','dimels',100)

    elif usbc_node_test: print("Initializing USBC Node Test")
    elif battery_backup_test: 
        #device = 'Battery Backup'
        mac_address = 'N/A'
        print("Initializing battery backup test")

    elif supernode_test:
        print("Initializing supernode test")
        snode.init(ip,test_config)
        #device = 'Supernode'
        # count = 0
        # while count != 10:
        #     coap_client.putValue(ip,'/network','lldp_enable','false')
        #     lldp_setting = coap_client.getValue(ip,'/network','lldp_enable')
        #     if lldp_setting == 'false':
        #         print("LLDP has been set to false")
        #         break
        # if lldp_setting != 'false': print("LLDP failed to set to false. Failed after",count,"retries")
        coap_client.set_lldp(ip,False)

        igain10_variable = 'cv_igain10'
        if device == 'Supernode CC' or 'Supernode': 
            igain10_variable = 'cc_igain10'
            count = 0
            while count != 10:
                coap_client.putValue(ip,'/actuators/actuator1',igain10_variable,7)
                igain10_setting = coap_client.getValue(ip,'/actuators/actuator1',igain10_variable)
                if igain10_setting == 7:
                    print(igain10_variable, "has been set to", igain10_setting)
                    break
            if igain10_setting != 7: print(igain10_variable, "failed to set to", 7, "after", count, "retries")
        if device == 'Supernode CV' or 'Supernode':
            igain10_variable = 'cv_igain10'
            count = 0
            while count != 10:
                coap_client.putValue(ip,'/actuators/actuator1',igain10_variable,15)
                igain10_setting = coap_client.getValue(ip,'/actuators/actuator1',igain10_variable)
                if igain10_setting == 15:
                    print(igain10_variable, "has been set to", igain10_setting)
                    break
            if igain10_setting != 15: print(igain10_variable, "failed to set to", 15, "after", count, "retries")


        for i in range(1,8):
            coap_client.putValue(ip,'/sensors/input'+str(i),'sentype','disable') # change sensor 1 events supernode version
            coap_client.putValue(ip,'/sensors/input'+str(i),'eventlh','default') 
            coap_client.putValue(ip,'/sensors/input'+str(i),'eventhl','default') # change sensor 1 events supernode version

        # coap_client.setSentype(ip,0,'disable')
        # coap_client.setEventLH(ip,0,'default')
        # coap_client.setEventHL(ip,0,'default')

    else:
        if not mini_node_test:
            coap_client.putValue(ip,'/network','cmd','set_ws 0')
            coap_client.putValue(ip,'/network','cmd','set_max_amp 3 2500')
    
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
            updateState('runTest','pass - board_version','Pass',f'board_version:{board_version}')
        else:
            updateState('runTest','fail - board_version','Fail',f'board_version:{board_version}')
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
        #print("starting loads test")
        if testLoads(test_config['loads']):
            updateState('runTest','pass - loads','Pass','loads')
        else:
            updateState('runTest','fail - loads','Fail','loads')
            if stop_on_failure:
                return False
    if 'rgbw' in test_config:
        if not isinstance(test_config['rgbw'], list) or not all(isinstance(x, int) for x in test_config['rgbw']):
            print("RGBW Sets in test_config must be formatted as a list of ints. Proceeding with default values.")
            rgbw_sets = [4278190080,16711680,65280,255,4294967295]
        else: rgbw_sets = test_config['rgbw']
        if mini_node_test: mnode.rgbw_test(rgbw_sets)
    if 'sensor1' in test_config and test_config['sensor1']: # Unsure why this has a parameter
        if testSensor1(test_config['sensor1']):
            updateState('runTest','pass - sensor1','Pass','sensor1')
        else:
            updateState('runTest','fail - sensor1','Fail','sensor1')
            if stop_on_failure:
                return False
    if 'pdline' in test_config and test_config['pdline']:
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
    if mini_node_test and 'firmware_upgrade' in test_config and test_config['firmware_upgrade']: 
        print("Starting firmware upgrade...")
        mnode.firmware_upgrade_test()
    if 'commission' in test_config: # Working on commission in main branch - Drew
        commission_settings = test_config['commission']
        if 'toggle' in commission_settings and commission_settings['toggle'] == 1:
            print("Commissioning Node")
            if commission(commission_settings): 
                updateState('runtest','pass - commission','Pass','commission')
            else: updateState('runtest','fail - commission','Fail','commission')
        else: print("Commission settings missing or toggled off.")
    if supernode_test:
        if snode.dc_in_test(): 
            updateState('runtest','pass - dc in','Pass','dc in')
        else: 
            updateState('runtest','fail - dc in','Fail','dc in')
        count: int = 0
        while count != 10:
            coap_client.putValue(ip,'/network','lldp_enable','true')
            lldp_setting = coap_client.getValue(ip,'/network','lldp_enable')
            if lldp_setting == 'true':
                print("LLDP has been set to true")
                break
        if lldp_setting != 'true': print("LLDP failed to set to true. Failed after",count,"retries")
    
    if supernode_test:
        for i in range(1,9): coap_client.secure_setting(ip,f'/actuators/actuator{i}','fadetime',2000)
    if 'supernode_commission' in test_config: # Need to remove this later and replace with a more general commission in the supernode YAML
        if snode.commission(test_config['supernode_commission']):
            updateState('runTest','pass - commission supernode', 'Pass','commission supernode')
        else:
            updateState('runTest','fail - commission supernode', 'Fail','commission supernode')
            if stop_on_failure: 
                return False
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
    if not load_settings():
        updateState('start','failed - cannot load general_settings.yaml','Failed','Cannot connect to database')
        return False
    if not load_test_config():
        updateState('start','failed - cannot load test.yaml','Failed','Cannot load test.yaml')
        return False
    if not controller.open(port,baud,timeout):
        updateState('start','failed - cannot open controller port','Failed','Cannot open controller port')
        return False
    controller.print_rx = debug_print # debug
    controller.startRXThread() # Check to see if this is causing console bloat - Drew
    if not getIP():
        updateState('start','failed - cannot get node ip','Failed','Cannot get node ip')
        return False
    if not load.open() and 'load' in test_config:
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

def checkCCCV(arg: str):
    global CC_yaml, CV_yaml, CUV_yaml
    if arg.lower() == 'cc':
        CC_yaml = True
        print('CC_yaml')
    elif arg.lower() == 'cv':
        CV_yaml = True
        print('CV_yaml')
    elif arg.lower() == 'cuv' or arg.lower() == 'cccv':
        CUV_yaml = True
        print('CUV_yaml')
    else: return False

def checkSetSerialNumber(arg):
    global set_sn, sn_leading_digits_to_set_sn
    if arg[:6] == 'set_sn': 
        print("Set SN Mode Active")
        set_sn = True
        sn_leading_digits_to_set_sn = arg[6:]
        print(sn_leading_digits_to_set_sn)
    elif arg[:5] == 'setsn': 
        print("Set SN Mode Active")
        set_sn = True
        sn_leading_digits_to_set_sn = arg[5:]

def checkCustomDevice(arg):
    global device, els_node_test, supernode_test, usbc_node_test, battery_backup_test, mini_node_test, custom_sn
    if arg in ('mini_node', 'mini', 'mnode', 'core_node', 'core', 'cnode'):
        mini_node_test = True
        device = "Core Node"
    elif arg[:5] == 'super':
        supernode_test = True
        device = 'Supernode'
        if arg == 'supercv': device = 'Supernode CV'
        elif arg == 'supercc': device = 'Supernode CC'
    elif arg == 'els' or arg == 'ELS':
        els_node_test = True
        device = 'ELS Node'
    elif arg == 'usbc':
        usbc_node_test = True
        device = 'USBC Node'
    elif arg[:2] == 'BB':
        battery_backup_test = True
        custom_sn = arg
        device = 'Battery Backup'
        print("Recorded Serial Number will be: ", custom_sn)

def checkCSV(arg):
    global csv_filename
    if 'csv' in arg.lower():
        csv_filename = str(arg).lower().replace('.', '').replace('csv', '')
        if csv_filename == 'no': csv_filename = None
        else:
            csv_filename = f"{csv_filename}.csv"
            #print(f"NODE WILL BE RECORDED IN {csv_filename}.")

def checkArg(arg):
    return checkSkipDB(arg) or checkVerbose(arg) or checkCCCV(arg) or checkCustomDevice(arg) or checkSetSerialNumber(arg) or checkCSV(arg)
    
###################    

def write_to_csv(csv_file_name, sn_to_csv = None,mac_to_csv = None):
    
    # Define the folder path where the CSV files will be saved
    folder_path = "records"
    
    # Create the 'records' folder if it doesn't exist
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Set the full path for the CSV file inside the 'records' folder
    csv_file_name = os.path.join(folder_path, csv_file_name)

    # Note to delete or rework how sn_to_cv and mac_to_csv work.
    sn_exists = False
    mac_exists = False

    # Check if the CSV file exists; if not, create it
    if not os.path.isfile(csv_file_name):
        with open(csv_file_name, 'w', newline='') as csvfile:
            fieldnames = ['Device','Rev','Serial Number', 'MAC Address','Status','Date']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

    with open(csv_file_name, 'r') as csvfile:
        lines = csvfile.readlines()
        for line in lines:
            if sn_to_csv and sn_to_csv in line: 
                print(f"SERIAL NUMBER ALREADY IN {csv_file_name}.")
                sn_exists = True
            if mac_to_csv.lower() in line.lower() and mac_to_csv != "N/A":
                if not mac_to_csv == '' or None:
                    print(f"MAC ADDRESS ALREADY IN {csv_file_name}.")
                mac_exists = True

    if not sn_exists and not mac_exists:
        with open(csv_file_name, 'a', newline='') as csvfile:
                    fieldnames = ['Device','Rev','Serial Number', 'MAC Address','Status','Date']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    # Check if the file is empty; if yes, write the header
                    if os.path.getsize(csv_file_name) == 0 or not lines: 
                        print("Writing header.")
                        writer.writeheader()

                    current_time = str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                    writer.writerow({'Device': device,'Rev': board_version.capitalize(), 'Serial Number': sn_to_csv, 'MAC Address': mac_to_csv.upper(), 'Status': 'Pass', 'Date': current_time})

        print(sn_to_csv,"has been written to", csv_file_name)
    else: print("NO DATA HAS BEEN WRITTEN.")

###################

def main(argv, arc):
    global test_id, serial_number, mac_address, board_version, csv_filename
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
        print('\nfinal - pass')

        # print("CSV Filename:",csv_filename)
        if "append_to_file" in test_config and test_config["append_to_file"] != False:
            if battery_backup_test:
                serial_number = custom_sn
                print("Battery Backup Serial Number:",serial_number)
                mac_address = 'N/A'
            if csv_filename == '': 
                t = time.localtime()
                csv_filename = f"{t.tm_year % 100}_{t.tm_mon}_{t.tm_mday}.csv"
                # print("CSV Filename:",csv_filename)
            if csv_filename == None: print("argument 'nocsv' was set, not writing to any csv file.")
            else: write_to_csv(csv_filename, serial_number, mac_address)
    else:
        print('\nfinal - fail')
    print('done')

if __name__ == '__main__':
    main(sys.argv, len(sys.argv))

