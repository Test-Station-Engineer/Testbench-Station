from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import override

from devices.base import Device
from devices.classic import Classic

from procedures.test_procedure import TestProcedure
from procedures.classic_procedure import ClassicProcedure

@dataclass
class SmartDesk(Classic):
    @override
    def name(self) -> str:
        return "Smart-Desk"
    
    @override
    def test_config_filename(self) -> str:
        return "test_smart_desk_load.yaml"
    
    @override
    def procedure(self) -> TestProcedure:
        return ClassicProcedure()
    
    @override
    def number_of_actuators(self) -> int:
        return 1
    @override
    def relays(self) -> list[str | int]:
        return [1]
    
    @override
    def has_rs485(self) -> bool:
        return False
    @override
    def has_sensors(self) -> bool:
        return False
    @override
    def has_010V_dimming(self) -> bool:
        return False
    