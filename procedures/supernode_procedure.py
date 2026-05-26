from dataclasses import dataclass
# from abc import ABC, abstractmethod
import time

from typing import override

from context import TestContext

from services import coap_client
from services import mux

from devices.base import Device

from resources import actuators

from write import write
from frontend import prompt

from procedures.test_procedure import TestProcedure

@dataclass
class SuperNodeProcedure(TestProcedure):

    @override
    def init(ctx: TestContext):
        coap_client.set_lldp(ctx.ip,False)
        for i in range(1,9): coap_client.secure_setting(ctx.ip,f'/actuators/actuator{i}','fadetime',0)

    ######################################################################
    @override
    def before_load_sequence(self, ctx, test_loads): 
        dim_setting: int = test_loads.get('dim', 100)
        ctx.dim_expected = dim_setting
        # dim: int = getattr(test_load, "get", lambda *_: 100)('dim', 100)
        for i in range(1,9):
            coap_client.secure_setting(ctx.ip,f'/sensors/input{i}','sentype','INPUT_LH_OR_HL',verbose=True) # Change sensor 1 events supernode version
            coap_client.secure_setting(ctx.ip,f'/sensors/input{i}','eventlh',f"F0,{i},{dim_setting}",verbose=True) # Change sensor 1 events supernode version
            coap_client.secure_setting(ctx.ip,f'/sensors/input{i}','eventhl',f"F0,{i},0",verbose=True) # Change sensor 1 events supernode version

    @override
    def set_relays(self,channel):
        mux.set(channel)
    
    @override
    def before_load_relays(self, ctx: TestContext, test_load: dict): 
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
        
        # dim_setting: int = 100
        # if 'dim' in test_load: dim_setting = test_load['dim']   
        # actuators.dim_update(
        #     ctx=ctx,
        #     dim_down_value=10,
        #     dim_up_value=dim_setting,
        #     channel=Device.all_actuators_integer(),
        #     delay=1.25
        # )

    @override
    def before_load_output_on(self, ctx, test_load: dict, step): 
        # This is exclusively for checking the change in the 0-10V port.
        coap_client.setDim(ctx.ip,9,10*ctx.current_relay)

        dim_setting: int = test_load.get('dim')
        # dim: int = getattr(test_load, "get", lambda *_: 100)('dim', 100)
        if dim_setting: 
            ctx.dim_expected = dim_setting
            coap_client.secure_setting(ctx.ip,f'/sensors/input{ctx.current_relay}','eventlh',f"F0,{ctx.current_relay},{dim_setting}",verbose=True) # Change sensor 1 events supernode version
        time.sleep(1.0)
        
        current_dim = coap_client.getDim(ctx.ip,ctx.current_relay)
        if current_dim != 0 and ctx.current_relay != 1: # Current channel should be 0 dim since it hasn't been set yet
            print(f"\033[3;93mPolicy eventhl is not working properly for channel {ctx.current_relay} | Dim: {current_dim} | Expected: 0\033[0m")

        # These 2 if statements are meant to invoke a change in dim from switching inputs on either end of the inputs 
        if ctx.current_relay == 1:
            mux.set(channel=8, verbose=False)
            time.sleep(0.5)
        # elif relay == 8 and dc_in_mode:
        #     set_mux(1,False)
        #     time.sleep(0.5)

        mux.set(ctx.current_relay)
        time.sleep(0.5)

    # Check to see that eventhl policy is working
        current_channel_dim = coap_client.getDim(ctx.ip,ctx.current_relay)
        if ctx.current_relay != 1: 
            previous_channel_dim = coap_client.getDim(ctx.ip,ctx.current_relay-1)
            if previous_channel_dim != 0:
                print(f"\033[3;93mPolicy eventhl is not working properly for channel {ctx.current_relay} | Previous: {previous_channel_dim} | Expected: 0\033[0m")
        if current_channel_dim != ctx.dim_expected:
            print(f"\033[3;93mPolicy eventlh is not working properly for channel {ctx.current_relay} | Current: {current_channel_dim} | Expected: {ctx.dim_expected}\033[0m")
            for i in range(1,9):
                print("Dim of channel",i,"is",coap_client.getDim(ctx.ip,i))
    
    @override
    def before_load_output_off(self, ctx, test_load: dict, step): 
        # GET OUTPUTS
        # time.sleep(5.0)
        current = coap_client.getValue(ctx.ip,f'/actuators/actuator{step}','current', timeout=5.0)
        voltage = coap_client.getValue(ctx.ip,f'/actuators/actuator{step}','voltage', timeout=5.0)
        if current is not None and voltage is not None: power = (current * voltage / 1000000) 
        else: power = None
        print(f"Power Output Data - Actuator {step}: {power} W")

    @override
    def after_load_sequence(self, ctx): pass
    ######################################################################

    # Sensor Testing
    def before_sensor_test(self, ctx): pass
    def after_sensor_test(self, ctx): 
        coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','0') # disable motion (supernode)

    def before_pdline_test(self, ctx): # TODO CHANGE TO POPUP PROMPT
        write.send_test_prompt(write.key,f'Connect control port of {ctx.device_name} to test station and press {write.key}','')
    def after_pdline_test(self, ctx): pass

    def custom_loads_test(self, ctx, test_loads): pass

    def dc_in_test(self, ctx, test_loads: list[dict]):
        import random
        from tests.load_test import test_single_load

        prompt.prompt(
            title_text="DCin Test",
            message_text="Replace SuperNode PoE cable with data cable. Then connect the DCin cable. "
                    "Press OK when ready"
        )

        time.sleep(3.0)
        valid_loads = None
        if test_loads is not None:
            valid_loads = [load for load in test_loads['test_steps'] if load.get('cccv') not in (1,2)]
            test_load = random.choice(valid_loads)
        
        if not valid_loads: 
            print("'Load' nor 'Loads' found in test yaml file. Using local default value.")
            local_default_loads = [
            { "cccv": 0, "Load_CV": 40, "dim": 100, "power": 45.0 },
            { "cccv": 1, "Load_CC": 5.0, "dim": 100, "power": 45.0 },
            { "cccv": 2, "Load_CC": 2.5, "dim": 100, "power": 45.0 },
            { "cccv": 3, "Load_CC": 2, "dim": 100, "power": 45.0 },
            { "cccv": 4, "Load_CC": 1.5, "dim": 100, "power": 45.0 }
            ]
            valid_loads = [load for load in local_default_loads if load.get('cccv') not in [1,2]]
            test_load = random.choice(local_default_loads)
        print(test_load)
        test_single_load(ctx, test_load)

        coap_client.setCCCV(ctx.ip,0,255)

        return True