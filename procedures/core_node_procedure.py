from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import override
import time

from context import TestContext

from services import coap_client, mux
from services import controller

from devices.base import Device
from resources import actuators
from write import write

from procedures.test_procedure import TestProcedure

class CoreNodeProcedure(TestProcedure):

    def __init__(self, drivers: list[int] = [0]) -> None:
        self.drivers = drivers
        self.mot: int = 100
        self.vac: int = 0

    # def check_yaml_for_specific_procedure_tests(self) -> bool: pass
    @override
    def before_load_sequence(self, ctx, test_loads): pass
    def set_relays(self,channel): controller.setRelays(channel)
    def before_load_relays(self, ctx, test_load: dict): pass
    def before_load_output_on(self, ctx, test_load: dict, step): pass
    def before_load_output_off(self, ctx, test_load: dict, step): pass
    def after_load_sequence(self, ctx): pass

    def before_sensor_test(self, ctx):
        ip=ctx.ip
        for driver in self.drivers:
            coap_client.secure_setting(ip,'/drivers/0/sensor','type','INPUT_LH')
            coap_client.secure_setting(ip,'/drivers/0/policy','mot',f'F1,0,{self.mot},-1,101;')
            coap_client.secure_setting(ip,'/drivers/0/policy','vac','F1,0,101,1,0;')
            # coap_client.secure_setting(ip,'/drivers/0/sensor','eventlh','mot')
            # coap_client.secure_setting(ip,'/drivers/0/sensor','eventhl','vac')
            coap_client.secure_setting(ip,'/drivers/0/sensor','eventlh',f'F0,0,{self.mot};')
            coap_client.secure_setting(ip,'/drivers/0/sensor','eventhl',f'F0,0,{self.vac};')

            coap_client.secure_setting(ip,f'/drivers/{driver}/sensor','enable','true')
    
    def after_sensor_test(self, ctx): pass

    def before_pdline_test(self, ctx): 
        print("Drivers:",self.drivers)
        for driver in self.drivers: 
            if not coap_client.secure_setting(ctx.ip,f'/drivers/{driver}/wallswitch','enable','true'): write.send_test_prompt(write.key,f'Type "set_wallswitch_enable true" in driver console and press {write.key} when it has been set.','')
        
        time.sleep(3.0) # 2.9.4+ has a slight delay before enabling

        mux.set(2,True)
    def after_pdline_test(self, ctx): pass

    def custom_loads_test(self, ctx, test_loads): pass