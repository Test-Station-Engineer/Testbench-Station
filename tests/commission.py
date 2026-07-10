from context import TestContext
from resources import actuators
from services import coap_client
import time

def run(ctx: TestContext, commission_settings) -> bool:
    """Commission settings to a device. Settings are set in the YAML test configuration file."""

    print(f"\033[94mCommissioning Device\033[0m")

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
            print(f"Applying settings to all {ctx.Device.number_of_actuators()} {resource_type} channels:")
            for k, v in kv_pairs.items():
                print(f"  {k}: {v}")
            cccv_was_set: bool = False
            for channel in range(1,ctx.Device.number_of_actuators()+1):
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
                    if key == 'cccv':
                        if not cccv_was_set:
                            if not actuators.set_cccv(ctx=ctx, actuator_num=ctx.Device.all_actuators_integer(), cccv_preset=value):
                                print(f"Failed to apply CV {value} setting.")
                                success = False
                            else: 
                                cccv_was_set = True
                                print(f"Waiting a few seconds after setting CCCV {value}.") # Switch this to a timeout preferably.
                                time.sleep(5.0)  # Allow time for CCCV to take effect    
                    elif not coap_client.secure_setting(ctx.ip, resource_channel, key, value, checkVerbose, timeout = 5.0):
                        print(f"Failed to apply {key}={value} on {resource_channel}")
                        success = False
                    
                # if device_name.lower() == 'supernode' or device_name.lower() == 'ccuv':
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
    
    print(f"\033[94mCommissioning complete. Writing to EEPROM...\033[0m")
    return success