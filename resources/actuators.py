from context import TestContext

from services import load_mach as load_mach
from services import coap_client
from services import controller

# from devices.base import Device

from write import write
from frontend import prompt

from dataclasses import dataclass
import time

@dataclass
class LoadTestResult:
    status: bool
    average_power: float | None
    median_power: float | None
    minimum_power: float | None
    maximum_power: float | None

def dim_update(ctx: TestContext, dim_down_value: int = 90, dim_up_value: int = 100, channel: int = 0, delay: float = 1.0):
    # device = ctx.Device
    set_dim(ctx, channel, dim_down_value)
    time.sleep(delay)
    set_dim(ctx, channel, dim_up_value)

def set_cccv(
    ctx: TestContext,
    actuator_num: int = 0,
    cccv_preset: int | None = None, 
    cc: int | None = None,
    cv: int | None = None
    ) -> bool:

    Device = ctx.Device
    if actuator_num == Device.all_actuators_integer():
        coap_client.putValue(
            ip_address=ctx.ip,
            resource=Device.all_actuators_resource(),
            key=Device.all_actuators_key(),
            value=Device.all_actuators_cccv_command(cccv_preset),
            timeout=Device.post_cccv_setting_delay() # TODO Is this necessary anymore? If so, consider universalizing.
        )
        if not check_actuators(ctx, Device.cccv_resource_key(), cccv_preset, Device.number_of_actuators(), verbose=True):
            return False
    elif cccv_preset is not None:
        coap_client.putValue(
            ip_address = ctx.ip,
            resource = Device.single_actuator_resource(actuator_num),
            key = Device.cccv_resource_key(actuator_num),
            value = str(cccv_preset),
            timeout=Device.post_cccv_setting_delay() # TODO Is this necessary anymore? If so, consider universalizing.
        )
        if not check_actuators(ctx, Device.cccv_resource_key(), cccv_preset, Device.number_of_actuators(), verbose=True):
            return False
    elif cc is not None:
        coap_client.secure_setting(
            ip_address = ctx.ip,
            resource = Device.single_actuator_resource(actuator_num),
            key = Device.current_resource_key(actuator_num),
            value = str(cc)
        )
        if not check_actuators(ctx, Device.current_resource_key(), cc, Device.number_of_actuators(), verbose=True):
            return False
    elif cv is not None:
        coap_client.secure_setting(
            ip_address = ctx.ip,
            resource = Device.single_actuator_resource(actuator_num),
            key = Device.voltage_resource_key(actuator_num),
            value = str(cv)
        )
        if not check_actuators(ctx, Device.voltage_resource_key(), cv, Device.number_of_actuators(), verbose=True):
            return False
        
    ctx.cccv_save = cccv_preset # TODO SEE IF THIS IS NEEDED LATER
    ctx.cc_save = cc            # TODO SEE IF THIS IS NEEDED LATER
    ctx.cv_save = cv            # TODO SEE IF THIS IS NEEDED LATER

    return True

def set_max_watt(
        ctx: TestContext,
        maxw: int | str, 
        actuator_num: int | None = None
    ) -> bool:

    Device = ctx.Device
    # If setting the max watt for all actuators of a device...
    if actuator_num is None or actuator_num == Device.all_actuators_integer(): 
        coap_client.putValue(
            ip_address=ctx.ip,
            resource=Device.all_actuators_resource(),
            key=Device.all_actuators_key(),
            value=Device.all_actuators_maxw_command(maxw)
        )
        actuators_to_check = Device.all_actuators_integer()
    else:
        # If only setting the max watt for a specific actuator...
        coap_client.secure_setting(
            ip_address = ctx.ip,
            resource = Device.single_actuator_resource(actuator_num),
            key = Device.power_resource_key(actuator_num),
            value = str(maxw)
        )
        actuators_to_check = actuator_num
    # TODO Is this necessary anymore? If so, consider removing.
    time.sleep(Device.post_maxw_setting_delay()) 

    if not check_actuators(
        ctx = ctx,  
        key_to_check = Device.power_resource_key(),
        value_expected = maxw,
        actuators_to_check=actuators_to_check,
        verbose = True
        ): 
        return False
    
    ctx.maxw_save = maxw
    return True

def set_dim(ctx: TestContext, channel: int, dim: int) -> bool: # NOTE Doesn't work with '3' as "all_actuators_integer" because that isn't accounted for here or in the device class file.
    """Sets dim on a given channel, if channel value passed in matches the Device's 
    \n'all_actuators_integer', then it can account for this as well."""
    Device = ctx.Device
    if channel == Device.all_actuators_integer():
        resource = Device.all_actuators_resource()
        key = Device.all_actuators_key()
        value = Device.all_actuators_dim_command(dim)
        print("Setting",key,"of",resource,"to",value) 
        coap_client.putValue(ctx.ip, resource=resource, key=key, value=value)
        # time.sleep(1.0)
        passed: bool = True
        for ch in range(Device.first_actuator(), Device.number_of_actuators()):
            dim_found = get_dim(ctx, ch)
            if dim_found != dim:
                # print("\033[1;93mWarning: Bold Yellow Text!\033[0m")
                print(f"\033[93mFailed to set dim {dim} on channel {ch}. Found dim {dim_found}.\033[0m")
                # print(f"Failed to set dim {dim} on channel {ch}. Found dim {dim_found}.")
                passed = False
        return passed
    else: return coap_client.secure_setting(ctx.ip, resource=Device.single_actuator_resource(), key=Device.dim_resource_key(), value=str(dim))

def get_dim(ctx: TestContext, channel: int) -> bool:
    return coap_client.getValue(ctx.ip, resource=ctx.Device.single_actuator_resource(channel), key=ctx.Device.dim_resource_key())

def check_actuators_dim(ctx: TestContext, actuators_to_check: int | list[int], expected_dim: int, verbose: bool = False) -> bool:
    return check_actuators(ctx = ctx, key_to_check=ctx.Device.dim_resource_key(), value_expected=expected_dim, actuators_to_check=actuators_to_check, verbose=verbose)

def check_actuators( # TODO THIS FUNCTION DOESN'T WORK FOR ANY RESOURCE THAT ISN'T SET BY A STRING, SUCH AS DIM. FIX THIS ASAP
        ctx: TestContext, 
        key_to_check: str, 
        value_expected: str | int, 
        actuators_to_check: int | list[int], 
        verbose: bool = False
        ) -> bool:
    
    Device = ctx.Device
    passed: bool = True

    if isinstance(actuators_to_check, int):
        if actuators_to_check == Device.all_actuators_integer():
            actuators_to_check = list(range(Device.first_actuator(), Device.number_of_actuators()+1))
        else:
            actuators_to_check = [actuators_to_check]
    # print("Checking actuators:",actuators_to_check,"for",key_to_check,"=",value_expected)
    for actuator in actuators_to_check:
        val = coap_client.getValue(ctx.ip, Device.single_actuator_resource(actuator), key_to_check, 8.0)
        try: # This try except is a failsafe to ensure the type set for the resource value matches what is actually expected by the device
            typed_val = type(value_expected)(val)
        except (ValueError, TypeError):
            typed_val = val  # fallback if casting fails
        if typed_val != value_expected:
            if verbose: write.updateLog(key_to_check, f'actuator{actuator} value is {val}; Expected {value_expected}')
            passed = False
    # ctx.maxw_save = maxw # NOTE Preserve just in case
    return passed   