# test.py

from itertools import count
from context import TestContext

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

def parse_general_settings(ctx: TestContext) -> bool:
    """
    Load general_settings.yaml into ctx.general_settings_config and apply
    relevant settings (prompt keys, batch CSV name, load machine COM resource).
    Returns True on success, False on failure (with printed errors).
    """
    folder_path = "config"
    file_name = os.path.join(folder_path, "general_settings.yaml")
    data = load_yaml(file_name)
    if data is None:
        print("General Settings wasn't loaded. Please troubleshoot.")
        return False

    ctx.general_settings_config = data
    # ctx = globals().get("_CTX")  # fetch shared ctx if we stash it globally (see below) # NOTE REMOVED
    # if ctx is not None:
    #     ctx.general_settings_config = data

    # Prompt keys
    if 'prompt_continue_key' in data:
        ctx.prompt_continue_key = data['prompt_continue_key']
    if 'prompt_end_test_key' in data:
        ctx.prompt_end_test_key = data['prompt_end_test_key']

    # Load Machine COM: may be a string like "COM3" or a number
    if 'Load Machine COM' in data:
        com_port = data['Load Machine COM']
        # Accept "COM3", 3, or "3"
        if isinstance(com_port, str):
            # Keep only digits
            digits = ''.join(ch for ch in com_port if ch.isdigit())
            if digits:
                com_port_int = int(digits)
            else:
                # Fallback: try to parse as int; if fails, print and skip
                try:
                    com_port_int = int(com_port)
                except Exception:
                    print(f"Warning: could not parse Load Machine COM = {com_port!r}")
                    com_port_int = None
        else:
            try:
                com_port_int = int(com_port)
            except Exception:
                print(f"Warning: invalid Load Machine COM = {com_port!r}")
                com_port_int = None

        if com_port_int is not None:
            print(com_port_int)
            try:
                # This mirrors your original: ASRL<COM>::INSTR
                load.res_els.append(f'ASRL{com_port_int}::INSTR')
            except Exception as e:
                print(f"Warning: failed to append load resource for COM{com_port_int}: {e}")

    if 'BATCH' in data:
        ctx.batch_csv_file = data['BATCH']

    # Optional scan tuning (store in ctx now so discovery uses it)
    # (These were read by get_ip(ctx) already, but storing here helps other steps)
    if 'scan_timeout' in data:
        ctx.scan_timeout = data['scan_timeout']
    if 'scan_start' in data:
        ctx.scan_range_start = data['scan_start']
    if 'scan_end' in data:
        ctx.scan_range_end = data['scan_end']

    return True

def load_test_config(ctx: TestContext) -> bool:
    """
    Decide which test YAML to load based on ctx flags, set ctx.device,
    and populate ctx.test_config. Returns True/False.
    """

    folder_path = "config"

    # Determine YAML file
    if ctx.CV_yaml:
        file_name = os.path.join(folder_path, "test_CV.yaml")
        ctx.device = "CV-RS485"
    elif ctx.CC_yaml:
        file_name = os.path.join(folder_path, "test_CC.yaml")
        ctx.device = "CC-0-10"
    elif ctx.CCUV_yaml:
        file_name = os.path.join(folder_path, 'test_CCUV.yaml')
        ctx.device = 'CCUV'
    elif ctx.mini_node_test:
        file_name = os.path.join(folder_path, 'test_mini_node.yaml')
        ctx.device = 'Core-Node' # TODO REMOVE THE ONE IN CUSTOM DEVICE CHECK
    elif ctx.battery_backup_test:
        file_name = os.path.join(folder_path, 'test_battery_backup.yaml')
        ctx.device = 'Battery-Backup' # TODO REMOVE THE ONE IN CUSTOM DEVICE CHECK
    elif ctx.supernode_test:
        if ctx.device == 'Supernode':
            file_name = os.path.join(folder_path, 'test_supernode.yaml')
        elif ctx.device == 'Supernode CV':
            file_name = os.path.join(folder_path, 'test_supernode_CV.yaml')
        elif ctx.device == 'Supernode CC':
            file_name = os.path.join(folder_path, 'test_supernode_CC.yaml')
    elif ctx.usbc_node_test:
        file_name = os.path.join(folder_path, 'test_usbc.yaml')
        ctx.device = 'USBC-Node' # TODO REMOVE THE ONE IN CUSTOM DEVICE CHECK
    elif ctx.els_node_test: 
        file_name = os.path.join(folder_path, "test_CC.yaml")
        ctx.device = 'ELS-Node'
    else:
        file_name = os.path.join(folder_path, "test.yaml")  # default
        ctx.device = "CCUV"
    
    # Load YAML
    data = load_yaml(file_name)
    ctx.test_config = data or {}

    # test_config = load_yaml(file_name)
    # if test_config is not None: return True
    
    if data is not None:
        return True
    else:
        print("test config not loaded. Please troubleshoot.")
        return False

def _derive_subnet_from_host() -> str:
    host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE) \
                        .stdout.decode('utf-8').split(' ')[0]
    print("USING HOST IP. HOST IP IS:", host_ip)
    parts = host_ip.split('.')
    if len(parts) == 4:
        parts[3] = '255'
        return '.'.join(parts)
    return '192.168.1.255'

ip = ''
def get_ip(ctx: TestContext) -> bool:
    """
    Discover device IP, using ctx.general_settings_config for subnet/scan parameters.
    Populates ctx.ip on success. Returns True/False.

    Behavior matches legacy getIP() with these improvements:
      - Uses ctx instead of module-level globals
      - Clear separation of 'scan_sn' vs. controller fallback
      - Safer conditionals and logging
    """

    updateLog('getIP','start')
    #if mini_node_test: coap_client_scan.is_mini_node = True

    # Mini-node flag still toggles a scan behavior flag
    if ctx.mini_node_test:
        coap_client_scan.is_mini_node = True

    # --- Configure scan parameters from general_settings.yaml (if present)
    gs = ctx.general_settings_config or {}
    
    if 'subnet' in gs and gs['subnet']:
        coap_client_scan.subnet = gs['subnet']
    else:
        # Derive subnet from host IP (legacy logic)
        try:
            coap_client_scan.subnet = gs.get('subnet') or _derive_subnet_from_host()
            # host_ip = subprocess.run(['hostname', '-I'], stdout=subprocess.PIPE) \
            #                     .stdout.decode('utf-8').split(' ')[0]
            # print("USING HOST IP. HOST IP IS: ",host_ip)
            # parts = host_ip.split('.')
            # if len(parts) == 4:
            #     parts[3] = '255'
            #     coap_client_scan.subnet = '.'.join(parts)
            # else:
            #     print("Unexpected host IP format; defaulting subnet to 255 broadcast on 192.168.2.x")
            #     coap_client_scan.subnet = '192.168.2.255'
        except Exception as e:
            print("Failed to derive subnet from host IP:", e)
            coap_client_scan.subnet = '192.168.2.255'

    # Scan tuning  
    ctx.scan_timeout = gs.get('scan_timeout', ctx.scan_timeout)
    ctx.scan_range_start = gs.get('scan_start', ctx.scan_range_start)
    ctx.scan_range_end = gs.get('scan_end', ctx.scan_range_end)

    # --- Decide scanning mode
    if ctx.scan_sn:
        # Set the scan matching mode (by SN exact or leading digits for set_sn)
        
        if ctx.set_sn and ctx.sn_leading_digits_to_set_sn:
            print('scan subnet', coap_client_scan.subnet,
                  'for device with leading sn digit(s):', ctx.sn_leading_digits_to_set_sn)
            coap_client_scan.serial_number = ctx.sn_leading_digits_to_set_sn
            coap_client_scan.scan_for_leading_digits = True
        else:
            print('scan subnet', coap_client_scan.subnet, 'for sn', ctx.serial_number)
            coap_client_scan.serial_number = ctx.serial_number
            coap_client_scan.scan_for_leading_digits = False

        # Perform the scan
        coap_client_scan.scan(ctx.scan_range_start, ctx.scan_range_end, ctx.scan_timeout)

        # Evaluate scan results
        for node in getattr(coap_client_scan, 'nodes', []):
            try:
                node_sn = node['network']['serialnum']
                node_ip = node['ip']
            except Exception:
                continue

            # Normal mode: exact match
            if not ctx.set_sn and node_sn == ctx.serial_number:
                ctx.ip = node_ip
                print('scan found sn', ctx.serial_number, 'at', ctx.ip)
                updateLog('getIP', ctx.ip)
                return True

            # Set-SN mode: leading digits match
            if ctx.set_sn and ctx.sn_leading_digits_to_set_sn \
               and node_sn.startswith(ctx.sn_leading_digits_to_set_sn):
                ctx.ip = node_ip
                print('scan found sn leading digits', ctx.sn_leading_digits_to_set_sn, 'at', ctx.ip)
                updateLog('getIP', ctx.ip)
                return True

        # No match found via scan
        updateLog('getIP', 'failed')
        return False

