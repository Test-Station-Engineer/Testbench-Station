from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import override

from devices.base import Device
from devices.classic import Classic

from procedures.test_procedure import TestProcedure
from procedures.classic_procedure import ClassicProcedure

@dataclass
class CC_2out(Classic):
    @override
    def name(self) -> str:
        return "CC-010"
    
    @override
    def test_config_filename(self) -> str:
        return "test_CC.yaml"
    
    @override
    def procedure(self) -> TestProcedure:
        return ClassicProcedure()
    