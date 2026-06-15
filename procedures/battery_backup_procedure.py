from dataclasses import dataclass
# from abc import ABC, abstractmethod

import time

from typing import override

# from context import TestContext
from context import TestContext
from services import coap_client

from resources import actuators

from write import write

from procedures.test_procedure import TestProcedure

from tests.load_test import test_single_load
from frontend import prompt

@dataclass
class BatteryBackupProcedure(TestProcedure):

    @override
    def init(ctx: TestContext):
        pass

    @override
    def before_load_sequence(self, ctx, test_loads: list[dict]): pass
    
    @override
    def before_load_relays(self, ctx, test_load: dict): 
        """Executed before the load sequence begins. 
        \nCan be used for any setup that needs to happen before loading, 
        \nsuch as setting mux channels or initializing devices."""
        
        # Procedure Specific Settings for Device Being Tested #
        self.Device = ctx.Device     # This will be set to the device being tested when the procedure is initialized in test.py. This allows the procedure to access device-specific methods and properties, such as actuator resources and keys, which is necessary for generalizing the load testing steps across different devices.
        Device = self.Device
        # MAXW
        if 'maxw' in test_load:
            if test_load['maxw'] != ctx.maxw_save:
                maxw = test_load['maxw']
                print("Setting max watt to",maxw,"on both channels")
                if actuators.set_max_watt(ctx, test_load['maxw'], Device.all_actuators_integer()):
                    write.updateLog('testMAXW','pass',test_load['maxw'])

        # CCCV
        if 'cccv' in test_load:
            if test_load['cccv'] != ctx.cccv_save:
                if actuators.set_cccv(ctx=ctx, 
                                      actuator_num=Device.all_actuators_integer(), 
                                      cccv_preset=test_load['cccv']):
                    write.updateLog('set_cccv','pass',test_load['cccv'])
                    ctx.cccv_save = test_load['cccv']
        
        # CUV TODO Generalize for n actuators and use actuators.check_actuators() instead
        if 'cuv' in test_load:
            if test_load['cuv'] != ctx.cuv_save:
                if coap_client.secure_setting(ctx.ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ctx.ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                    write.updateLog('testCUV','pass',test_load['cuv'])
        
        dim: int = 100
        if 'dim' in test_load: dim = test_load['dim']   
        actuators.dim_update(
            ctx=ctx,
            dim_down_value=10,
            dim_up_value=dim,
            channel=Device.all_actuators_integer(),
            delay=1.25
        )
    
    def before_load_output_on(self, ctx, test_load, step): pass
    def before_load_output_off(self, ctx, test_load, step): pass
    def after_load_sequence(self, ctx, test_load, step): pass

    def before_sensor_test(self, ctx): pass
    def after_sensor_test(self, ctx): pass

    def before_pdline_test(self, ctx): pass
    def after_pdline_test(self, ctx): pass

    def custom_loads_test(self, ctx, test_loads: list[dict]): 

        def test_battery_load(ctx: TestContext, upper_load, lower_load, wait_time) -> bool:
            if not actuators.set_cccv(ctx=ctx, actuator_num=0, cccv_preset=10): 
                return False
            # actuators.set_dim(ctx,0,dim=90)  # NOTE Commented out 4/13/2026
            # time.sleep(1)                    # NOTE Commented out 4/13/2026
            # actuators.set_dim(ctx,0,dim=100) # NOTE Commented out 4/13/2026

            time.sleep(wait_time) # TODO Check if needed next time

            if not test_single_load(ctx, upper_load): 
                return False

            if not actuators.set_cccv(ctx=ctx, actuator_num=0, cccv_preset=10): 
                return False

            print("Doing a DIM UPDATE") # Added 4/13/2026 for checking dim resource/key pairs
            actuators.dim_update(ctx,channel=0,dim_down_value=90,dim_up_value=100,delay=1.0)
            
            # write.send_test_prompt(key,f"Press and hold switch test button. Then press {key} on keyboard when ready.", "Keep button held.")
            if prompt.prompt("Switch Test Button", "Press and hold switch test button for this next test. Select 'Okay' to continue or 'Cancel' to end test."): 
                print("Keep button held")
            else: 
                return False

            # time.sleep(wait_time) # NOTE Commented out 4/13/2026 to try to use time_before_load_on instead
            if not test_single_load(ctx, lower_load): 
                return False
            print("Release button")
            time.sleep(5.0)
            actuators.set_dim(ctx,channel=0,dim=100)
            if not test_single_load(ctx, upper_load): 
                return False
            

            # TESTING FEATURE
            
            if not actuators.set_cccv(ctx=ctx, actuator_num=0, cccv_preset=255): # Replaced cv 0
                return False
            actuators.set_dim(ctx,channel=0,dim=0)

            print("Dim:",coap_client.getDim(ctx.ip,1),coap_client.getDim(ctx.ip,2),"; CCCV:", coap_client.getCCCV(ctx.ip,1),coap_client.getCCCV(ctx.ip,2))
            time.sleep(wait_time*2)

            #write.send_test_prompt(key, f"Unplug Channel 1, then press {key}","Testing Power Loss Backup")
            #time.sleep(wait_time)

            if not test_single_load(ctx, lower_load): 
                return False
            
            #write.send_test_prompt(key, f"Plug in Channel 1, then press {key}","Testing Normal High Load")
            #time.sleep(wait_time)

            if not actuators.set_cccv(ctx=ctx, actuator_num=0, cccv_preset=10):
                return False
            # if not actuators.set_max_watt(ctx, ctx.test_config['maxw'], actuator_num=0): # NOTE Is this even necessary anymore?
            #     return False
            # coap_client.setDim(ctx.ip,0,100)
            if not test_single_load(ctx, upper_load): 
                return False

            print("Remember to unplug pink battery backup connectors when finished testing.")
            return True
        
        def test_battery_backup(ctx: TestContext, batt_test_loads) -> bool:
            for load in batt_test_loads:
                name = load.get('Name','').lower()
                if 'low' in name:
                    low_load = load
                elif 'high' in name:
                    high_load = load
                else: print(f"\033[3;91mNo High or Low Load found in {load}\033[0m")

            if "await_time" in ctx.test_config: 
                batt_wait_time = ctx.test_config["await_time"]
            else: batt_wait_time = 2

            if not test_battery_load(ctx, high_load, low_load, batt_wait_time):
                return False
            return True
    
        if not test_battery_backup(ctx, test_loads): return False
        return True
    
    