def testSubnet(ctx, subnet) -> bool:
    # ip_split = ctx.ip.split('.')
    ip_split = (ctx.ip or '').split('.')
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

def testCodeVersion(ctx: TestContext, code_version: str) -> bool:

    dfu = coap_client.getDFUVersion(ctx.ip)
    golden = coap_client.getGoldenVersion(ctx.ip)
    dfd = coap_client.getDFDVersion(ctx.ip)

    if dfu != code_version:
        updateLog('testCodeVersion','fail dfu',dfu,'expected',code_version)
        return False
    
    if golden != code_version:
        updateLog('testCodeVersion','fail golden',golden)
        if ctx.update_golden:
            updateLog('testCodeVersion','update golden')
            coap_client.putValue(ctx.ip,'/dfu','updt',0) # NOTE No longer used
            elapsed = 0
            while elapsed < 100:
                time.sleep(1.0)
                elapsed += 1
                print('\r waiting for reboot: ',str(elapsed),end='')
            golden = coap_client.getGoldenVersion(ctx.ip)
            if ctx.require_golden_match == True:
                if  golden != code_version:
                    updateLog('testCodeVersion','fail golden',golden)
                    return False
        elif require_golden_match == True:
            return False
    if dfd != code_version:
        updateLog('testCodeVersion','fail dfd',dfd)
        if ctx.dfd_match_required:
            return False
    else: print("DFD Version Correctly Matches DFU.")
    return True


def testSerialNumber(ctx: TestContext, sn: str) -> bool:
    """
    Context-based version of testSerialNumber. Behavior unchanged.
    """
    _sync_ctx_to_globals(ctx)

    if ctx.mini_node_test:
        mnode.serial_number_test(sn)  # sn had serial_number before for some reason
    if ctx.set_sn or not ctx.scan_sn:
        coap_client.setSN(ctx.ip, str(sn))
        get_sn = coap_client.getSN(ctx.ip)
        if get_sn != str(sn):
            updateLog('testSerialNumber', 'fail get', get_sn)
            return False
        if ctx.set_sn:
            print("Serial number set to", get_sn)

    return True



def testBoardVersion(ctx: TestContext, bv: str) -> bool:
    """
    Context-based version of testBoardVersion. Behavior unchanged.
    """
    _sync_ctx_to_globals(ctx)

    if ctx.mini_node_test:
        if not mnode.get_board_version(ctx.ip):
            return False
    elif ctx.battery_backup_test:
        # legacy forced value for battery backup NOTE THIS SUCKS
        ctx.board_version = 'BB-R2'
        _sync_ctx_to_globals(ctx)
    else:
        get_bv = coap_client.getBoardVersion(ctx.ip)
        if get_bv != str(bv):
            updateLog('testBoardVersion', 'fail get', get_bv)
            return False

    return True


def testTrigger(ctx: TestContext, number_of_times_to_restart: int, seconds_to_wait_for_restart: float) -> bool:
    # TODO Replace this with a simpler timeout check, also ip check should be different

    _sync_ctx_to_globals(ctx)

    times_restarted = 0
    while(times_restarted < number_of_times_to_restart):
        coap_client.putValue(ctx.ip,'/network','cmd','trigger 1')
        count = 0
        while(count < seconds_to_wait_for_restart):
            try:
                print("Attempt",times_restarted+1,
                      "IP Address rediscovered:",
                      coap_client.getValue(ctx.ip,'/network','madr'))
                break
            except Exception:
                print("Awaiting ip...")
                time.sleep(1.0) # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
                print(count)    # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
                count += 1      # TODO THIS WAS ORIGINALLY OUTSIDE OF THIS EXCEPTION, CHECK IF NEEDED
        if coap_client.getValue(ctx.ip,'/network','madr') != ctx.ip: # TODO THIS WILL NEVER BE THE CASE!
            return False
        times_restarted += 1
    return True

def testCMD(ctx: TestContext, cmds) -> bool:
    
    _sync_ctx_to_globals(ctx)

    for cmd in cmds:
        if not coap_client.secure_setting(ctx.ip,'/network','cmd',str(cmd), True):
            # print(f"Failed to set cmd {cmd}")
            return False
    return True


def testCCCV(ctx: TestContext, cccv: int) -> bool:

    ctx.cccv_save = cccv

    if ctx.supernode_test: coap_client.setCCCV(ctx.ip,0,cccv)
    else: coap_client.setCCCV(ctx.ip,3,cccv)

    time.sleep(6.0)
            
    cccv1 = coap_client.getValue(ctx.ip,'/actuators/actuator1','cccv')
    cccv2 = coap_client.getValue(ctx.ip,'/actuators/actuator2','cccv')
    if cccv1 != str(cccv):
        updateLog('testCCCV','fail actuator1',cccv1)
        return False
    
    if not ctx.battery_backup_test or not 'battery_backup_loads' in ctx.test_config: # Accounts for when you are doing a battery backup test
        if cccv2 != str(cccv):
            updateLog('testCCCV','fail actuator2',cccv2)
            return False
    return True

def testMAXW(ctx: TestContext, maxw: int | str) -> bool:

    ctx.maxw_save = maxw

    coap_client.setMaxWatt(ctx.ip,0,str(maxw))
    
    if ctx.supernode_test:
        time.sleep(3.0)

    maxw1 = coap_client.getValue(ctx.ip,'/actuators/actuator1','maxw')
    maxw2 = coap_client.getValue(ctx.ip,'/actuators/actuator2','maxw')
    
    if maxw1 != str(maxw):
        updateLog('testMAXW','fail actuator1',maxw1)
        return False
    if maxw2 != str(maxw):
        updateLog('testMAXW','fail actuator2',maxw2)
        return False

    return True

def setMux(channel: int, verbose: bool = True, delay: float = 0.25):
    # If you want to improve the odds of it finding the mux, give it more time to read it in controller.py

    controller.setMux(channel - 1)

    if verbose: 
        print("Setting Mux to output on channel", channel)
    if delay: time.sleep(delay)
    #print("Mux channel",relay,"is",controller.getMux())
    current_mux = controller.getMux()
    count: int = 0
    while current_mux != channel - 1:
        current_mux = controller.getMux()
        if count == -1 or count % 50 == 0:
            print("Attempting to retrieve mux")
            count = 1
        #print("MUX WAS NOT SET PROPERLY FOR CHANNEL",channel,"- CURRENT MUX IS",current_mux)
        count += 1
        if delay: 
            time.sleep(delay)
        
        if count > 200:
            print("MUX failed to set after 200 polls; continuing anyway")
            break


@dataclass
class LoadTestResult:
    status: bool
    average_power: float | None
    median_power: float | None
    minimum_power: float | None
    maximum_power: float | None

