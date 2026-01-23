# test.py

#Probably newest version
from pickletools import int4
import controller
import coap_client
import load
import dev.defunct.database as database
import yaml
import time
import sys
import coap_client_scan
import subprocess

import os
import csv
import random

from dataclasses import dataclass

from devices import functions_misc as misc
from devices import functions_els as els
from devices import functions_supernode as snode
from devices import functions_mini as mnode

import prompt
import rs485

sys.stdout.reconfigure(line_buffering=True)

stop_on_failure: bool = False        # Whether or not to stop the test on first failure
update_golden: bool = False         # Whether or not to update the golden firmware on code version mismatch (NO LONGER USED)
require_golden_match: bool = False  # Whether or not to require the golden firmware to match the code version (NO LONGER USED)
debug_print: bool = False           # Unsure if used
dfd_match_required: bool = False    # Whether or not to require the DFD firmware to match the code version
test_id: str = '1'          # I should remove this @ some point, it's useless
serial_number: str = ''     # Serial number of device under test
mac_address: str = ''       # MAC address of device under test
board_version: str = ''     # Board version of device under test
custom_sn: str = ''         # Custom serial number for certain devices (Unsure if still used)

#port: str = '/dev/ttyUSB0'
microcontroller_port: str = 'COM3'  # The COM port for the microcontroller connection, MAKE SURE THIS IS SET IN GENERAL SETTINGS YAML
baud: int = 115200                  # Baud rate for microcontroller connection
microcontroller_timeout: int = 0    # timeout for connecting to microcontroller COM port (in seconds); 0 = no timeout

scan_sn: bool = True        # Set to false by default if we implement COM-based discovery again (cut feature unfortunately)
database.skip_db = True     # Database functions are defunct (NO LONGER USED) 

maxw_save = None # CHECK IF THIS IS NECESSARY LATER
cccv_save = None # CHECK IF THIS IS NECESSARY LATER

CC_yaml: bool = False # Generalize all devices to use the same name convention for bools and standardize the logic between them
CV_yaml: bool = False # Instead of having a set of yaml bools that are used differently 
CCUV_yaml: bool = False # than the already differently named [device]_test bools

# DEVICE IDENTIFICATION (All 'test' bools are used to handle special quirks involved with an otherwise standardized test procedure)
device: str = ''
node_channels: int = 2              # How many channels for a node. 2 by default
mini_node_test: bool = False        
els_node_test: bool = False
usbc_node_test: bool = False
usbc_current_channel = ''           # NEED TO GENERALIZE USBC LOAD TEST FUNCTION TO WORK WITHIN STANDARD TEST LOAD FUNCTION USING YAML
supernode_test: bool = False
battery_backup_test: bool = False   # STILL NEED TO GIVE THIS ITS OWN .PY FILE FOR DEVICE-SPECIFIC FUNCTIONS

# Allows testbench to look for a device with leading digits provided in an argument and 
# sets the serial number of that device to the serial number argument
# NOT BEING USED CURRENTLY, CAN REMOVE
set_sn: bool = False
sn_leading_digits_to_set_sn: str

general_settings_config = None
scan_timeout = 0.1
scan_range_start = 2
scan_range_end = 255
test_config = None

prompt_continue_key: str = 'DOWN'
prompt_end_test_key: str = 'Esc'

test_status: str = 'Pass'  # Overall test status, Pass by default
test_notes: list = []
csv_arg_file_name: str = ''
batch_csv_file = "test_batch.csv"

def updateTestNotes(*notes: float | str | None):
    global test_notes
    # if test_notes == '': test_notes = str(note)
    # else: test_notes += '/' + str(note)
    for note in notes: test_notes.append(note)

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
        #database.updateTestLog(test_id,serial_number,board_version,desc)

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

def parse_general_settings():
    global general_settings_config
    folder_path = "config"
    file_name = os.path.join(folder_path, "general_settings.yaml")
    general_settings_config = load_yaml(file_name)
    if general_settings_config is None: 
        print("General Settings wasn't loaded. Please troubleshoot.")
        return False
    else: 
        pass

    if 'prompt_continue_key' in general_settings_config:
        global prompt_continue_key
        prompt_continue_key = general_settings_config['prompt_continue_key']
    if 'prompt_end_test_key' in general_settings_config:
        global prompt_end_test_key
        prompt_end_test_key = general_settings_config['prompt_end_test_key']
    if 'Load Machine COM' in general_settings_config:
        COM_port = general_settings_config['Load Machine COM']
        if isinstance(COM_port, str):
            # Keep only digits and join them into one string
            num_str = ''.join(ch for ch in COM_port if ch.isdigit())
            COM_port = int(num_str)
        else:
            COM_port = int(COM_port)

        print(COM_port)
        load.res_els.append(f'ASRL{COM_port}::INSTR')
        return True
    # if 'Microcontroller COM' in general_settings_config:
    #     COM_port = general_settings_config['Microcontroller COM']
    #     if isinstance(COM_port, str):
    #         if 'COM' in COM_port:
    #             num_str = ''.join(ch for ch in COM_port if ch.isdigit())
    #             COM_port = int(num_str)

    if 'BATCH' in general_settings_config:
        global batch_csv_file
        batch_csv_file = general_settings_config['BATCH']


