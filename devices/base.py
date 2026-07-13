from dataclasses import dataclass
from abc import ABC, abstractmethod
# from procedures.test_procedure import TestProcedure
try:
    from procedures.test_procedure import TestProcedure
except ImportError:
    print("IMPORT ERROR: Make sure TestProcedure has no issues.")

@dataclass
class Device(ABC):
    
    @abstractmethod
    def procedure(self) -> "TestProcedure":
        raise NotImplementedError("Device subclasses must implement the procedure() method.")
    
    def update_db_wait_time(self) -> float:
        """Return the amount of time (in seconds) to wait after sending the update_db command before proceeding with the test. This allows time for the device's database to update with the new settings before any further commands or checks are made."""
        return 8.0

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError("Device subclasses must implement the name() method.")
    @abstractmethod
    def test_config_filename(self) -> str:
        raise NotImplementedError("Device subclasses must implement the test_config_filename() method.")

    def ip(self) -> str:
        return self.ip_address
    
    # ACTUATOR RELATED METHODS #
    # @abstractmethod
    def all_actuators_integer(self) -> int:
        """Return the 'all actuators' sentinel integer."""
        return 3
    def number_of_actuators(self) -> int:
        return 2
    def first_actuator(self) -> int:
        return 1
    def relays(self) -> list[str | int]:
        return [1, 2]
    
    def single_actuator_resource(self, actuator_num: int = first_actuator) -> str:
        return f'/actuators/actuator{actuator_num}'
    def all_actuators_resource(self) -> str:
        return '/network'
    def all_actuators_key(self) -> str:
        return 'cmd'
    def all_actuators_maxw_command(self, maxw_value: int) -> str:
        return f'set_max_watt {self.all_actuators_integer()} {maxw_value}'
    def all_actuators_cccv_command(self, cccv_value: int) -> str: 
        return f'set_cv {self.all_actuators_integer()} {cccv_value}'
    def all_actuators_dim_command(self, dim_value: int) -> str:
        return f'set_dim {self.all_actuators_integer()} {dim_value}'
    
    def dim_resource_key(self, actuator_num: int = first_actuator) -> str:
        if actuator_num == self.all_actuators_integer(): return self.all_actuators_key()
        else: return 'pp'
    def power_resource_key(self, actuator_num: int = first_actuator) -> str:
        if actuator_num == self.all_actuators_integer(): return self.all_actuators_key()
        else: return 'maxw'
    def cccv_resource_key(self, actuator_num: int = first_actuator) -> str | None:
        if actuator_num == self.all_actuators_integer(): return self.all_actuators_key()
        else: return 'cccv'
    def current_resource_key(self, actuator_num: int = first_actuator) -> str | None:
        return None
    def voltage_resource_key(self, actuator_num: int = first_actuator) -> str | None:
        return None

    def post_maxw_setting_delay(self) -> float:
        return 0.5
    def post_cccv_setting_delay(self) -> float:
        return 8.0

    """ #  NOTE USE FOR SUPERNODE
    def cmd_network_resource(self, value: int) -> dict:
        resource = super().cmd_network_resource(value)
        resource['sensor'] = f'set_sensor {self.all_actuators_integer()} {value}'
        return resource
    """
    

    def load_test_sequence(self):
        pass

    def load_test_preset(self):
        pass

# END OF ACTUATOR RELATED METHODS #

    # Features
    def has_dc_in(self) -> bool:
        return False
    def has_rs485(self) -> bool:
        return False
    def has_sensors(self) -> bool:
        return True
    def has_010V_dimming(self) -> bool:
        return True