def power_check(
        ctx: TestContext,
        power_to_check_against: float, 
        relay: int, 
        turn_off_load_after: bool = True, 
        reverse_power_thresh: bool = False
    ) -> LoadTestResult:
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
    test_value = (power_to_check_against - power) if reverse_power_thresh \
    else (power - power_to_check_against)

    if test_value < 0:
        if reverse_power_thresh: print(f"Failed initial power test at {power} watts. Expected at most {power_to_check_against} watts. Awaiting new measurement...")
        else: print(f"Failed initial power test at {power} watts. Expected at least {power_to_check_against} watts. Awaiting new measurement...")

        time.sleep(3.0)
        power = load.measurePower()

        # Second Power Check
        # If power to check against is less than power measured, wait, then measure again. Then await the user to measure a third time
        test_value = (power_to_check_against - power) if reverse_power_thresh \
        else (power - power_to_check_against)

        if test_value < 0:
            # Ask the user what to do
            if reverse_power_thresh: 
                cont = prompt.prompt(
                    "Power Measure Fail",
                    f"Power Measure Fail. Measured {power} watts. "
                    f"Expected at most {power_to_check_against} watts. Continue the test?"
                    )
                if not cont:
                    misc.updateLog('testLoad',relay,'fail excessive power',power)
                    return LoadTestResult(False, power, None, None, None)
            else: 
                if prompt.prompt("Power Measure Fail",f"Power Measure Fail. Measured {power} watts. Expected at least {power_to_check_against} watts. Continue the test?"):
                    pass
                else:
                    misc.updateLog('testLoad',relay,'fail inadequate power',power)
                    return LoadTestResult(False, power, None, None, None)
            
            # Third reading before final comparison
            power = load.measurePower()

        # Sets load output off
        # if turn_off_load_after: load.setOutputOn(False)
        load.setOutputOn(False)

        # if power is less than required, fail it. Else, pass it
        test_value = (power_to_check_against - power) if reverse_power_thresh \
        else (power - power_to_check_against)
                
        if test_value < 0:
            misc.updateLog('testLoad',relay,'fail power',power)
            return LoadTestResult(False, power, None, None, None)

    misc.updateLog('testLoad',relay,'pass power',power)
    if turn_off_load_after: load.setOutputOn(False)
    # return True
    return LoadTestResult(True, power, None, None, None)