def load_test_config():
    global device, test_config

    folder_path = "config"

    if CV_yaml:
        file_name = os.path.join(folder_path, "test_CV.yaml")
        device = "CV-RS485"
    elif CC_yaml:
        file_name = os.path.join(folder_path, "test_CC.yaml")
        device = "CC-0-10"
    elif CCUV_yaml:
        device = 'CCUV'
        file_name = os.path.join(folder_path, 'test_CCUV.yaml')
    elif mini_node_test:
        file_name = os.path.join(folder_path, 'test_mini_node.yaml')
    elif battery_backup_test:
        device = 'Battery-Backup' # Redundant, done in CheckCustomDevice(arg)
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
        file_name = os.path.join(folder_path, "test_CC.yaml")
    else:
        file_name = os.path.join(folder_path, "test.yaml")  # default
        device = "CCUV"
    test_config = load_yaml(file_name)
    if test_config is not None: return True
    else:
        print("test config not loaded. Please troubleshoot.")
        return False

ip = ''
def getIP():
    global ip, scan_timeout, scan_range_start, scan_range_end
    updateLog('getIP','start')
    if mini_node_test: coap_client_scan.is_mini_node = True
    if scan_sn:
        if 'subnet' in general_settings_config: 
            coap_client_scan.subnet = general_settings_config['subnet']
            if 'scan_timeout' in general_settings_config: scan_timeout = general_settings_config['scan_timeout']
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
            coap_client_scan.scan(scan_range_start,scan_range_end,scan_timeout)
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
        updateLog('testCodeVersion','fail dfu',dfu,'expected',code_version)
        return False
    if golden != code_version:
        updateLog('testCodeVersion','fail golden',golden)
        if update_golden:
            updateLog('testCodeVersion','update golden')
            coap_client.putValue(ip,'/dfu','updt',0)         # update golden / No longer used
            elapsed = 0
            while elapsed < 100:
                time.sleep(1.0)
                elapsed += 1
                print('\r waiting for reboot: ',str(elapsed),end='')
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
    if battery_backup_test:
        global board_version
        board_version = 'BB-R2'
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
        time.sleep(1.0)
    return True


def testCCCV(cccv):
    global cccv_save
    cccv_save = cccv

    if supernode_test: coap_client.setCCCV(ip,0,cccv)
    else: coap_client.setCCCV(ip,3,cccv)

    time.sleep(6.0)
            
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

@dataclass
class LoadTestResult:
    status: bool
    average_power: float | None
    median_power: float | None
    minimum_power: float | None
    maximum_power: float | None

def power_check(power_to_check_against: float, relay: int, turn_off_load_after: bool = True, reverse_power_thresh: bool = False):
    """Measures power once, then if it is below expected, it will wait and measure again.
    \nIf it's still inadequate, it will pause and await user input.
    \nIf still inadequate, it will fail and turn load machine off, if input var is true."""
    try:
        power = load.measurePower()
    except load.visa.errors.VisaIOError as e:
        print(f"Load-01 Visa IO Timeout Error: {e}")
        # misc.updateLog('testLoad',relay,'VISA IO Fail', e)
        # return False
        return LoadTestResult(False, None, None, None, None)
    except Exception as e:
        print(f"Unexpected error during power check: {e}")
        # return False
        return LoadTestResult(False, None, None, None, None)

    # If power to check against is less than power measured, wait, then measure again. Then await the user to measure a third time
    if reverse_power_thresh: test_value = power_to_check_against - power
    else: test_value = power - power_to_check_against

    if test_value < 0:
        if reverse_power_thresh: print(f"Failed initial power test at {power} watts. Expected at most {power_to_check_against} watts. Awaiting new measurement...")
        else: print(f"Failed initial power test at {power} watts. Expected at least {power_to_check_against} watts. Awaiting new measurement...")

        time.sleep(3.0)
        power = load.measurePower()

        # Second Power Check
        # If power to check against is less than power measured, wait, then measure again. Then await the user to measure a third time
        if reverse_power_thresh: test_value = power_to_check_against - power
        else: test_value = power - power_to_check_against

        if test_value < 0:
            # misc.send_test_prompt(misc.key,f"TEST STATION PAUSED. PRESS {misc.key} TO CONTINUE.","CONTINUING TEST...")
            if reverse_power_thresh: 
                if prompt.prompt("Power Measure Fail",f"Power Measure Fail. Measured {power} watts. Expected at most {power_to_check_against} watts. Continue the test?"):
                    pass
                else: 
                    misc.updateLog('testLoad',relay,'fail excessive power',power)
                    # return False
                    return LoadTestResult(False, power, None, None, None)
            else: 
                if prompt.prompt("Power Measure Fail",f"Power Measure Fail. Measured {power} watts. Expected at least {power_to_check_against} watts. Continue the test?"):
                    pass
                else:
                    misc.updateLog('testLoad',relay,'fail inadequate power',power)
                    # return False
                    return LoadTestResult(False, power, None, None, None)
            power = load.measurePower()

        # Sets load output off
        load.setOutputOn(False)

        # if power is less than required, fail it. Else, pass it
        if reverse_power_thresh: test_value = power_to_check_against - power
        else: test_value = power - power_to_check_against
                
        if test_value < 0:
            misc.updateLog('testLoad',relay,'fail power',power)
            # return False
            return LoadTestResult(False, power, None, None, None)
        # else: 
        #     misc.updateLog('testLoad',relay,'pass power',power)
            # return True
    misc.updateLog('testLoad',relay,'pass power',power)
    if turn_off_load_after: load.setOutputOn(False)
    # return True
    return LoadTestResult(True, power, None, None, None)

