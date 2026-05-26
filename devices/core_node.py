from devices.base import Device
from typing import override

from procedures.core_node_procedure import CoreNodeProcedure

class CoreNode(Device):

    def __init__(self, drivers: list[int] = [0]) -> None:
        self.drivers = drivers

    @override
    def name(self) -> str:
        return "Core-Node"
    @override
    def test_config_filename(self) -> str:
        return "test_core_node.yaml"

    @override # NOTE Technically doesn't exist for core nodes
    def all_actuators_integer(self) -> int:
        return -1
    @override
    def number_of_actuators(self) -> int:
        return 1
    @override
    def first_actuator(self) -> int:
        return 0
    @override
    def relays(self) -> list[int]:
        return self.drivers
    
    def actuator_resource(self, i: int = 0) -> str:
        return f'/drivers/{i}/actuator'
    