def moving_power_check(
    ctx: TestContext,
    min_power_thresh: float = None,
    max_power_thresh: float = None,
    hold_time_seconds: float = 5.0,
    measure_every_seconds: float = 0.25,
    relay: int = 1,
    turn_off_load_after: bool = True
    ) -> LoadTestResult:
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
        print(f"\r Measurements: {power_measurements}", end='')
        # num_measurements += 1
        time.sleep(measure_every_seconds)
        time_elapsed += measure_every_seconds

    middle_value = lambda nums: sorted(nums)[len(nums)//2 - (1 if len(nums)%2==0 else 0)]
    # median_power = sorted(power_measurements)[len(power_measurements)//2 - (1 if len(power_measurements)%2==0 else 0)]

    avg_power = sum(power_measurements)/len(power_measurements)     # Get the average power from the list
    median_power = middle_value(power_measurements)    # Get the median power from the list
    minimum_power = min(power_measurements)                     # Get the minimum power from the list
    maximum_power = max(power_measurements)                     # Get the maximum power from the list
    print("Average Power: ",avg_power)
    print("Median Power: ",median_power)
    print("Minimum Power: ",minimum_power)
    print("Maximum Power: ",maximum_power)

    # Evaluate thresholds (min)
    p = None
    if min_power_thresh is not None:
        test_avg = avg_power - min_power_thresh
        test_med = median_power - min_power_thresh
        fail_type = None
        fail_power = None
        if test_avg < 0: 
            fail_type = "average"
            fail_power = f"Average: {avg_power}"
        if test_med < 0: 
            fail_type = ("average and median" if fail_type else "median")
            fail_power = (f"{fail_power}, and Median: {median_power}" if fail_power \
                          else f"Median: {median_power}")
        if test_avg < 0 or test_med < 0: 
            print(
                f"Failed initial {fail_type} power test at {fail_power} watts. "
                f"Expected at least {min_power_thresh} watts. "
                )
            p = prompt.abort_retry_ignore_prompt(
                "Power Measure Fail",f"Power Measure Fail. Measured {fail_power} watts. "
                f"Expected at least {min_power_thresh} watts.")

    # Evaluate thresholds (max)
    if p is None and max_power_thresh is not None:
        test_avg = max_power_thresh - avg_power
        test_med = max_power_thresh - median_power
        fail_type = None
        fail_power = None
        if test_avg < 0: 
            fail_type = ("average")
            fail_power = f"Average: {avg_power}"
        elif test_med < 0: 
            fail_type = ("average and median" if fail_type else "median")
            fail_power = (f"{fail_power}, and Median: {median_power}" if fail_power \
                          else f"Median: {median_power}")
        if test_avg < 0 or test_med < 0: 
            print(
                f"Failed initial {fail_type} power test at {fail_power} watts. "
                f"Expected at most {max_power_thresh} watts. "
                )
            p = prompt.abort_retry_ignore_prompt(
                "Power Measure Fail",
                f"Power Measure Fail. Measured {fail_power} watts. "
                f"Expected at most {max_power_thresh} watts.")

    if p is not None: 
        if p == "abort": 
            print("\nAbort was selected. Process ended.")
            #sys.exit()
            # return False
            return LoadTestResult(False, avg_power, median_power, minimum_power, maximum_power)
        elif p == "retry":
            print("Retrying...")
            time.sleep(3.0)
            return moving_power_check(
                ctx,
                min_power_thresh, max_power_thresh, 
                hold_time_seconds, measure_every_seconds, 
                relay, turn_off_load_after
            )
        elif p == "ignore":
            load.setOutputOn(False)
            print("Ignore was selected. Continuing test...")
            ctx.test_status = 'Fail'
            misc.updateLog('testLoad',relay,'fail power',power)
            return LoadTestResult(True, avg_power, median_power, minimum_power, maximum_power)

    misc.updateLog('testLoad',relay,'pass power',power)
    if turn_off_load_after: 
        load.setOutputOn(False)
    return LoadTestResult(True, avg_power, median_power, minimum_power, maximum_power)

def testLoad(ctx: TestContext,test_load) -> bool:
    """
    Context-based version of testLoad.
    Behavior is identical to legacy version.
    Only difference: all state is routed through ctx instead of globals.
    """
    _sync_ctx_to_globals(ctx)  # keep legacy globals in sync

    # Full converted logic (matching original 100%) will go here.
    # We will paste the complete version in Step 3.


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
        if test_load['cccv'] != ctx.cccv_save:
            if testCCCV(ctx, test_load['cccv']):
                updateLog('testCCCV','pass',test_load['cccv'])
                ctx.cccv_save = test_load['cccv']
                _sync_ctx_to_globals(ctx)
    # CUV
    if 'cuv' in test_load:
        if test_load['cuv'] != ctx.cccv_save:
            if coap_client.secure_setting(ctx.ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ctx.ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                updateLog('testCUV','pass',test_load['cuv'])
    # MAXW
    if 'maxw' in test_load:
        if test_load['maxw'] != ctx.maxw_save:
            if testMAXW(ctx, test_load['maxw']):
                updateLog('testMAXW','pass',test_load['maxw'])
    # turn_off_load_after toggle
    if 'turn_off_load_after' in test_load:
        print("turn_off_load_after found in test load:",test_load['turn_off_load_after'])
        if test_load['turn_off_load_after'] in (False, 0):
            turn_load_off_after = False
    else: turn_load_off_after = True

    if ctx.mini_node_test:
        if not ran_once: print("Starting Mini Node Load test")
        if not mnode.load_test(test_load): return False
        else: return True

    if ctx.els_node_test:
        print("Starting ELS load test")
        if not els.load_test(ctx.ip, test_load, ctx.test_config): return False
        else: return True

    if ctx.supernode_test:
        print("Starting Supernode load test")
        if not snode.load_test(test_load): return False
        else: return True

    # dim: int = 100
    # if 'dim' in test_load: dim = test_load['dim']
                
    # coap_client.setDim(ctx.ip,3,10)
    # time.sleep(1)
    # coap_client.setDim(ctx.ip,3,dim)

    # MIGHT NEED TO LOOK BACK AT PUTTING THIS IN IF DIM PROBLEMS PERSIST

    time.sleep(0.5)

    if ('CR' in test_load or 'CC' in test_load or 'CV' in test_load) and \
       ('power' in test_load or 'below_power' in test_load):

        # SET RELAYS
        relays = ['output1','output2']
        if ctx.battery_backup_test: relays = ['output1'] # Accounts for when you are doing a battery backup test 
        
        if not ctx.usbc_node_test: 
            # Dim set happens here
            dim: int = 100
            if 'dim' in test_load: dim = test_load['dim']
            coap_client.setDim(ctx.ip,3,10)
            time.sleep(1.25)
            coap_client.setDim(ctx.ip,3,dim)

            dim1 = coap_client.getDim(ctx.ip,1)
            dim2 = coap_client.getDim(ctx.ip,2)

            if dim1 != dim:
                updateLog('testLoad',1,'failed to set dim on channel 1 to',dim,"Current dim:",dim1)
                return False
            if dim2 != dim:
                updateLog('testLoad',2,'failed to set dim on channel 2 to',dim,"Current dim:",dim2)
                return False

        # If USBC test   
        else: relays = [ctx.usbc_current_channel] # usbc_current_channel is set in the test_loads function
            

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
            time_before_load_on = (test_load.get('time_before_load_on') 
            or ctx.test_config.get('time_before_load_on'))
            if time_before_load_on is not None:
                print("Time before load on was set in test config, delaying",time_before_load_on,"seconds.")
                time.sleep(time_before_load_on)

            # Sets load output on.
            if not ctx.usbc_node_test or not ran_once: load.setOutputOn(True)  

            # Moving Power Check
            if 'MOVING' in test_load and (test_load['MOVING'] != 0 and test_load['MOVING'] != False): 
                hold_load_time = test_load.get('hold_load_time', 10.0)
                measure_every_seconds = test_load.get('measure_every_seconds', 1.0)

                result = moving_power_check(
                    ctx=ctx,
                    min_power_thresh = min_power,
                    max_power_thresh = max_power,
                    hold_time_seconds = hold_load_time,
                    measure_every_seconds = measure_every_seconds,
                    relay = relay,
                    turn_off_load_after = turn_load_off_after
                )
                if not result.status:
                    ctx.add_notes(round(result.average_power, 5))
                    # updateTestNotes(round(result.average_power,5))
                    _sync_ctx_to_globals(ctx)
                    return False
                
            # Normal Power Check
            else:
                if 'hold_load_time' in test_load: 
                    time.sleep(test_load['hold_load_time'])
                elif 'loads' in ctx.test_config and \
                    'hold_load_time' in ctx.test_config['loads']: 
                    loads_setting = ctx.test_config['loads']
                    time.sleep(loads_setting['hold_load_time'])
                elif 'hold_load_time' in ctx.test_config: 
                    time.sleep(ctx.test_config['hold_load_time'])
                time.sleep(1.0)

                # Perform power check
                if invert_power_thresh: 
                    result = power_check(ctx, max_power, relay, turn_load_off_after, invert_power_thresh)
                else: result = power_check(ctx, min_power, relay, turn_load_off_after)

                if not result.status:
                    ctx.add_notes(round(result.average_power, 5))
                    # updateTestNotes(round(result.average_power,5))
                    return False

            # Successful measurement
            ctx.add_notes(round(result.average_power, 5))     
            # updateTestNotes(round(result.average_power,5))    
            ran_once = True
        
        return True
    
    if ctx.supernode_test: load.setOutputOn(False)


    # End-of-function sync
    _sync_ctx_to_globals(ctx)
    return True

def testLoads(ctx: TestContext, test_loads: list) -> bool:

    _sync_ctx_to_globals(ctx)  # keep legacy globals in sync
    test_pass = True

    if ctx.mini_node_test: 
        print("Testing Mini Node Loads")
        if not mnode.loads_test(test_loads): return False
        return True
    
    if ctx.usbc_node_test:
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
            if not testLoad(ctx, test_load): test_pass = False

    load.setOutputOn(False)

    if test_pass:
        updateLog('testLoads','pass')
        _sync_ctx_to_globals(ctx)
        return True
    
    updateLog('testLoads','fail')
    _sync_ctx_to_globals(ctx)
    return False

# clean up function before return
def returnTestSensor1(ctx: TestContext, ret):
    if not ctx.mini_node_test: coap_client.secure_setting(ctx.ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
    if not ctx.supernode_test: coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','3') # disable motion
    else: coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','0') # disable motion (supernode)
    return ret

def testSensor1(ctx: TestContext, do_test) -> bool:
    
    _sync_ctx_to_globals(ctx)  # keep legacy globals in sync

    if ctx.mini_node_test:
        if mnode.sensor_test(): return True
        else: return False

    coap_client.putValue(ctx.ip,'/sensors/sensor1','eventrisefall','on,off') # change sensor 1 events
    coap_client.putValue(ctx.ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
    coap_client.putValue(ctx.ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    # coap_client.putValue(ctx.ip,'/policy','updown','10,10,90,5') # this should be default, but change if not
    coap_client.putValue(ctx.ip,'/actuators/actuator1','motdsbl','33') # enable motion

    if ctx.usbc_node_test: misc.send_test_prompt(misc.key,f'Connect control port of {device} to test station and press {misc.key}','')

    
    controller.setAux(1,False,'') # set Aux1 low
    coap_client.setDim(ctx.ip,3,0) # clear dim

    time.sleep(5.0) # wait for event
    controller.setAux(1,True,'') # set Aux1 high, test rising edge of sensor1
    time.sleep(5.0) # wait for event
    
    dim1 = coap_client.getDim(ctx.ip,1) # dim1 should be 100%
    dim2 = coap_client.getDim(ctx.ip,2) # dim2 should be 100%
    if dim1 <= 0:
        updateLog('testSensor1','high',1,'fail set dim',dim1)
        return returnTestSensor1(ctx, False) # DREW note turn aux 1 off if fail
    elif dim2 <= 0:
        updateLog('testSensor1','high',2,'fail set dim',dim2)
        return returnTestSensor1(ctx, False)
    else: updateLog('testSensor1','high','pass set dim', dim2)

    time.sleep(2.0)

    controller.setAux(1,False,'') # set Aux1 low, test falling edge of sensor1
    time.sleep(1.0) # wait for  event
    dim1 = coap_client.getDim(ctx.ip,1) # dim1 should be 0%
    dim2 = coap_client.getDim(ctx.ip,2) # dim2 should be 0%

    if dim1 != 0:
        updateLog('testSensor1','low',1,'fail set dim',dim1)
        return returnTestSensor1(ctx,False)
    elif dim2 != 0:
        updateLog('testSensor1','low',2,'fail set dim',dim2)
        return returnTestSensor1(ctx,False)
    else: updateLog('testSensor1','low','pass set dim', dim2)
    return returnTestSensor1(ctx,True)

def testPDLine(ctx: TestContext,do_test) -> bool:

    _sync_ctx_to_globals(ctx)  # keep legacy globals in sync

    if ctx.mini_node_test:
        if not mnode.wallswitch_test(mnode.drivers): 
            return False
        else: 
            return True
    if not ctx.supernode_test and not ctx.mini_node_test:
        coap_client.putValue(ctx.ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
        coap_client.putValue(ctx.ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    elif ctx.mini_node_test:
        if not coap_client.secure_setting(ctx.ip,'/drivers/0/wallswitch','enable','true'): 
            misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver console and press {misc.key} when it has been set.','')
        if mnode.remote_driver_exists: 
            if not coap_client.secure_setting(ctx.ip,'/drivers/1/wallswitch','enable','true'): 
                misc.send_test_prompt(misc.key,f'Type "set_wallswitch_enable true" in driver console and press {misc.key} when it has been set.','')
    else: 
        misc.send_test_prompt(misc.key,f'Connect control port of {device} to test station and press {misc.key}','')
    
    controller.setPush4BTNOff() # press off button, but ignore event
    coap_client.setDim(ctx.ip,0,0) # clear dim, in case off button did not work
    time.sleep(1.0) # CHECK TO SEE IF THIS IS NECESSARY
    
    updateLog('Starting PDLine Testing')
    attempts = 0
    while attempts != 10:
        time.sleep(0.25)
        controller.setPush4BTNOn()
        dim1 = coap_client.getDim(ctx.ip,1) # dim1 should be 0%
        dim2 = coap_client.getDim(ctx.ip,2)
        attempts += 1
        if dim1 == 100 and dim2 == 100:
            break

    updateLog('Attempts taken for dim 100:', attempts)
    if dim1 != 100:
        updateLog('testPDLine','On',1,'fail set dim',dim1)
        return False
    if dim2 != 100:
        if ctx.mini_node_test and not mnode.remote_driver_exists: 
            pass # A mini node with only one driver will not have a second channel to test
        else:
            updateLog('testPDLine','On',2,'fail set dim',dim2)
            return False
    # OFF attempts
    attempts = 0
    while attempts != 10:
        time.sleep(0.25)
        controller.setPush4BTNOff()
        dim1 = coap_client.getDim(ctx.ip,1) # dim1 should be 0%
        dim2 = coap_client.getDim(ctx.ip,2)
        attempts += 1
        if dim1 == 0 and dim2 == 0: 
            break
    updateLog('Attempts taken for dim 0:', attempts)

    if dim1 != 0:
        updateLog('testPDLine','Off',1,'fail set dim',dim1)
        return False
    if dim2 != 0:
        updateLog('testPDLine','Off',2,'fail set dim',dim2)
        return False
    return True

def testBatteryLoad(ctx: TestContext, upper_load,lower_load,key,wait_time) -> bool:

    if not testCCCV(ctx, 10): 
        return False
    coap_client.setDim(ctx.ip,3,90)
    time.sleep(1)
    coap_client.setDim(ctx.ip,3,100)

    time.sleep(wait_time)

    if not testLoad(ctx, upper_load): 
        return False

    if not testCCCV(ctx, 10): 
        return False

    coap_client.setDim(ctx.ip,3,90)
    time.sleep(1)
    coap_client.setDim(ctx.ip,3,100)
    
    # misc.send_test_prompt(key,f"Press and hold switch test button. Then press {key} on keyboard when ready.", "Keep button held.")
    if prompt.prompt("Switch Test Button", "Press and hold switch test button. Select 'Okay' to continue or 'Cancel' to end test."): 
        print("Keep button held")
    else: 
        return False

    time.sleep(wait_time)
    if not testLoad(ctx, lower_load): 
        return False
    print("Release button")
    time.sleep(5.0)
    coap_client.setDim(ctx.ip,3,100)
    if not testLoad(ctx, upper_load): 
        return False
    

# TESTING FEATURE
    coap_client.setDim(ctx.ip,3,0)
    if not testCCCV(ctx, 255): # Replaced cv 0
        return False
    #if not testCCCV(ctx, 0): 
        #return False
    #coap_client.setDim(ctx.ip,3,0) # Commented out

    print("Dim:",coap_client.getDim(ctx.ip,1),coap_client.getDim(ctx.ip,2),"; CCCV:", coap_client.getCCCV(ctx.ip,1),coap_client.getCCCV(ctx.ip,2))
    time.sleep(wait_time*2)


    #misc.send_test_prompt(key, f"Unplug Channel 1, then press {key}","Testing Power Loss Backup")
    #time.sleep(wait_time)

    if not testLoad(ctx, lower_load): 
        return False
    
    #misc.send_test_prompt(key, f"Plug in Channel 1, then press {key}","Testing Normal High Load")
    #time.sleep(wait_time)

    if not testCCCV(ctx, 10): 
        return False
    if not testMAXW(ctx, ctx.test_config['maxw']): 
        return False
    # coap_client.setDim(ctx.ip,3,100)
    if not testLoad(ctx, upper_load): 
        return False

    print("Remember to unplug pink battery backup connectors when finished testing.")
    return True

def USBC_test_loads(ctx, test_loads): # TODO REFACTOR THIS TO USE testLoad FUNCTION OR PUT INTO ITS OWN THING

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
                if coap_client.secure_setting(ctx.ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ctx.ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                    updateLog('testCUV','pass',test_load['cuv'])
        if 'maxw' in test_load:
            if test_load['maxw'] != maxw_save:
                if testMAXW(ctx, test_load['maxw']):
                    updateLog('testMAXW','pass',test_load['maxw'])
        if 'turn_off_load_after' in test_load:
            if test_load['turn_off_load_after'] == False or test_load['turn_off_load_after'] == 0:
                turn_load_off_after = False
        else: turn_load_off_after = True

        dim: int = 100
        if 'dim' in test_load: dim = test_load['dim']

        # print("Load Dim is",dim)
        #coap_client.setDim(ctx.ip,3,100)
        time.sleep(1.0)
        coap_client.setDim(ctx.ip,3,dim)

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
            elif 'time_before_load_on' in ctx.test_config: time.sleep(ctx.test_config['time_before_load_on'])
            # Sets load output on.
            if not usbc_node_test or not ran_once: load.setOutputOn(True)  

            if 'hold_load_time' in test_load: time.sleep(test_load['hold_load_time'])
            elif 'loads' in ctx.test_config and 'hold_load_time' in ctx.test_config['loads']: 
                loads_setting = ctx.test_config['loads']
                time.sleep(loads_setting['hold_load_time'])
            elif 'hold_load_time' in ctx.test_config: time.sleep(ctx.test_config['hold_load_time'])
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

def testBatteryBackup(ctx: TestContext, batt_test_load) -> bool:
    if "Low Load" in batt_test_load: low_load = batt_test_load["Low Load"]
    else: 
        print("No Low Load in yaml file")
        return False

    if "High Load" in batt_test_load: high_load = batt_test_load["High Load"]
    else:
        print("No High Load in yaml file")
        return False

    if "await_key" in ctx.test_config: await_key = ctx.test_config["await_key"]
    else: await_key = misc.key

    if "await_time" in ctx.test_config: batt_wait_time = ctx.test_config["await_time"]
    else: batt_wait_time = 2

    if not testBatteryLoad(ctx, high_load,low_load,await_key,batt_wait_time):
        return False

    return True

def commission(ctx: TestContext, commission_settings) -> bool:
    """Commission settings to a device. Settings are set in the YAML test configuration file."""
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
            if 'actuators' in resource: 
                resource_type = 'actuator'
            elif 'sensors' in resource: 
                resource_type = 'input'
            else: 
                resource_type = 'unknown'
            print(f"Applying settings to all {ctx.node_channels} {resource_type} channels:")
            for k, v in kv_pairs.items():
                print(f"  {k}: {v}")
            for channel in range(1,ctx.node_channels+1): # FIND THIS VARIABLE IN THE INITIALIZATION SECTION WHERE CHANNELS ARE DEFINED BY NODE TYPE 
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
                    if not coap_client.secure_setting(ctx.ip, resource_channel, key, value, checkVerbose, timeout = 5.0):
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
                if not coap_client.secure_setting(ctx.ip, resource, key, value, checkVerbose, timeout = 8.0):
                    print(f"Failed to apply {key}={value} on {resource}")
                    success = False

    time.sleep(5.0)  # Allow time to write to EEPROM
    
    print("Commissioning complete. Writing to EEPROM...")
    return success

def testRS485(ctx):
    rs485.main()
    #misc.send_test_prompt(misc.key,f"Verify RS485 communication was successful. Press {misc.key} if it passed and 'Esc' if it failed.", "")
    if prompt.prompt("RS485 Testing", "Check the console to see if RS485 communication was successful. Did it pass?"):
        return True
    else: return False

def runTest(ctx): #TODO No return type specified

    cfg = ctx.test_config
    _sync_ctx_to_globals(ctx)

    #
    # ─────────────────────────────────────────────
    # 1. Code Version Test
    # ─────────────────────────────────────────────
    if 'code_version' in cfg:
        if testCodeVersion(ctx, cfg['code_version']):
            updateState('runTest','pass - code_version','Pass','code_version')
        else:
            updateState('runTest','fail - code_version','Fail','code_version')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
        _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 2. Trigger Test (optional, probabilistic)
    # ─────────────────────────────────────────────
    if cfg.get('trigger_1_test'):
        chance = cfg.get('chance_to_test_trigger_1', 0)
        if random.random() < chance / 100:
            print("Starting Trigger 1 Test")
            attempts = cfg.get('number_of_trigger_1_attempts', 1)
            wait_sec = cfg.get('seconds_to_wait_for_restart', 5)
            if testTrigger(ctx, attempts, wait_sec):
                updateState('runTest', 'pass - trigger1', 'Pass', 'trigger1')
            else:
                updateState('runTest', 'fail - trigger1', 'Fail', 'trigger1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        _sync_ctx_to_globals(ctx)

    #
    # ─────────────────────────────────────────────
    # 3. Update DB flag (unchanged behavior)
    # ─────────────────────────────────────────────
    if cfg.get('update_db'):
        coap_client.putValue(ctx.ip, '/network', 'cmd', 'update_db')
        time.sleep(8.0)
    _sync_ctx_to_globals(ctx)
    
    #
    # ─────────────────────────────────────────────
    # 4. Capture SN + MAC (after DB update)
    # ─────────────────────────────────────────────
    if not ctx.battery_backup_test:
        sn = coap_client.getSN(ctx.ip)
        ctx.serial_number = sn  # write into context
        if ctx.mini_node_test: 
            mac = coap_client.getValue(ctx.ip, '/network', 'mac')
        else:
            mac = coap_client.getMAC(ctx.ip)
        ctx.mac_address = str(mac).upper()
        updateLog('SN:', sn, 'MAC:', ctx.mac_address)
    else:
        # Battery Backup test uses a special SN provided earlier
        ctx.mac_address = 'N/A'

    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 5. Device-specific initialization
    # ─────────────────────────────────────────────
    if ctx.mini_node_test:
        ctx.node_channels = 1
        mnode.init(ctx.ip, cfg, ctx.serial_number)
        print("Initializing Mini Node Test")


    elif ctx.els_node_test: 
        print("Initializing ELS test")
        coap_client.putValue(ctx.ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ctx.ip,'/actuators/actuator1','els','true')
        coap_client.putValue(ctx.ip,'/actuators/actuator1','dimels',100)
        coap_client.putValue(ctx.ip,'/actuators/actuator2','dimels',100)

    elif ctx.usbc_node_test: 
        print("Initializing USBC Node Test")
    elif ctx.battery_backup_test:
        print("Initializing battery backup test")
    elif ctx.supernode_test:
        ctx.node_channels = 8
        print("Initializing supernode test")
        snode.init(ctx.ip, cfg)

        
        # igain setup logic
        igain_var = 'cv_igain10'
        if ctx.device in ('Supernode CC', 'Supernode'):
            igain_var = 'cc_igain10'
        for target in [(igain_var, 7), ('cv_igain10', 15)]:
            name, val = target
            for attempt in range(10):
                coap_client.putValue(ctx.ip,'/actuators/actuator1',name,val)
                got = coap_client.getValue(ctx.ip,'/actuators/actuator1',name)
                if got == val:
                    print(name, "has been set to", got)
                    break
                else:
                    print(name, "failed to set to", val, "after", attempt+1, "retries")

        for i in range(1,8):
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'sentype','disable') # change sensor 1 events supernode version
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'eventlh','default') 
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'eventhl','default') # change sensor 1 events supernode version

    else:
        if not ctx.mini_node_test:
            coap_client.putValue(ctx.ip,'/network','cmd','set_ws 0')
            coap_client.putValue(ctx.ip,'/network','cmd','set_max_amp 3 2500')
    
    _sync_ctx_to_globals(ctx)
    
    #
    # ─────────────────────────────────────────────
    # 6. Subnet Validation
    # ─────────────────────────────────────────────
    if 'subnet' in cfg:
        if testSubnet(ctx, cfg['subnet']):
            updateState('runTest','pass - subnet','Pass','subnet')
        else:
            updateState('runTest','fail - subnet','Fail','subnet')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 7. Serial Number Test
    # ─────────────────────────────────────────────
    
    if ctx.serial_number not in ('', '0'):
        if testSerialNumber(ctx,ctx.serial_number):
            updateState('runTest','pass - serial_number','Pass','serial_number')
        else:
            updateState('runTest','fail - serial_number','Fail','serial_number')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 8. Board Version Test
    # ─────────────────────────────────────────────
    if ctx.board_version and not ctx.supernode_test:
        if testBoardVersion(ctx,ctx.board_version):
            updateState('runTest','pass - board_version','Pass', f'board_version:{ctx.board_version}')
        else:
            updateState('runTest','fail - board_version','Fail', f'board_version:{ctx.board_version}')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    #
    # ─────────────────────────────────────────────
    # 9. CCCV Test
    # ─────────────────────────────────────────────
    if 'cccv' in cfg:
        if testCCCV(ctx, cfg['cccv']):
            updateState('runTest','pass - cccv','Pass','cccv')
        else:
            updateState('runTest','fail - cccv','Fail','cccv')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 10. MAXW Test
    # ─────────────────────────────────────────────
    if 'maxw' in cfg:
        if testMAXW(ctx, cfg['maxw']):
            updateState('runTest','pass - maxw','Pass','maxw')
        else:
            updateState('runTest','fail - maxw','Fail','maxw')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 11. Single Load Test
    # ─────────────────────────────────────────────
    if 'load' in cfg:
        load_cfg = cfg['load']
        if misc.check_toggle(load_cfg):
            print("Starting Load Test")
            if testLoad(ctx, load_cfg):
                updateState('runTest','pass - load','Pass','load')
            else:
                updateState('runTest','fail - load','Fail','load')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOAD TEST TOGGLE IS SET TO OFF (0). SKIPPING LOAD TEST.")
            updateState('runTest','skip - load','Skip','load')
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 12. Multi-step Load Tests
    # ─────────────────────────────────────────────
    if 'loads' in cfg:
        loads_cfg = cfg['loads']
        if misc.check_toggle(loads_cfg):
            print("Starting Loads Test")
            if testLoads(ctx, loads_cfg['test_steps']):
                updateState('runTest','pass - loads','Pass','loads')
            else:
                updateState('runTest','fail - loads','Fail','loads')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOADS TEST TOGGLE IS SET TO OFF (0). SKIPPING LOADS TEST.")
            updateState('runTest','skip - loads','Skip','loads')
    _sync_ctx_to_globals(ctx)


    
    #
    # ─────────────────────────────────────────────
    # 13. RGBW Test
    # ─────────────────────────────────────────────
    if 'rgbw' in cfg:
        rgbw_sets = cfg['rgbw']
        if not isinstance(rgbw_sets, list) or not all(isinstance(x, int) for x in rgbw_sets):
            print("RGBW Sets in test_config must be formatted as a list of ints. Proceeding with default values.")
            rgbw_sets = [4278190080,16711680,65280,255,4294967295]
        if ctx.mini_node_test:
            mnode.rgbw_test(rgbw_sets)
    _sync_ctx_to_globals(ctx)

    
#
    # ─────────────────────────────────────────────
    # 14. Sensor 1 Test
    # ─────────────────────────────────────────────
    if 'sensor1' in cfg:
        val = cfg['sensor1']
        if val in (1, True):
            if testSensor1(ctx, val):
                updateState('runTest','pass - sensor1','Pass','sensor1')
            else:
                updateState('runTest','fail - sensor1','Fail','sensor1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        elif val in (0, False):
            print(f"SENSOR1 TEST TOGGLE IS SET TO OFF {val}. SKIPPING SENSOR1 TEST.")
        else:
            print(f"SENSOR1 TEST TOGGLE INVALID: {val}. SKIPPING.")
    _sync_ctx_to_globals(ctx)

    
#
    # ─────────────────────────────────────────────
    # 15. PDLine Test
    # ─────────────────────────────────────────────
    #
    if 'pdline' in cfg:
        v = cfg['pdline']
        if v in (1, True):
            if testPDLine(ctx, v):
                updateState('runTest','pass - pdline','Pass','pdline')
            else:
                updateState('runTest','fail - pdline','Fail','pdline')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print(f"PDLINE TEST TOGGLE IS SET TO OFF {v}. SKIPPING PDLINE TEST.")
    _sync_ctx_to_globals(ctx)


    
    #
    # ─────────────────────────────────────────────
    # 16. Battery Backup Loads Test
    # ─────────────────────────────────────────────
    if 'battery_backup_loads' in cfg:
        ctx.battery_backup_test = True
        ctx.mac_address = ''
        if testBatteryBackup(ctx, cfg["battery_backup_loads"]):
            print('pass','battbackup')
            updateState('runTest','pass - battbackup','Pass','battbackup')
        else:
            updateState('runTest','fail - battbackup','Fail','battbackup')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    
    #
    # ─────────────────────────────────────────────
    # 17. Mini Node Firmware Upgrade
    # ─────────────────────────────────────────────
    if ctx.mini_node_test and cfg.get('firmware_upgrade'):
        print("Starting firmware upgrade...")
        mnode.firmware_upgrade_test()
    _sync_ctx_to_globals(ctx)

    
    
    #
    # ─────────────────────────────────────────────
    # 18. Supernode DC-IN Test
    # ─────────────────────────────────────────────
    if ctx.supernode_test and 'dc_in' in cfg:
        if cfg['dc_in'] in (1, True):
            print("Starting DC IN Test")
            if snode.dc_in_test():
                updateState('runtest','pass - dc in','Pass','dc in')
            else:
                ctx.test_status = 'Fail'
                updateState('runtest','fail - dc in','Fail','dc in')
                if ctx.stop_on_failure:
                    return False
        else:
            print("DC IN TEST TOGGLE SET TO OFF (0). SKIPPING.")
            updateState('runtest','skip - dc in','Skip','dc in')
    _sync_ctx_to_globals(ctx)

    
    
    #
    # ─────────────────────────────────────────────
    # 19. Commissioning
    # ─────────────────────────────────────────────
    if 'commission' in cfg:
        commission_settings = cfg['commission']
        if misc.check_toggle(commission_settings):
            print("Commissioning Node")
            if commission(ctx, commission_settings):
                updateState('runtest','pass - commission','Pass','commission')
            else:
                ctx.test_status = 'Fail'
                updateState('runtest','fail - commission','Fail','commission')
                if ctx.stop_on_failure:
                    return False
        else:
            print("Commission settings missing or toggled off.")
    _sync_ctx_to_globals(ctx)
    
    #
    # ─────────────────────────────────────────────
    # 20. CMD list execution
    # ─────────────────────────────────────────────
    if 'cmd' in cfg:
        if testCMD(ctx, cfg['cmd']):
            updateState('runTest','pass - cmd','Pass','cmd')
        else:
            updateState('runTest','fail - cmd','Fail','cmd')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    #
    # ─────────────────────────────────────────────
    # 21. RS485 test
    # ─────────────────────────────────────────────
    if 'rs485' in cfg and cfg['rs485'] in (1, True):
        if testRS485(ctx):
            updateState('runTest','pass - rs485','Pass','rs485')
        else:
            updateState('runTest','fail - rs485','Fail','rs485')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    _sync_ctx_to_globals(ctx)

    #
    # ─────────────────────────────────────────────
    # Final return
    # ─────────────────────────────────────────────
    return ctx.test_status != 'Fail'


def start() -> bool:
    if not database.connect():
        updateState('start','failed - cannot connect to database','Failed','Cannot connect to database')
        return False
    
    _CTX = globals().get("_CTX")  # TEMP until we thread ctx through start()
    if _CTX is None:
        print("Internal error: _CTX missing")
        return False

    if not parse_general_settings(_CTX):
        updateState('start','failed - cannot load general_settings.yaml','Failed','Cannot parse settings')
        return False
    if not load_test_config(_CTX):
        updateState('start','failed - cannot load test yaml','Failed','Cannot load test yaml')
        return False
    if not controller.open(_CTX.microcontroller_port,_CTX.baud,_CTX.microcontroller_timeout):
    #if not controller.open_device("ARDUINO_NANO"): # Feature for future
        updateState('start','failed - cannot open controller port','Failed','Cannot open controller port')
        return False
    controller.print_rx = _CTX.debug_print # debug
    controller.startRXThread() # Check to see if this is causing console bloat - Drew
    
    if not get_ip(_CTX):
        updateState('start','failed - cannot get node ip','Failed','Cannot get node ip')
        return False
    _sync_ctx_to_globals(_CTX)
    if not load.open() and 'load' in _CTX.test_config:
        updateState('start','failed - cannot open electronic load','Failed','Cannot open electronic load')
        return False

    # OPTIONAL SYNC: reflects any changes from settings/test_config/ip into ctx
    # _sync_ctx_to_globals(globals().get("_CTX")) # NOTE REMOVED BECAUSE REDUNDANT

    return True

def stop():
    controller.close()
    load.close()

def checkScanSN(ctx: TestContext, arg: str) -> bool:
    if arg == '-s':
        ctx.scan_sn = True
        return True
    return False

def checkVerbose(ctx: TestContext, arg: str) -> bool:
    if arg == '-v':
        ctx.debug_print = True
        print('verbose controller print rx')
        return True
    return False

def checkSkipDB(ctx: TestContext, arg: str) -> bool:
    if arg == 'skip_db':
        database.skip_db = True
        print('skip_db')
        return True
    return False

def checkCCCV(ctx: TestContext, arg: str) -> bool:
    if arg.lower() == 'cc':
        ctx.CC_yaml = True
        print('CC_yaml')
        return True
    elif arg.lower() == 'cv':
        ctx.CV_yaml = True
        print('CV_yaml')
        return True
    elif arg.lower() == 'ccuv' or arg.lower() == 'cccv':
        ctx.CCUV_yaml = True
        print('CCUV_yaml')
        return True
    else: return False


def checkSetSerialNumber(ctx: TestContext, arg: str) -> bool:
    if arg.startswith('set_sn'):
        print("Set SN Mode Active")
        ctx.set_sn = True
        ctx.sn_leading_digits_to_set_sn = arg[6:]
        print(ctx.sn_leading_digits_to_set_sn)
        return True
    if arg.startswith('setsn'):
        print("Set SN Mode Active")
        ctx.set_sn = True
        ctx.sn_leading_digits_to_set_sn = arg[5:]
        print(ctx.sn_leading_digits_to_set_sn)
        return True
    return False

# def checkSetSerialNumber(ctx: TestContext, arg: str) -> bool:
#     if arg[:6] == 'set_sn': 
#         print("Set SN Mode Active")
#         ctx.set_sn = True
#         ctx.sn_leading_digits_to_set_sn = arg[6:]
#         print(ctx.sn_leading_digits_to_set_sn)
#     elif arg[:5] == 'setsn': 
#         print("Set SN Mode Active")
#         ctx.set_sn = True
#         ctx.sn_leading_digits_to_set_sn = arg[5:]

def checkCustomDevice(ctx: TestContext, arg: str) -> bool:
    if arg in ('mini_node', 'mini', 'mnode', 'core_node', 'core', 'cnode'):
        ctx.mini_node_test = True
        ctx.device = "Core Node"
        return True
    if arg.startswith('super'):
        ctx.supernode_test = True
        ctx.device = 'Supernode'
        if arg == 'supercv': ctx.device = 'Supernode CV'
        elif arg == 'supercc': ctx.device = 'Supernode CC'
        return True
    if arg in ('els', 'ELS'):
        ctx.els_node_test = True
        ctx.device = 'ELS-Node'
        return True
    if arg == 'usbc':
        ctx.usbc_node_test = True
        ctx.device = 'USBC-Node'
        return True
    if arg.startswith('BB'):
        ctx.battery_backup_test = True
        ctx.custom_sn = arg
        ctx.device = 'Battery-Backup'
        print("Recorded Serial Number will be: ", ctx.custom_sn)
        return True
    return False 

# def checkCustomDevice(ctx: TestContext, arg: str) -> bool:
#     global device, els_node_test, supernode_test, usbc_node_test, battery_backup_test, mini_node_test, custom_sn
#     if arg in ('mini_node', 'mini', 'mnode', 'core_node', 'core', 'cnode'):
#         ctx.mini_node_test = True
#         ctx.device = "Core Node"
#         return True
#     elif arg[:5] == 'super':
#         ctx.supernode_test = True
#         ctx.device = 'Supernode'
#         if arg == 'supercv': ctx.device = 'Supernode CV'
#         elif arg == 'supercc': ctx.device = 'Supernode CC'
#         return True
#     elif arg == 'els' or arg == 'ELS':
#         ctx.els_node_test = True
#         ctx.device = 'ELS-Node'
#         return True
#     elif arg == 'usbc':
#         ctx.usbc_node_test = True
#         ctx.device = 'USBC-Node'
#         return True
#     elif arg[:2] == 'BB':
#         ctx.battery_backup_test = True
#         ctx.custom_sn = arg
#         ctx.device = 'Battery-Backup'
#         print("Recorded Serial Number will be: ", custom_sn)
#         return True


def checkCSV(ctx, arg) -> bool:
    if 'csv' in arg.lower():
        name = str(arg).lower().replace('.', '').replace('csv', '')
        ctx.csv_arg_file_name = None if name == 'no' else f"{name}.csv"
        return True
    return False

# def checkCSV(arg):
#     global csv_arg_file_name
#     if 'csv' in arg.lower():
#         csv_arg_file_name = str(arg).lower().replace('.', '').replace('csv', '')
#         if csv_arg_file_name == 'no': csv_arg_file_name = None
#         else:
#             csv_arg_file_name = f"{csv_arg_file_name}.csv"
#             #print(f"NODE WILL BE RECORDED IN {csv_arg_file_name}.")


def checkArg(ctx, arg) -> bool:
    return (
        checkSkipDB(ctx, arg) or
        checkVerbose(ctx, arg) or
        checkCCCV(ctx, arg) or
        checkCustomDevice(ctx, arg) or
        checkSetSerialNumber(ctx, arg) or
        checkCSV(ctx, arg)
    )

def write_to_csv(
    csv_file_name: str,
    sn_to_csv=None,
    mac_to_csv=None,
    test_status: str = 'Pass',
    device: str = '',
    board_version: str = '',
    extra_columns: list = None  # extra columns to append
) -> None:
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


def _sync_ctx_to_globals(ctx):
    g = globals()
    g["test_id"] = ctx.test_id
    g["serial_number"] = ctx.serial_number
    g["mac_address"] = ctx.mac_address
    g["board_version"] = ctx.board_version
    g["custom_sn"] = ctx.custom_sn

    g["stop_on_failure"] = ctx.stop_on_failure
    g["update_golden"] = ctx.update_golden
    g["require_golden_match"] = ctx.require_golden_match
    g["debug_print"] = ctx.debug_print
    g["dfd_match_required"] = ctx.dfd_match_required

    g["scan_sn"] = ctx.scan_sn
    g["set_sn"] = ctx.set_sn
    g["sn_leading_digits_to_set_sn"] = ctx.sn_leading_digits_to_set_sn

    g["microcontroller_port"] = ctx.microcontroller_port
    g["baud"] = ctx.baud
    g["microcontroller_timeout"] = ctx.microcontroller_timeout

    g["ip"] = ctx.ip
    g["scan_timeout"] = ctx.scan_timeout
    g["scan_range_start"] = ctx.scan_range_start
    g["scan_range_end"] = ctx.scan_range_end

    g["device"] = ctx.device
    g["node_channels"] = ctx.node_channels

    g["mini_node_test"] = ctx.mini_node_test
    g["els_node_test"] = ctx.els_node_test
    g["usbc_node_test"] = ctx.usbc_node_test
    g["supernode_test"] = ctx.supernode_test
    g["battery_backup_test"] = ctx.battery_backup_test

    g["usbc_current_channel"] = ctx.usbc_current_channel

    g["maxw_save"] = ctx.maxw_save
    g["cccv_save"] = ctx.cccv_save

    g["CC_yaml"] = ctx.CC_yaml
    g["CV_yaml"] = ctx.CV_yaml
    g["CCUV_yaml"] = ctx.CCUV_yaml

    g["general_settings_config"] = ctx.general_settings_config
    g["test_config"] = ctx.test_config

    g["prompt_continue_key"] = ctx.prompt_continue_key
    g["prompt_end_test_key"] = ctx.prompt_end_test_key

    g["test_status"] = ctx.test_status
    g["test_notes"] = ctx.test_notes

    g["csv_arg_file_name"] = ctx.csv_arg_file_name
    g["batch_csv_file"] = ctx.batch_csv_file

def main(argv, arc):
    # global test_id, serial_number, mac_address, board_version

    ctx = TestContext()
    globals()["_CTX"] = ctx  # TEMP handle for helpers during migration

    _sync_ctx_to_globals(ctx)

    # ─────────────────────────────────────────────
    # TEMP SHIMS: expose module-level names, backed by ctx
    # NOTE: Only for transition. We will remove these after refactor.
    # ─────────────────────────────────────────────
    globals().update({
        "test_id": ctx.test_id,
        "serial_number": ctx.serial_number,
        "mac_address": ctx.mac_address,
        "board_version": ctx.board_version,
        "custom_sn": ctx.custom_sn,

        "stop_on_failure": ctx.stop_on_failure,
        "update_golden": ctx.update_golden,
        "require_golden_match": ctx.require_golden_match,
        "debug_print": ctx.debug_print,
        "dfd_match_required": ctx.dfd_match_required,

        "scan_sn": ctx.scan_sn,
        "set_sn": ctx.set_sn,
        "sn_leading_digits_to_set_sn": ctx.sn_leading_digits_to_set_sn,

        "microcontroller_port": ctx.microcontroller_port,
        "baud": ctx.baud,
        "microcontroller_timeout": ctx.microcontroller_timeout,

        "ip": ctx.ip,
        "scan_timeout": ctx.scan_timeout,
        "scan_range_start": ctx.scan_range_start,
        "scan_range_end": ctx.scan_range_end,

        "device": ctx.device,
        "node_channels": ctx.node_channels,

        "mini_node_test": ctx.mini_node_test,
        "els_node_test": ctx.els_node_test,
        "usbc_node_test": ctx.usbc_node_test,
        "supernode_test": ctx.supernode_test,
        "battery_backup_test": ctx.battery_backup_test,

        "usbc_current_channel": ctx.usbc_current_channel,

        "maxw_save": ctx.maxw_save,
        "cccv_save": ctx.cccv_save,

        "CC_yaml": ctx.CC_yaml,
        "CV_yaml": ctx.CV_yaml,
        "CCUV_yaml": ctx.CCUV_yaml,

        "general_settings_config": ctx.general_settings_config,
        "test_config": ctx.test_config,

        "prompt_continue_key": ctx.prompt_continue_key,
        "prompt_end_test_key": ctx.prompt_end_test_key,

        "test_status": ctx.test_status,
        "test_notes": ctx.test_notes,

        "csv_arg_file_name": ctx.csv_arg_file_name,
        "batch_csv_file": ctx.batch_csv_file,
    })
    # _sync_ctx_to_globals(ctx)

    #print(argv, arc)
    if arc > 1:
        if not checkArg(ctx, argv[1]):
            ctx.test_id = argv[1]
            print('test_id',ctx.test_id)
    if arc > 2:
        if not checkArg(ctx, argv[2]):
            ctx.serial_number = argv[2]
            print('serial_number',ctx.serial_number)
    if arc > 3:
        if not checkArg(ctx, argv[3]) and not checkScanSN(ctx, argv[3]):
            ctx.board_version = argv[3]
            print('board_version',ctx.board_version)
    for i in range(4,8):
        if arc > i:
            if not checkArg(ctx, argv[i]) and not checkScanSN(ctx, argv[i]):
                pass
        
    _sync_ctx_to_globals(ctx)

    final_pass = False

    if start():
        # SYNC in case start() loaded or modified globals (settings, test_config, ip)
        _sync_ctx_to_globals(ctx)
        updateState('main','test start','Started','Test started')

        if runTest(ctx) and test_status != 'Fail':
            updateState('main','test end - pass','Completed','Pass')
            final_pass = True
        else:
            updateState('main','test end - fail','Completed','Fail')
    
    stop()
    # SYNC in case runTest() updated SN/MAC/status/notes
    _sync_ctx_to_globals(ctx)

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

