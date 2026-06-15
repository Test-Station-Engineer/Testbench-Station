from dataclasses import dataclass
from abc import ABC, abstractmethod

from services import controller

# from context import TestContext

@dataclass
class TestProcedure(ABC):
    '''TestProcedure is an abstract base class that defines the structure for test procedures.
    Each method corresponds to a specific stage in the testing process, allowing for customized behavior at each stage. 
    By inheriting from this class and implementing the desired methods, 
    you can create a test procedure that fits the specific needs of your device and testing requirements.'''
    
    """def __init__(self):
        self.ran_once = False               # NOTE Probably not the best strategy in the long run
        self.set_relays = True              # NOTE Probably not the best strategy in the long run
        self.turn_load_off_after = True
        self.invert_power_thresh = False
        pass"""
    
    # TODO Implement a runner that checks for the specific procedure tests in the YAML file
    def check_yaml_for_specific_procedure_tests(self) -> bool: pass

    def before_load_sequence(self, ctx, test_loads): pass
    def set_relays(self,channel): controller.setRelays(channel)
    def before_load_relays(self, ctx, test_load: dict): pass
    def before_load_output_on(self, ctx, test_load: dict, step): pass
    def before_load_output_off(self, ctx, test_load: dict, step): pass
    def after_load_sequence(self, ctx): pass

    def before_sensor_test(self, ctx): pass
    def after_sensor_test(self, ctx): pass

    def before_pdline_test(self, ctx): pass
    def after_pdline_test(self, ctx): pass

    def custom_loads_test(self, ctx, test_loads): pass