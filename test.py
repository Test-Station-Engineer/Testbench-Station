# test.py
from context import TestContext
import cli
from write import write

import services.controller as controller
import services.coap_client as coap_client
import services.load_mach as load_mach
import services.coap_client_scan as coap_client_scan

# import services.rs485_old as rs485_old
import services.rs485_module as rs485_module

# import dev.defunct.database as database

from resources import network, actuators

from tests import trigger_test, load_test, sensor_test, wall_switch_test, commission

from devices import functions_mini as mnode

import frontend.prompt as prompt

import time
import sys
import subprocess
import os
import csv
import random
from itertools import count
from pickletools import int4

sys.stdout.reconfigure(line_buffering=True)

def fail_test(ctx: TestContext, message: str) -> False:
    write.updateLog('testResult','fail',message)
    print(f"\033[91mTEST FAILED: {message}\033[0m")
    return False

def testCodeVersion(ctx: TestContext, code_version: str) -> bool:

    dfu = coap_client.getDFUVersion(ctx.ip)
    golden = coap_client.getGoldenVersion(ctx.ip)
    dfd = coap_client.getDFDVersion(ctx.ip)

    if dfu != code_version:
        write.updateLog('testCodeVersion','fail dfu',dfu,'expected',code_version)
        return False
    
    if golden != code_version:
        write.updateLog('testCodeVersion','fail golden',golden)
        if ctx.update_golden:
            write.updateLog('testCodeVersion','update golden')
            coap_client.putValue(ctx.ip,'/dfu','updt',0) # NOTE No longer used
            elapsed = 0
            while elapsed < 100:
                time.sleep(1.0)
                elapsed += 1
                print('\r waiting for reboot: ',str(elapsed),end='')
            golden = coap_client.getGoldenVersion(ctx.ip)
            if ctx.require_golden_match == True:
                if  golden != code_version:
                    write.updateLog('testCodeVersion','fail golden',golden)
                    return False
        elif ctx.require_golden_match == True:
            return False
    
    if dfd != code_version:
        write.updateLog('testCodeVersion','fail dfd',dfd)
        if ctx.dfd_match_required:
            return False
    else: print("DFD Version Correctly Matches DFU.")
    return True


def testSerialNumber(ctx: TestContext, sn: str) -> bool:
    """
    Context-based version of testSerialNumber. Behavior unchanged.
    """

    if ctx.mini_node_test:
        mnode.serial_number_test(sn)  # sn had serial_number before for some reason
    if ctx.set_sn or not ctx.scan_sn:
        coap_client.setSN(ctx.ip, str(sn))
        get_sn = coap_client.getSN(ctx.ip)
        if get_sn != str(sn):
            write.updateLog('testSerialNumber', 'fail get', get_sn)
            return False
        if ctx.set_sn:
            print("Serial number set to", get_sn)
    return True

def testBoardVersion(ctx: TestContext, bv: str) -> bool:
    """
    Context-based version of testBoardVersion. Behavior unchanged.
    """

    if ctx.mini_node_test:
        if not mnode.get_board_version(ctx.ip):
            return False
    elif ctx.battery_backup_test:
        # legacy forced value for battery backup NOTE THIS SUCKS
        ctx.board_version = 'BB-R2.2'
    else:
        get_bv = coap_client.getBoardVersion(ctx.ip)
        if get_bv != str(bv):
            write.updateLog('testBoardVersion', 'fail get', get_bv)
            return False
    return True

def testCMD(ctx: TestContext, cmds) -> bool:
    for cmd in cmds:
        if not coap_client.secure_setting(ctx.ip,'/network','cmd',str(cmd), True):
            # print(f"Failed to set cmd {cmd}")
            return False
    return True

# def testRS485(ctx):
#     rs485.main()
#     if prompt.prompt("RS485 Testing", "Check the console to see if RS485 communication was successful. Did it pass?"):
#         return True
#     else: return False