def moving_power_check(
    min_power_thresh: float = None,
    max_power_thresh: float = None,
    hold_time_seconds: float = 5.0,
    measure_every_seconds: float = 0.25,
    relay: int = 1,
    turn_off_load_after: bool = True):
    """Measures power every set interval of time (measure_every_seconds) over a set amount of time (hold_time_seconds). 
    \nThen, check the average power measured. If it's below expected, wait and measure again with the same method.
    \nIf it's still inadequate, it pauses and awaits user input.
    \nIf still inadequate, consider it a fail and turn load machine off, if input var is true.
    \nIt will return a dictionary with the minimum measurement"""

    # Once every input interval, measure power and add it to a list
    # Calculate the average, and return the maximum and minimum values on that list
    time_elapsed: float = 0.0
    #num_measurements: int = 1
    power_measurements: list = []
    time.sleep(2.0)
    while time_elapsed < hold_time_seconds:
        try: 
            power = load.measurePower()
            # print(f"Measurement {num_measurements}: {power}.")
        except load.visa.errors.VisaIOError as e:
            print(f"Load-01 Visa IO Timeout Error: {e}")
            # misc.updateLog('testLoad',relay,'VISA IO Fail', e)
            # return False
            return LoadTestResult(False, None, None, None, None)
        except Exception as e:
            print(f"Unexpected error during power check: {e}")
            # return False
            return LoadTestResult(False, None, None, None, None)

        power_measurements.append(power)
        print(f"\r Measurements: {power_measurements}")
        # num_measurements += 1
        time.sleep(measure_every_seconds)
        time_elapsed += measure_every_seconds

    middle_value = lambda nums: sorted(nums)[len(nums)//2 - (1 if len(nums)%2==0 else 0)]
    # median_power = sorted(power_measurements)[len(power_measurements)//2 - (1 if len(power_measurements)%2==0 else 0)]

    power = sum(power_measurements)/len(power_measurements)     # Get the average power from the list
    median_power = middle_value(power_measurements)    # Get the median power from the list
    minimum_power = min(power_measurements)                     # Get the minimum power from the list
    maximum_power = max(power_measurements)                     # Get the maximum power from the list
    print("Average Power: ",power)
    print("Median Power: ",median_power)
    print("Minimum Power: ",minimum_power)
    print("Maximum Power: ",maximum_power)

    fail_type = None
    if min_power_thresh is not None:
        test_average_value = power - min_power_thresh
        test_median_value = median_power - min_power_thresh
        if test_average_value < 0: 
            fail_type = "average"
            fail_power = f"Average: {power}"
            if test_median_value < 0: 
                fail_type += " and median"
                fail_power += f", and Median: {median_power}"
        elif test_median_value < 0: 
            fail_type = "median"
            fail_power = f"Median: {median_power}"
        if test_average_value < 0 or test_median_value < 0: 
            print(
                f"Failed initial {fail_type} power test at {fail_power} watts. "
                f"Expected at least {min_power_thresh} watts. "
                )
            p = prompt.abort_retry_ignore_prompt("Power Measure Fail",f"Power Measure Fail. Measured {fail_power} watts. Expected at least {min_power_thresh} watts.")

    if max_power_thresh is not None:
        test_average_value = max_power_thresh - power
        test_median_value = max_power_thresh - median_power
        if test_average_value < 0: 
            fail_type = "average"
            fail_power = f"Average: {power}"
            if test_median_value < 0: 
                fail_type += " and median"
                fail_power += f", and Median: {median_power}"
        elif test_median_value < 0: 
            fail_type = "median"
            fail_power = f"Median: {median_power}"
        if test_average_value < 0 or test_median_value < 0: 
            print(
                f"Failed initial {fail_type} power test at {fail_power} watts. "
                f"Expected at most {max_power_thresh} watts. "
                )
            p = prompt.abort_retry_ignore_prompt("Power Measure Fail",f"Power Measure Fail. Measured {fail_power} watts. Expected at most {max_power_thresh} watts.")

    #print(test_average_value,test_median_value)

    if fail_type: 
        if p == "abort": 
            print("\nAbort was selected. Process ended.")
            #sys.exit()
            # return False
            return LoadTestResult(False, power, median_power, minimum_power, maximum_power)
        elif p == "retry":
            print("Retrying...")
            time.sleep(3.0)
            return moving_power_check(min_power_thresh, max_power_thresh, hold_time_seconds, measure_every_seconds, relay, turn_off_load_after)
        elif p == "ignore":
            global test_status
            load.setOutputOn(False)
            print("Ignore was selected. Continuing test...")
            # return False
            test_status = 'Fail'
            misc.updateLog('testLoad',relay,'fail power',power)
            return LoadTestResult(True, power, median_power, minimum_power, maximum_power)

    misc.updateLog('testLoad',relay,'pass power',power)
    if turn_off_load_after: load.setOutputOn(False)
    # return True
    return LoadTestResult(True, power, median_power, minimum_power, maximum_power)

def testLoad(test_load):
    ran_once : bool = False

    # power_threshold: float = 0.0        # Comes from test parameters, power measured checks against this value
    turn_load_off_after: bool = True    # Whether or not to turn load machine off after a measurement is finalized
    invert_power_thresh: bool = False   # Used when checking if power is BELOW or equal to the threshold power instead of GREATER than or equal to it

    # Checks to see how power threshold should be compared to power measured
    min_power = None
    max_power = None
    if not ('power' in test_load or 'below_power' in test_load): 
        print(f"WARNING: LOAD {test_load} HAS NO POWER THRESHOLD LISTED")
        pass
    else:
        min_power,max_power = None,None
        if 'below_power' in test_load:
            invert_power_thresh = True
            max_power = float(test_load['below_power'])
        if 'power' in test_load: 
            invert_power_thresh = False
            min_power = float(test_load['power'])

    if 'cccv' in test_load:
        if test_load['cccv'] != cccv_save:
            if testCCCV(test_load['cccv']):
                updateLog('testCCCV','pass',test_load['cccv'])
    if 'cuv' in test_load:
        if test_load['cuv'] != cccv_save:
            if coap_client.secure_setting(ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                updateLog('testCUV','pass',test_load['cuv'])
    if 'maxw' in test_load:
        if test_load['maxw'] != maxw_save:
            if testMAXW(test_load['maxw']):
                updateLog('testMAXW','pass',test_load['maxw'])
    if 'turn_off_load_after' in test_load:
        print("turn_off_load_after found in test load:",test_load['turn_off_load_after'])
        if test_load['turn_off_load_after'] == False or test_load['turn_off_load_after'] == 0:
            turn_load_off_after = False
    else: turn_load_off_after = True

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
        relays = ['output1','output2']
        if battery_backup_test: relays = ['output1'] # Accounts for when you are doing a battery backup test 
        
        if not usbc_node_test: 
            # Dim set happens here
            dim: int = 100
            if 'dim' in test_load: dim = test_load['dim']
            coap_client.setDim(ip,3,10)
            time.sleep(1.25)
            coap_client.setDim(ip,3,dim)

            dim1 = coap_client.getDim(ip,1)
            dim2 = coap_client.getDim(ip,2)

            if dim1 != dim:
                updateLog('testLoad',1,'failed to set dim on channel 1 to',dim,"Current dim:",dim1)
                return False
            if dim2 != dim:
                updateLog('testLoad',2,'failed to set dim on channel 2 to',dim,"Current dim:",dim2)
                return False

        # If USBC test   
        else: relays = [usbc_current_channel] # usbc_current_channel is set in the test_loads function
            

        print(relays)

        for relay in relays:

            controller.setRelays(relay)

            if 'CR' in test_load: load.setResistance(test_load['CR'])
            if 'CV' in test_load: load.setVoltage(test_load['CV'])
            if 'CC' in test_load: load.setCurrent(test_load['CC'])
                # Use this for CC instead if the load machine is crappy. (Sig SDL 1000x series for instance)
                # if test_load['CC'] > 3.5:
                #     load.setCurrent(test_load['CC']/2) # Sets load machine to half the desired value to let it catch up. 
                #     time.sleep(0.5)
                

            # SET OUTPUT ON AND MEASURE POWER
            time.sleep(1.0)
            time_before_load_on = (test_load.get('time_before_load_on') or test_config.get('time_before_load_on'))
            if time_before_load_on is not None:
                print("Time before load on was set in test config, delaying",time_before_load_on,"seconds.")
                time.sleep(time_before_load_on)

            # Sets load output on.
            if not usbc_node_test or not ran_once: load.setOutputOn(True)  

            if 'MOVING' in test_load and (test_load['MOVING'] != 0 or test_load['MOVING'] != False): 
                if 'hold_load_time' in test_load: hold_load_time = test_load['hold_load_time']
                else: hold_load_time = 10.0
                if 'measure_every_seconds' in test_load: measure_every_seconds = test_load['measure_every_seconds']
                else: measure_every_seconds = 1.0
                # if 'retry' in test_load and (test_load['retry'] != 0 or test_load['retry'] != False): retry_bool = True
                # else: retry_bool = False

                # if invert_power_thresh: moving_power_check(power_threshold,hold_load_time,measure_every_seconds,relay,turn_load_off_after, invert_power_thresh)
                # else: moving_power_check(power_threshold,hold_load_time,measure_every_seconds,relay,turn_load_off_after,False,retry_bool)
                result = moving_power_check(
                    min_power_thresh = min_power,
                    max_power_thresh = max_power,
                    hold_time_seconds = hold_load_time,
                    measure_every_seconds = measure_every_seconds,
                    relay = relay,
                    turn_off_load_after = turn_load_off_after
                )
                if not result.status:
                    updateTestNotes(round(result.average_power,5))
                    return False
            else:
                if 'hold_load_time' in test_load: time.sleep(test_load['hold_load_time'])
                elif 'loads' in test_config and 'hold_load_time' in test_config['loads']: 
                    loads_setting = test_config['loads']
                    time.sleep(loads_setting['hold_load_time'])
                elif 'hold_load_time' in test_config: time.sleep(test_config['hold_load_time'])
                time.sleep(1.0)

                # This is where power is checked
                if invert_power_thresh: 
                    result = power_check(max_power,relay,turn_load_off_after, invert_power_thresh)
                    if not result.status:
                        updateTestNotes(round(result.average_power,5))
                        return False
                else:
                    result = power_check(min_power,relay,turn_load_off_after)
                    if not result.status: 
                        updateTestNotes(round(result.average_power,5))
                        return False
                    
            updateTestNotes(round(result.average_power,5))    
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
    
    if usbc_node_test:
        if USBC_test_loads(test_loads): return True
        else: return False
    
    # elif usbc_node_test: 
    #     load.setOutputOn(True)
    #     usbc_channels = ['output1','output2']
    #     for index,channel in enumerate(usbc_channels): # usbc_channels defined as a global variable. Should be 2 channels until we make USBC supernodes
    #         usbc_current_channel = usbc_channels[index]
    #         print(usbc_current_channel)
    #         controller.setRelays(channel)
    #         for index,test_load in enumerate(test_loads):
    #             if not testLoad(test_load): test_pass = False
    
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
    if not mini_node_test: coap_client.secure_setting(ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
    if not supernode_test: coap_client.secure_setting(ip,'/actuators/actuator1','motdsbl','3') # disable motion
    else: coap_client.secure_setting(ip,'/actuators/actuator1','motdsbl','0') # disable motion (supernode)
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

    time.sleep(2.0)

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
    time.sleep(1)
    coap_client.setDim(ip,3,100)

    time.sleep(wait_time)

    if not testLoad(upper_load): 
        return False

    if not testCCCV(10): 
        return False

    coap_client.setDim(ip,3,90)
    time.sleep(1)
    coap_client.setDim(ip,3,100)
    
    # misc.send_test_prompt(key,f"Press and hold switch test button. Then press {key} on keyboard when ready.", "Keep button held.")
    if prompt.prompt("Switch Test Button", "Press and hold switch test button. Select 'Okay' to continue or 'Cancel' to end test."): 
        print("Keep button held")
    else: 
        return False

    time.sleep(wait_time)
    if not testLoad(lower_load): 
        return False
    print("Release button")
    time.sleep(5.0)
    coap_client.setDim(ip,3,100)
    if not testLoad(upper_load): 
        return False
    

# TESTING FEATURE
    coap_client.setDim(ip,3,0)
    if not testCCCV(255): # Replaced cv 0
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
    # coap_client.setDim(ip,3,100)
    if not testLoad(upper_load): 
        return False

    print("Remember to unplug pink battery backup connectors when finished testing.")
    return True

def USBC_test_loads(test_loads): # TODO REFACTOR THIS TO USE testLoad FUNCTION OR PUT INTO ITS OWN THING

    def USBC_test_load(test_load):
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

        if 'cccv' in test_load:
            if test_load['cccv'] != cccv_save:
                if testCCCV(test_load['cccv']):
                    updateLog('testCCCV','pass',test_load['cccv'])
        if 'cuv' in test_load:
            if test_load['cuv'] != cccv_save:
                if coap_client.secure_setting(ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                    updateLog('testCUV','pass',test_load['cuv'])
        if 'maxw' in test_load:
            if test_load['maxw'] != maxw_save:
                if testMAXW(test_load['maxw']):
                    updateLog('testMAXW','pass',test_load['maxw'])
        if 'turn_off_load_after' in test_load:
            if test_load['turn_off_load_after'] == False or test_load['turn_off_load_after'] == 0:
                turn_load_off_after = False
        else: turn_load_off_after = True

        dim: int = 100
        if 'dim' in test_load: dim = test_load['dim']

        # print("Load Dim is",dim)
        #coap_client.setDim(ip,3,100)
        time.sleep(1.0)
        coap_client.setDim(ip,3,dim)

        # MIGHT NEED TO LOOK BACK AT PUTTING THIS IN IF DIM PROBLEMS PERSIST

        time.sleep(0.5)

        # SET RELAYS
        relays = [usbc_current_channel] # usbc_current_channel is set in the test_loads function
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
            elif 'loads' in test_config and 'hold_load_time' in test_config['loads']: 
                loads_setting = test_config['loads']
                time.sleep(loads_setting['hold_load_time'])
            elif 'hold_load_time' in test_config: time.sleep(test_config['hold_load_time'])
            time.sleep(1.0)

            # This is where power is checked
            if invert_power_thresh: power_check(power_threshold,relay,turn_load_off_after, invert_power_thresh)
                #if not power_check(power_threshold,relay,turn_load_off_after, invert_power_thresh): return False
            else: power_check(power_threshold,relay,turn_load_off_after)
                #if not power_check(power_threshold,relay,turn_load_off_after): return False
                    
            ran_once = True
            return True
        return True

    load.setOutputOn(True)
    usbc_channels = ['output1','output2']
    for index,channel in enumerate(usbc_channels): # usbc_channels defined as a global variable. Should be 2 channels until we make USBC supernodes
        usbc_current_channel = usbc_channels[index]
        print(usbc_current_channel)
        controller.setRelays(channel)
        for index,test_load in enumerate(test_loads):
            if not USBC_test_load(test_load): 
                updateLog('testLoads','fail')
                return False
    updateLog('testLoads','pass')
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

def commission(commission_settings):
    settings = commission_settings.get("settings", {})
    success = True

    checkVerbose = commission_settings.get("verbose", True)

    for resource, kv_pairs in settings.items():
        if not resource:
            print("No resource set for this setting")
            success = False
            continue

        if 'ALL' in resource: 
            # Check resource type (actuator, sensor, etc.) and apply settings to all channels accordingly
            if 'actuators' in resource: resource_type = 'actuator'
            elif 'sensors' in resource: resource_type = 'input'
            else: resource_type = 'unknown'
            print(f"Applying settings to all {node_channels} {resource_type} channels:")
            for k, v in kv_pairs.items():
                print(f"  {k}: {v}")
            for channel in range(1,node_channels+1): # FIND THIS VARIABLE IN THE INITIALIZATION SECTION WHERE CHANNELS ARE DEFINED BY NODE TYPE 
                # Replace the 'ALL' with the appropriate resource and channel number
                resource_channel = resource.replace("ALL",f"{resource_type}{str(channel)}")

                for key, value in kv_pairs.items():
                    if key is None:
                        print(f"No key set for resource {resource_channel}")
                        success = False
                        continue
                    if value is None:
                        print(f"No value set for key {key} on {resource_channel}")
                        success = False
                        continue

                    # Apply the setting
                    if not coap_client.secure_setting(ip, resource_channel, key, value, checkVerbose, timeout = 5.0):
                        print(f"Failed to apply {key}={value} on {resource_channel}")
                        success = False
                    if key == 'cccv':
                        print(f"Waiting a few seconds after setting CCCV on {resource_channel}.") # Switch this to a timeout preferably.
                        time.sleep(5.0)  # Allow time for CCCV to take effect
                # if device.lower() == 'supernode' or device.lower() == 'ccuv':
                #     print(f"Waiting 3 seconds between actuator settings for {device}.")
                #     time.sleep(3.0)  # Some devices need a bit more time between settings
        else:
            for key, value in kv_pairs.items():
                if key is None:
                    print(f"No key set for resource {resource}")
                    success = False
                    continue
                if value is None:
                    print(f"No value set for key {key} on {resource}")
                    success = False
                    continue

                # Apply the setting
                if not coap_client.secure_setting(ip, resource, key, value, checkVerbose, timeout = 8.0):
                    print(f"Failed to apply {key}={value} on {resource}")
                    success = False

    time.sleep(5.0)  # Allow time to write to EEPROM
    print("Commissioning complete. Writing to EEPROM...")
    return success

def testRS485():
    rs485.main()
    #misc.send_test_prompt(misc.key,f"Verify RS485 communication was successful. Press {misc.key} if it passed and 'Esc' if it failed.", "")
    if prompt.prompt("RS485 Testing", "Check the console to see if RS485 communication was successful. Did it pass?"):
        return True
    else: return False

def runTest():
    global device
    global mac_address
    global battery_backup_test
    global node_channels

    global test_status

    if 'code_version' in test_config:
        if testCodeVersion(test_config['code_version']):
            updateState('runTest','pass - code_version','Pass','code_version')
        else:
            updateState('runTest','fail - code_version','Fail','code_version')
            test_status = 'Fail'
            if stop_on_failure:
                return False

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
                    test_status = 'Fail'
            else: pass

    if 'update_db' in test_config:
        if test_config['update_db'] != False or test_config['update_db'] != 0: 
            coap_client.putValue(ip,'/network','cmd','update_db')
            time.sleep(8.0)
    
    if not battery_backup_test:
        sn = coap_client.getSN(ip)
        if mini_node_test: mac_address = coap_client.getValue(ip,'/network','mac')
        else: mac_address = coap_client.getMAC(ip)
        mac_address = str(mac_address.upper())
        updateLog('SN: ',sn, 'MAC: ',mac_address)

    if mini_node_test: 
        node_channels = 1
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
        #device = 'Battery-Backup'
        mac_address = 'N/A'
        print("Initializing battery backup test")

    elif supernode_test:
        node_channels = 8
        print("Initializing supernode test")
        snode.init(ip,test_config)

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

    else:
        if not mini_node_test:
            coap_client.putValue(ip,'/network','cmd','set_ws 0')
            coap_client.putValue(ip,'/network','cmd','set_max_amp 3 2500')
    
    if 'subnet' in test_config:
        if testSubnet(test_config['subnet']):
            updateState('runTest','pass - subnet','Pass','subnet')
        else:
            updateState('runTest','fail - subnet','Fail','subnet')
            test_status = 'Fail'
            if stop_on_failure:
                return False
    if serial_number != '' or serial_number != '0':
        if testSerialNumber(serial_number):
            updateState('runTest','pass - serial_number','Pass','serial_number')
        else:
            updateState('runTest','fail - serial_number','Fail','serial_number')
            test_status = 'Fail'
            if stop_on_failure:
                return False
    if board_version != '' and not supernode_test: # FIXME: Weird exception for supernode board version test
        if testBoardVersion(board_version):
            updateState('runTest','pass - board_version','Pass',f'board_version:{board_version}')
        else:
            updateState('runTest','fail - board_version','Fail',f'board_version:{board_version}')
            test_status = 'Fail'
            if stop_on_failure:
                return False

    if 'cccv' in test_config:
        if testCCCV(test_config['cccv']):
            updateState('runTest','pass - cccv','Pass','cccv')
        else:
            updateState('runTest','fail - cccv','Fail','cccv')
            test_status = 'Fail'
            if stop_on_failure:
                return False
    if 'maxw' in test_config:
        if testMAXW(test_config['maxw']):
            updateState('runTest','pass - maxw','Pass','maxw')
        else:
            updateState('runTest','fail - maxw','Fail','maxw')
            test_status = 'Fail'
            if stop_on_failure:
                return False
    if 'load' in test_config: # Fix later for toggle 0
        parse_general_settings = test_config['load']
        if misc.check_toggle(parse_general_settings):
            print("Starting Load Test")
            if testLoad(parse_general_settings):
                updateState('runTest','pass - load','Pass','load')
            else:
                updateState('runTest','fail - load','Fail','load')
                test_status = 'Fail'
                if stop_on_failure:
                    return False
        else:
            print("LOAD TEST TOGGLE IS SET TO OFF (0). SKIPPING LOAD TEST.")
            updateState('runTest','skip - load','Skip','load')

    if 'loads' in test_config:
        loads_settings = test_config['loads']
        if misc.check_toggle(loads_settings):
            print("Starting Loads Test")
            if testLoads(loads_settings['test_steps']):
                updateState('runTest','pass - loads','Pass','loads')
            else:
                updateState('runTest','fail - loads','Fail','loads')
                test_status = 'Fail'
                if stop_on_failure:
                    return False
        else:
            print("LOADS TEST TOGGLE IS SET TO OFF (0). SKIPPING LOADS TEST.")
            updateState('runTest','skip - loads','Skip','loads')

    if 'rgbw' in test_config:
        if not isinstance(test_config['rgbw'], list) or not all(isinstance(x, int) for x in test_config['rgbw']):
            print("RGBW Sets in test_config must be formatted as a list of ints. Proceeding with default values.")
            rgbw_sets = [4278190080,16711680,65280,255,4294967295]
        else: rgbw_sets = test_config['rgbw']
        if mini_node_test: mnode.rgbw_test(rgbw_sets)
    if 'sensor1' in test_config:
        if test_config['sensor1'] == 1 or test_config['sensor1'] == True: 
            if testSensor1(test_config['sensor1']):
                updateState('runTest','pass - sensor1','Pass','sensor1')
            else:
                updateState('runTest','fail - sensor1','Fail','sensor1')
                test_status = 'Fail'
                if stop_on_failure:
                    return False
        elif test_config['sensor1'] == 0 or test_config['sensor1'] == False:
            print(f"SENSOR1 TEST TOGGLE IS SET TO OFF {test_config['sensor1']}. SKIPPING SENSOR1 TEST.")
        else: print(f"SENSOR1 TEST TOGGLE IS SET TO INCOHERENT VALUE: {test_config['sensor1']}. SHOULD BE true, false, 1, OR 0. SKIPPING SENSOR1 TEST.")
    if 'pdline' in test_config:
        if test_config['pdline'] == 1 or test_config['pdline'] == True:
            if testPDLine(test_config['pdline']):
                print('pass','pdline')
                updateState('runTest','pass - pdline','Pass','pdline')
            else:
                updateState('runTest','fail - pdline','Fail','pdline')
                test_status = 'Fail'
                if stop_on_failure:
                    return False
        else: print(f"PDLINE TEST TOGGLE IS SET TO OFF {test_config['pdline']}. SKIPPING PDLINE TEST.")
    if 'battery_backup_loads' in test_config:
        battery_backup_test = True
        mac_address = ''

        if (testBatteryBackup(test_config["battery_backup_loads"])):
            print('pass','battbackup')
            updateState('runTest','pass - battbackup','Pass','battbackup')
        else:
            updateState('runTest','fail - battbackup','Fail','battbackup')
            test_status = 'Fail'
            if stop_on_failure:
                return False
    if mini_node_test and 'firmware_upgrade' in test_config and test_config['firmware_upgrade']: 
        print("Starting firmware upgrade...")
        mnode.firmware_upgrade_test()
    
    if supernode_test and 'dc_in' in test_config:
        if test_config['dc_in'] == 1 or test_config['dc_in'] == True: 
            print("Starting DC IN Test")
            if snode.dc_in_test(): 
                updateState('runtest','pass - dc in','Pass','dc in')
            else: 
                test_status = 'Fail'
                updateState('runtest','fail - dc in','Fail','dc in')
        else: 
            print("DC IN TEST TOGGLE IS SET TO OFF (0). SKIPPING DC IN TEST.")
            updateState('runtest','skip - dc in','Skip','dc in')
    
    if 'commission' in test_config:
        commission_settings = test_config['commission']
        if misc.check_toggle(commission_settings):
            print("Commissioning Node")
            if commission(commission_settings): 
                updateState('runtest','pass - commission','Pass','commission')
            else: 
                test_status = 'Fail'
                updateState('runtest','fail - commission','Fail','commission')
        else: print("Commission settings missing or toggled off.")

    if 'cmd' in test_config:
        if testCMD(test_config['cmd']):
            updateState('runTest','pass - cmd','Pass','cmd')
        else:
            updateState('runTest','fail - cmd','Fail','cmd')
            test_status = 'Fail'
            if stop_on_failure:
                return False
            
    if 'rs485' in test_config and (test_config['rs485'] == 1 or test_config['rs485'] == True):
        if testRS485():
            updateState('runTest','pass - rs485','Pass','rs485')
        else:
            updateState('runTest','fail - rs485','Fail','rs485')
            test_status = 'Fail'
            if stop_on_failure:
                return False
            
    return True

def start():
    if not database.connect():
        updateState('start','failed - cannot connect to database','Failed','Cannot connect to database')
        return False
    if not parse_general_settings():
        updateState('start','failed - cannot load general_settings.yaml','Failed','Cannot parse settings')
        return False
    if not load_test_config():
        updateState('start','failed - cannot load test yaml','Failed','Cannot load test yaml')
        return False
    if not controller.open(microcontroller_port,baud,microcontroller_timeout):
    #if not controller.open_device("ARDUINO_NANO"): # Feature for future
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
    global CC_yaml, CV_yaml, CCUV_yaml
    if arg.lower() == 'cc':
        CC_yaml = True
        print('CC_yaml')
    elif arg.lower() == 'cv':
        CV_yaml = True
        print('CV_yaml')
    elif arg.lower() == 'ccuv' or arg.lower() == 'cccv':
        CCUV_yaml = True
        print('CCUV_yaml')
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
        device = 'ELS-Node'
    elif arg == 'usbc':
        usbc_node_test = True
        device = 'USBC-Node'
    elif arg[:2] == 'BB':
        battery_backup_test = True
        custom_sn = arg
        device = 'Battery-Backup'
        print("Recorded Serial Number will be: ", custom_sn)

def checkCSV(arg):
    global csv_arg_file_name
    if 'csv' in arg.lower():
        csv_arg_file_name = str(arg).lower().replace('.', '').replace('csv', '')
        if csv_arg_file_name == 'no': csv_arg_file_name = None
        else:
            csv_arg_file_name = f"{csv_arg_file_name}.csv"
            #print(f"NODE WILL BE RECORDED IN {csv_arg_file_name}.")

def checkArg(arg):
    return checkSkipDB(arg) or checkVerbose(arg) or checkCCCV(arg) or checkCustomDevice(arg) or checkSetSerialNumber(arg) or checkCSV(arg)    

def write_to_csv(
    csv_file_name: str,
    sn_to_csv=None,
    mac_to_csv=None,
    test_status: str = 'Pass',
    device: str = '',
    board_version: str = '',
    extra_columns: list = None  # extra columns to append
):
    folder_path = "records"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    csv_file_name = os.path.join(folder_path, csv_file_name)
    sn_exists = False
    mac_exists = False

    # Base columns
    base_fieldnames = ['Device', 'Rev', 'Serial Number', 'MAC Address', 'Status', 'Date']
    extra_columns = extra_columns or []

    # Check if file exists
    if not os.path.isfile(csv_file_name):
        # Create CSV with base + extra columns
        fieldnames = base_fieldnames + [f'Extra{i+1}' for i in range(len(extra_columns))]
        with open(csv_file_name, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
    else:
        # File exists, read existing header
        with open(csv_file_name, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            existing_fieldnames = reader.fieldnames or base_fieldnames

        # Add new ExtraX columns if missing
        for i in range(len(extra_columns)):
            col_name = f'Extra{i+1}'
            if col_name not in existing_fieldnames:
                existing_fieldnames.append(col_name)

        # If header changed, rewrite the CSV to include new columns
        if existing_fieldnames != reader.fieldnames:
            # Read old data
            with open(csv_file_name, 'r', newline='') as f:
                rows = list(csv.DictReader(f))
            # Rewrite with new header
            with open(csv_file_name, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=existing_fieldnames)
                writer.writeheader()
                writer.writerows(rows)

    # Check for duplicates
    with open(csv_file_name, 'r') as csvfile:
        lines = csvfile.readlines()
        for line in lines:
            if sn_to_csv and sn_to_csv in line:
                print(f"SERIAL NUMBER ALREADY IN {csv_file_name}.")
                sn_exists = True
            if mac_to_csv and mac_to_csv.lower() in line.lower() and mac_to_csv != "N/A":
                if mac_to_csv not in ['', None]:
                    print(f"MAC ADDRESS ALREADY IN {csv_file_name}.")
                mac_exists = True

    # Append row if no duplicates
    if not sn_exists and not mac_exists:
        with open(csv_file_name, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=existing_fieldnames)
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            row_data = {
                'Device': device,
                'Rev': board_version, 
                'Serial Number': sn_to_csv,
                'MAC Address': mac_to_csv.upper() if mac_to_csv else '',
                'Status': test_status,
                'Date': current_time
            } # board_version was board_version.capitalize()

            # Add extra columns dynamically
            for i, val in enumerate(extra_columns):
                row_data[f'Extra{i+1}'] = val

            writer.writerow(row_data)
        print(sn_to_csv, "has been written to", csv_file_name)
    else:
        print("NO DATA HAS BEEN WRITTEN.")


###################

def main(argv, arc):
    global test_id, serial_number, mac_address, board_version
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
        if runTest() and test_status != 'Fail':
            updateState('main','test end - pass','Completed','Pass')
            final_pass = True
        else:
            updateState('main','test end - fail','Completed','Fail')
    stop()

    t = time.localtime()
    date_csv_file = f"{t.tm_year % 100}_{t.tm_mon}_{t.tm_mday}.csv"
    csv_list = [
        f"fpy_{device}_{t.tm_year}.csv",
        f"fpy_{t.tm_year}.csv",
        batch_csv_file,
        date_csv_file
    ]

    if final_pass:
        print('\nfinal - pass')

    else:
        print('\nfinal - fail')
        csv_list = [
            f"fpy_{device}_{t.tm_year}.csv",
            f"fpy_{t.tm_year}.csv"
    ]

    if csv_arg_file_name != None: 
        # Set serial number to the battery backup serial number for writing to csv
        if battery_backup_test:
            serial_number = custom_sn 
            print("Battery Backup Serial Number:",serial_number)
            mac_address = 'N/A'


        csvs_to_write_to = prompt.multi_selection_prompt(
            title="Add Device to CSVs",
            message="Select which CSV files this device should be added to:",
            selections=csv_list
            )
        
        for csv_file in csvs_to_write_to:
            if csv_file == batch_csv_file or csv_file == date_csv_file: 
                write_to_csv(
                    csv_file_name=csv_file,
                    device=device,
                    board_version=board_version,
                    sn_to_csv=serial_number, 
                    mac_to_csv=mac_address, 
                    test_status=test_status,
                    extra_columns=test_notes)
            else: 
                #print(test_notes)
                write_to_csv( 
                    csv_file_name=csv_file,
                    device=device,
                    board_version=board_version,
                    sn_to_csv=serial_number, 
                    mac_to_csv=mac_address, 
                    test_status=test_status,
                    extra_columns=test_notes) # THESE ARE BOTH THE SAME AT THE MOMENT, IMPLEMENT LOGIC TO DIFFERENTIATE LATER
    else: print("ARGUMENT 'nocsv' WAS SET, NOT WRITING TO ANY CSV.")
    print('done')

if __name__ == '__main__':
    main(sys.argv, len(sys.argv))

