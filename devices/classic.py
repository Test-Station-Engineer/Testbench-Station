from dataclasses import dataclass
from abc import ABC, abstractmethod
from devices.base import Device
from typing import override

from procedures.test_procedure import TestProcedure
from procedures.classic_procedure import ClassicProcedure

@dataclass
class Classic(Device):
    stored_name: str = "CC-0-10"

    @abstractmethod
    @override
    def name(self) -> str:
        return self.stored_name
    # def name(self, optional_set_name_to_arg: str | None = None) -> str:
    #     name = optional_set_name_to_arg if optional_set_name_to_arg else self.stored_name
    #     self.stored_name = name
    #     return name
        
    @override
    @abstractmethod
    def test_config_filename(self) -> str:
        return "test.yaml"
    
    @override
    def procedure(self) -> TestProcedure:
        return ClassicProcedure()
    
    # Features
    def has_dc_in(self) -> bool:
        return False
    def has_rs485(self) -> bool:
        return True
    def has_sensors(self) -> bool:
        return True
    def has_010V_dimming(self) -> bool:
        return True