def runTest(ctx): #TODO No return type specified

    cfg = ctx.test_config
    Device = ctx.Device

    #
    # ─────────────────────────────────────────────
    # 1. Code Version Test
    # ─────────────────────────────────────────────
    if 'code_version' in cfg:
        if testCodeVersion(ctx, cfg['code_version']):
            write.updateState('runTest','pass - code_version','Pass','code_version')
        else:
            write.updateState('runTest','fail - code_version','Fail','code_version')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
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
            if trigger_test.run(ctx, attempts, wait_sec):
                write.updateState('runTest', 'pass - trigger1', 'Pass', 'trigger1')
            else:
                write.updateState('runTest', 'fail - trigger1', 'Fail', 'trigger1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False

    #
    # ─────────────────────────────────────────────
    # 3. Update DB flag (unchanged behavior)
    # ─────────────────────────────────────────────
    if cfg.get('update_db'):
        coap_client.putValue(ctx.ip, '/network', 'cmd', 'update_db')
        time.sleep(ctx.Device.update_db_wait_time())  # Wait for DB update to complete
    
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
        write.updateLog('SN:', sn, 'MAC:', ctx.mac_address)
    else:
        # Battery Backup test uses a special SN provided earlier
        ctx.mac_address = 'N/A'
    
    #
    # ─────────────────────────────────────────────
    # 5. Device-specific initialization
    # ─────────────────────────────────────────────
    # TODO JUST MIGRATE THESE TO PROCEDURE INITS FFS
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
    else:
        if not ctx.mini_node_test:
            coap_client.putValue(ctx.ip,'/network','cmd','set_ws 0')
            coap_client.putValue(ctx.ip,'/network','cmd','set_max_amp 3 2500')

    '''elif ctx.supernode_test:
        ctx.node_channels = 8
        print("Initializing supernode test")
        snode.init(ctx.ip, cfg)

        
        # igain setup logic
        igain_var = 'cv_igain10'
        if ctx.device_name in ('Supernode CC', 'Supernode'):
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
            coap_client.putValue(ctx.ip,'/sensors/input'+str(i),'eventhl','default') # change sensor 1 events supernode version'''
        
    # ─────────────────────────────────────────────
    # 6. Subnet Validation
    # ─────────────────────────────────────────────
    if 'subnet' in cfg:
        if network.testSubnet(ctx, cfg['subnet']):
            write.updateState('runTest','pass - subnet','Pass','subnet')
        else:
            write.updateState('runTest','fail - subnet','Fail','subnet')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 7. Serial Number Test
    # ─────────────────────────────────────────────
    if ctx.serial_number not in ('', '0'):
        if testSerialNumber(ctx,ctx.serial_number):
            write.updateState('runTest','pass - serial_number','Pass','serial_number')
        else:
            write.updateState('runTest','fail - serial_number','Fail','serial_number')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 8. Board Version Test
    # ─────────────────────────────────────────────
    if ctx.board_version and not ctx.supernode_test:
        if testBoardVersion(ctx,ctx.board_version):
            write.updateState('runTest','pass - board_version','Pass', f'board_version:{ctx.board_version}')
        else:
            write.updateState('runTest','fail - board_version','Fail', f'board_version:{ctx.board_version}')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # 9. CCCV Test
    # ─────────────────────────────────────────────
    if 'cccv' in cfg:
        if actuators.set_cccv(ctx=ctx, actuator_num=Device.all_actuators_integer(), cccv_preset=cfg['cccv']):
            write.updateState('runTest','pass - cccv','Pass','cccv')
        else:
            write.updateState('runTest','fail - cccv','Fail','cccv')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    

    # ─────────────────────────────────────────────
    # 10. MAXW Test
    # ─────────────────────────────────────────────
    if 'maxw' in cfg:
        if actuators.set_max_watt(ctx=ctx, maxw=cfg['maxw'], actuator_num=Device.all_actuators_integer()):
            write.updateState('runTest','pass - maxw','Pass','maxw')
        else:
            write.updateState('runTest','fail - maxw','Fail','maxw')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False
    
    #
    # ─────────────────────────────────────────────
    # 11. Single Load Test
    # ─────────────────────────────────────────────
    if 'load' in cfg:
        load_cfg = cfg['load']
        if write.check_toggle(load_cfg):
            print("Starting Load Test")
            if load_test.test_single_load(ctx, load_cfg):
                write.updateState('runTest','pass - load','Pass','load')
            else:
                write.updateState('runTest','fail - load','Fail','load')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOAD TEST TOGGLE IS SET TO OFF (0). SKIPPING LOAD TEST.")
            write.updateState('runTest','skip - load','Skip','load')
    
    #
    # ─────────────────────────────────────────────
    # 12. Multi-step Load Tests
    # ─────────────────────────────────────────────
    if 'loads' in cfg:
        loads_cfg = cfg['loads']
        if write.check_toggle(loads_cfg):
            print("Starting Loads Test")
            if load_test.test_loads(ctx, loads_cfg):
                write.updateState('runTest','pass - loads','Pass','loads')
            else:
                write.updateState('runTest','fail - loads','Fail','loads')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print("LOADS TEST TOGGLE IS SET TO OFF (0). SKIPPING LOADS TEST.")
            write.updateState('runTest','skip - loads','Skip','loads')
    
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

    # 
    # ─────────────────────────────────────────────
    # 14. Sensor 1 Test
    # ─────────────────────────────────────────────
    if 'sensor1' in cfg:
        val = cfg['sensor1']
        if val in (1, True):
            if sensor_test.run(ctx):
                write.updateState('runTest','pass - sensor1','Pass','sensor1')
            else:
                write.updateState('runTest','fail - sensor1','Fail','sensor1')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        elif val in (0, False):
            print(f"SENSOR1 TEST TOGGLE IS SET TO OFF {val}. SKIPPING SENSOR1 TEST.")
        else:
            print(f"SENSOR1 TEST TOGGLE INVALID: {val}. SKIPPING.")
    
    #
    # ─────────────────────────────────────────────
    # 15. PDLine Test
    # ─────────────────────────────────────────────
    if 'pdline' in cfg:
        v = cfg['pdline']
        if v in (1, True):
            if wall_switch_test.run(ctx):
                write.updateState('runTest','pass - pdline','Pass','pdline')
            else:
                write.updateState('runTest','fail - pdline','Fail','pdline')
                ctx.test_status = 'Fail'
                if ctx.stop_on_failure:
                    return False
        else:
            print(f"PDLINE TEST TOGGLE IS SET TO OFF {v}. SKIPPING PDLINE TEST.")

    #
    # ─────────────────────────────────────────────
    # 16. Battery Backup Loads Test
    # ─────────────────────────────────────────────
    # if 'battery_backup_loads' in cfg:
    #     ctx.battery_backup_test = True
    #     ctx.mac_address = ''
    #     if testBatteryBackup(ctx, cfg["battery_backup_loads"]):
    #         print('pass','battbackup')
    #         write.updateState('runTest','pass - battbackup','Pass','battbackup')
    #     else:
    #         write.updateState('runTest','fail - battbackup','Fail','battbackup')
    #         ctx.test_status = 'Fail'
    #         if ctx.stop_on_failure:
    #             return False
    
    #
    # ─────────────────────────────────────────────
    # 17. Mini Node Firmware Upgrade
    # ─────────────────────────────────────────────
    if ctx.mini_node_test and cfg.get('firmware_upgrade'):
        print("Starting firmware upgrade...")
        mnode.firmware_upgrade_test()
    
    #
    # ─────────────────────────────────────────────
    # 18. Supernode DC-IN Test
    # ─────────────────────────────────────────────
    if Device.has_dc_in:
        if cfg.get('dc_in') in (1, True):
            print("Starting DC IN Test")
            try:
                Device.procedure().dc_in_test(
                    ctx, 
                    test_loads=ctx.test_config.get('loads').get('steps')
                    or ctx.test_config.get('load'))
            except Exception as e:
                import traceback
                print("Error during DC IN test:", e)
                traceback.print_exc()
                ctx.test_status = 'Fail'
                write.updateState('runTest','fail - dc in','Fail','dc in')
                if ctx.stop_on_failure:
                    return False  
    
    #
    # ─────────────────────────────────────────────
    # 19. Commissioning
    # ─────────────────────────────────────────────
    if 'commission' in cfg:
        commission_settings = cfg['commission']
        if write.check_toggle(commission_settings):
            print("Commissioning Node")
            if commission.run(ctx, commission_settings):
                write.updateState('runtest','pass - commission','Pass','commission')
            else:
                ctx.test_status = 'Fail'
                write.updateState('runtest','fail - commission','Fail','commission')
                if ctx.stop_on_failure:
                    return False
        else:
            print("Commission settings missing or toggled off.")
    
    #
    # ─────────────────────────────────────────────
    # 20. CMD list execution
    # ─────────────────────────────────────────────
    if 'cmd' in cfg:
        if testCMD(ctx, cfg['cmd']):
            write.updateState('runTest','pass - cmd','Pass','cmd')
        else:
            write.updateState('runTest','fail - cmd','Fail','cmd')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # 21. RS485 test
    # ─────────────────────────────────────────────
    if 'rs485' in cfg and cfg['rs485'] in (1, True):
        if rs485_module.main():
        # if rs485.main():
            write.updateState('runTest','pass - rs485','Pass','rs485')
        else:
            write.updateState('runTest','fail - rs485','Fail','rs485')
            ctx.test_status = 'Fail'
            if ctx.stop_on_failure:
                return False

    #
    # ─────────────────────────────────────────────
    # Final return
    # ─────────────────────────────────────────────
    return ctx.test_status != 'Fail'


def start(ctx: TestContext) -> bool:
    # if not database.connect(): NOTE DATABASE REMOVED
    #     updateState('start','failed - cannot connect to database','Failed','Cannot connect to database')
    #     return False
    
    if ctx is None:
        print("Internal error: _CTX missing")
        return False

    if not cli.parse_general_settings(ctx):
        write.updateState('start','failed - cannot load general_settings.yaml','Failed','Cannot parse settings')
        return False
    if not cli.init_test_config(ctx):
        write.updateState('start','failed - cannot load test yaml','Failed','Cannot load test yaml')
        return False
    if not controller.open(ctx.microcontroller_port,ctx.baud,ctx.microcontroller_timeout):
    #if not controller.open_device("ARDUINO_NANO"): # Feature for future
        write.updateState('start','failed - cannot open controller port','Failed','Cannot open controller port')
        return False
    controller.print_rx = ctx.debug_print # debug
    controller.startRXThread() # Check to see if this is causing console bloat - Drew
    
    if not network.get_ip(ctx):
        write.updateState('start','failed - cannot get node ip','Failed','Cannot get node ip')
        return False
    if not load_mach.open() and 'load' in ctx.test_config:
        write.updateState('start','failed - cannot open electronic load','Failed','Cannot open electronic load')
        return False

    return True

def stop():
    controller.close()
    load_mach.close()

def write_to_csv(
    csv_file_name: str,
    sn_to_csv=None,
    mac_to_csv=None,
    test_status: str = "Pass",
    device_name: str = "",
    board_version: str = "",
    extra_columns: list | None = None
) -> None:

    folder_path = "records"
    os.makedirs(folder_path, exist_ok=True)

    csv_file_path = os.path.join(folder_path, csv_file_name)

    base_fields = ['Device', 'Rev', 'Serial Number', 'MAC Address', 'Status', 'Date']
    extra_columns = extra_columns or []
    extra_fields = [f'Extra{i+1}' for i in range(len(extra_columns))]
    required_fields = base_fields + extra_fields

    rows = []
    existing_fields = []

    # Read existing file if present
    if os.path.isfile(csv_file_path):
        with open(csv_file_path, newline="") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or base_fields
            rows = list(reader)

    # Expand header if needed
    for field in required_fields:
        if field not in existing_fields:
            existing_fields.append(field)

    if not existing_fields:
        existing_fields = required_fields

    # Duplicate detection
    for row in rows:
        row_sn = row.get("Serial Number")
        row_mac = row.get("MAC Address", "").lower()
        row_rev = row.get("Rev")

        # Check Serial Number + Rev
        if sn_to_csv and row_sn == sn_to_csv and row_rev == board_version:
            print(f"\033[3;91mSERIAL NUMBER + REV ALREADY IN {csv_file_name}.\033[0m")
            return

        # Check MAC + Rev
        if mac_to_csv and mac_to_csv != "N/A":
            if row_mac == mac_to_csv.lower() and row_rev == board_version:
                print(f"\033[3;91mMAC ADDRESS + REV ALREADY IN {csv_file_name}.\033[0m")
                return

    # Create new row
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    new_row = {
        "Device": device_name,
        "Rev": board_version,
        "Serial Number": sn_to_csv,
        "MAC Address": mac_to_csv.upper() if mac_to_csv else "",
        "Status": test_status,
        "Date": current_time,
    }

    for i, val in enumerate(extra_columns):
        new_row[f'Extra{i+1}'] = val

    rows.append(new_row)

    # Normalize rows so every row matches the header
    clean_rows = []
    for r in rows:
        new_r = {field: r.get(field, "") for field in existing_fields}
        clean_rows.append(new_r)

    rows = clean_rows

    # Write file
    with open(csv_file_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=existing_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(sn_to_csv, "has been written to", csv_file_name)

###################

def main(argv, arc):

    ctx = TestContext()

    #print(argv, arc)
    if arc > 1:
        if not cli.checkArg(ctx, argv[1]):
            ctx.test_id = argv[1]
            print('test_id',ctx.test_id)
    if arc > 2:
        if not cli.checkArg(ctx, argv[2]):
            ctx.serial_number = argv[2]
            print('serial_number',ctx.serial_number)
    if arc > 3:
        if not cli.checkArg(ctx, argv[3]) and not cli.checkScanSN(ctx, argv[3]):
            ctx.board_version = argv[3]
            print('board_version',ctx.board_version)
    for i in range(4,8):
        if arc > i:
            if not cli.checkArg(ctx, argv[i]) and not cli.checkScanSN(ctx, argv[i]):
                pass

    final_pass = False

    # if start():
    if start(ctx):
        # SYNC in case start() loaded or modified globals (settings, test_config, ip)
        write.updateState('main','test start','Started','Test started')

        if runTest(ctx) and ctx.test_status != 'Fail':
            write.updateState('main','test end - pass','Completed','Pass')
            final_pass = True
        else:
            write.updateState('main','test end - fail','Completed','Fail')
    
    stop()
    # SYNC in case runTest() updated SN/MAC/status/notes

    t = time.localtime()
    date_csv_file = f"{t.tm_year % 100}_{t.tm_mon}_{t.tm_mday}.csv"
    csv_list = [
        f"fpy_{ctx.Device.name()}_{t.tm_year}.csv",
        f"fpy_{t.tm_year}.csv",
        ctx.batch_csv_file,
        date_csv_file
    ]

    if final_pass:
        print('\nfinal - pass')

    else:
        print("\033[3;91mfinal - fail\033[0m")
        # print('\nfinal - fail')
        csv_list = [
            f"fpy_{ctx.device_name}_{t.tm_year}.csv",
            f"fpy_{t.tm_year}.csv"
    ]

    if ctx.csv_arg_file_name != None: 
        # Set serial number to the battery backup serial number for writing to csv
        if ctx.battery_backup_test:
            ctx.serial_number = ctx.custom_sn 
            print("Battery Backup Serial Number:",ctx.serial_number)
            # mac_address = 'N/A'


        csvs_to_write_to = prompt.multi_selection_prompt(
            title="Add Device to CSVs",
            message="Select which CSV files this device should be added to:",
            selections=csv_list
            )
        
        for csv_file in csvs_to_write_to:
            if csv_file == ctx.batch_csv_file or csv_file == date_csv_file: 
                write_to_csv(
                    csv_file_name = csv_file,
                    device_name = ctx.Device.name(),
                    board_version = ctx.board_version,
                    sn_to_csv = ctx.serial_number, 
                    mac_to_csv = ctx.mac_address, 
                    test_status = ctx.test_status,
                    extra_columns = ctx.test_notes)
            else: 
                #print(test_notes)
                write_to_csv( 
                    csv_file_name = csv_file,
                    device_name = ctx.Device.name(),
                    board_version = ctx.board_version,
                    sn_to_csv = ctx.serial_number, 
                    mac_to_csv = ctx.mac_address, 
                    test_status = ctx.test_status,
                    extra_columns = ctx.test_notes) # TODO THESE ARE BOTH THE SAME AT THE MOMENT, IMPLEMENT LOGIC TO DIFFERENTIATE LATER
    else: print("ARGUMENT 'nocsv' WAS SET, NOT WRITING TO ANY CSV.")
    print('done')

if __name__ == '__main__':
    main(sys.argv, len(sys.argv))
