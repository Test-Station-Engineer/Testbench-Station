from context import TestContext
import os
import yaml

import services.load_mach as load_mach
from write import write

from devices.classic_CC import CC_2out
from devices.classic_CV import CV_2out
from devices.classic_CCUV import CCUV_2out
from devices.classic_USBC import USBC_2out
from devices.smart_desk import SmartDesk

from devices.core_node import CoreNode
from devices.els_node import ELSNode
from devices.super_node import SuperNode
from devices.battery_backup import BatteryBackup

def load_yaml(file_path):
    """Load a YAML file safely, updating logs if successful."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return None

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
            write.updateLog(data) # TODO Implement this in the function that calls load_yaml so I don't have to import log here
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
                load_mach.res_els.append(f'ASRL{com_port_int}::INSTR')
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

def init_test_config(ctx: TestContext) -> bool:
    """
    Decide which test YAML to load based on ctx flags, set ctx.device_name,
    and populate ctx.test_config. Returns True/False.
    """

    folder_path = "config"
    # print(f"\033[93mDevice is {ctx.Device}\033[0m")
    file_name = os.path.join(folder_path, ctx.Device.test_config_filename())

    # Load YAML
    data = load_yaml(file_name)
    ctx.test_config = data or {}
    
    if data is not None:
        return True
    else:
        print("test config not loaded. Please troubleshoot.")
        return False
    
def checkArg(ctx, arg) -> bool:
    return (
        checkSkipDB(ctx, arg) or
        checkVerbose(ctx, arg) or
        checkDevice(ctx, arg) or
        checkSetSerialNumber(ctx, arg) or
        checkCSV(ctx, arg)
    )

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
        # database.skip_db = True
        print('skip_db')
        return True
    return False


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

def checkDevice(ctx: TestContext, arg: str) -> bool:
    # If Node 90 is an argument #
    if arg in ('cc', 'cv', 'ccuv', 'cccv','usbc'):
        if arg.lower() == 'cc':
            Device = ctx.Device = CC_2out()
            ctx.Procedure = ctx.Device.procedure()
            # Device.name(optional_set_name_to_arg="CC-0-10") # NOTE Remember this exists if you want to use it.
            ctx.CC_2out_test = True
            print('CC_2out_test')
            return True
        elif arg.lower() == 'cv':
            Device = ctx.Device = CV_2out()
            ctx.Procedure = ctx.Device.procedure()
            ctx.CV_2out_test = True
            print('CV_2out_test')
            return True
        elif arg.lower() == 'ccuv' or arg.lower() == 'cccv':
            Device = ctx.Device = CCUV_2out()
            ctx.Procedure = ctx.Device.procedure()
            ctx.CCUV_2out_test = True
            print('CCUV_2out_test')
            return True
        elif arg.lower() == 'usbc':
            Device = ctx.Device = USBC_2out()
            ctx.Procedure = ctx.Device.procedure()
            ctx.usbc_node_test = True
            print('USBC_2out_test')
            return True
    
    elif arg in ('smart', 'smart_desk', 'smartdesk'):
        ctx.Device = SmartDesk()
        ctx.smart_desk_test = True # NOTE Holdover from when I used device bools instead of classes. This can probably be removed soon, but just in case I have any steps that check this instead of the device class, I'll keep it for now.
        return True
    # If Core Node is an argument # 
    elif arg in ('mini_node', 'mini', 'mnode', 'core_node', 'core', 'cnode'):
        ctx.Device = CoreNode()
        ctx.mini_node_test = True # NOTE Holdover from when I used device bools instead of classes. This can probably be removed soon, but just in case I have any steps that check this instead of the device class, I'll keep it for now.
        ctx.Device.name("Core Node")
        return True
    
    # If Supernode is an argument #
    elif arg.startswith('super'):
        ctx.Device = SuperNode()
        ctx.supernode_test = True # NOTE Holdover from when I used device bools instead of classes. This can probably be removed soon, but just in case I have any steps that check this instead of the device class, I'll keep it for now.
        if arg == 'supercv': ctx.device_name = 'Supernode CV'
        elif arg == 'supercc': ctx.device_name = 'Supernode CC'
        else: ctx.device_name = 'Supernode'
        return True
    
    # If ELS-Node is an argument #
    elif arg in ('els', 'ELS'):
        ctx.Device = ELSNode()
        ctx.els_node_test = True # NOTE Holdover from when I used device bools instead of classes. This can probably be removed soon, but just in case I have any steps that check this instead of the device class, I'll keep it for now.
        ctx.device_name = 'ELS-Node'
        return True
    
    # If battery backup is an argument #
    elif arg.startswith('BB'):
        ctx.Device = BatteryBackup()
        ctx.battery_backup_test = True # NOTE Holdover from when I used device bools instead of classes. This can probably be removed soon, but just in case I have any steps that check this instead of the device class, I'll keep it for now.
        ctx.custom_sn = arg
        ctx.device_name = 'Battery-Backup'
        print("Recorded Serial Number will be: ", ctx.custom_sn)
        return True
    return False 

def checkCSV(ctx, arg) -> bool:
    if 'csv' in arg.lower():
        name = str(arg).lower().replace('.', '').replace('csv', '')
        ctx.csv_arg_file_name = None if name == 'no' else f"{name}.csv"
        return True
    return False