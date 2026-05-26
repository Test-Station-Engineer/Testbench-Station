from dataclasses import dataclass
# from abc import ABC, abstractmethod

from time import sleep

from typing import override

# from context import TestContext
from services import coap_client
from services import controller

from devices.base import Device

from resources import actuators

from write import write

from procedures.test_procedure import TestProcedure

@dataclass
class ClassicProcedure(TestProcedure):
    
    # Load Sequence
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
        
        # NOTE Commented out device settings irrelevant to this specific procedure. TODO Save for other procedures.
        """
        else: # As of now, there can't be both a cccv preset and a cc/cv value. 
            if 'cc' in test_load:
                if test_load['cc'] != ctx.cc_save:
                    if actuators.set_cccv(ctx=ctx,
                                actuator_num=Device.all_actuators_integer(), 
                                cccv_preset=test_load['cc']):
                        write.updateLog('set_cc','pass',test_load['cc'])
                        ctx.cccv_save = test_load['cc']
            elif 'cv' in test_load:
                if test_load['cv'] != ctx.cc_save:
                    if actuators.set_cccv(ctx=ctx,
                                actuator_num=Device.all_actuators_integer(), 
                                cccv_preset=test_load['cv']):
                        write.updateLog('set_cv','pass',test_load['cv'])
                        ctx.cccv_save = test_load['cv']
        """
        
        # CUV TODO Generalize for n actuators and use actuators.check_actuators() instead
        if 'cuv' in test_load:
            if test_load['cuv'] != ctx.cuv_save:
                if coap_client.secure_setting(ctx.ip,'/actuators/actuator1','cuv',str(test_load['cuv'])) and coap_client.secure_setting(ctx.ip,'/actuators/actuator2','cuv',str(test_load['cuv'])):
                    write.updateLog('testCUV','pass',test_load['cuv'])
        
        dim: int = 100
        if 'dim' in test_load:     # NOTE Keep an eye on this, 
            dim = test_load['dim'] # NOTE not sure if not having dim in test_load can  
            actuators.dim_update(  # NOTE cause issues with certain devices that use this procedure
                ctx=ctx,
                dim_down_value=10,
                dim_up_value=dim,
                channel=Device.all_actuators_integer(),
                delay=1.25
            )
    def before_load_output_on(self, ctx, test_load, step): pass
    
    def before_load_output_off(self, ctx, test_load, step): 
        # GET OUTPUTS
        sleep(5.0)
        # current_actuator = step[-1] if isinstance(step, str) else step
        pwr_output_data = coap_client.getValue(ctx.ip,f'/actuators/actuator{step}','power', timeout=5.0)
        print(f"Power Output Data - Actuator {step}: {pwr_output_data} W")
        pass
    
    def after_load_sequence(self, ctx, test_load, step): pass

    
    # Sensor Testing
    def before_sensor_test(self, ctx): 
        coap_client.putValue(ctx.ip,'/sensors/sensor1','eventrisefall','on,off') # change sensor 1 events
        coap_client.putValue(ctx.ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
        coap_client.putValue(ctx.ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
        # coap_client.putValue(ctx.ip,'/policy','updown','10,10,90,5') # this should be default, but change if not
        coap_client.putValue(ctx.ip,'/actuators/actuator1','motdsbl','33') # enable motion
    
    def after_sensor_test(self, ctx): 
        # if not ctx.mini_node_test: coap_client.secure_setting(ctx.ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
        # if not ctx.supernode_test: coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','3') # disable motion
        # else: coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','0') # disable motion (supernode)
        coap_client.secure_setting(ctx.ip,'/sensors/sensor1','eventrisefall','mot,vac') # reset sensor 1 events
        coap_client.secure_setting(ctx.ip,'/actuators/actuator1','motdsbl','3') # disable motion

    # Wall Switch Testing
    @override
    def before_pdline_test(self, ctx): 
        coap_client.putValue(ctx.ip,'/policy','onpol','0,100,-1,101,256') # this should be default, but change if not
        coap_client.putValue(ctx.ip,'/policy','offpol','0,0,-1,101,256') # this should be default, but change if not
    def after_pdline_test(self, ctx): pass

    def custom_loads_test(self, ctx, test_loads: list[dict]): pass