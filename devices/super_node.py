from devices.base import Device
from typing import override

from procedures.test_procedure import TestProcedure
from procedures.supernode_procedure import SuperNodeProcedure

class SuperNode(Device):
    stored_name: str = "Supernode"

    @override
    def name(self) -> str:
        return self.stored_name
    @override
    def test_config_filename(self) -> str:
        return "test_supernode.yaml"
    
    @override
    def update_db_wait_time(self) -> float:
        return 14.0

    @override
    def all_actuators_integer(self) -> int:
        return 0
    @override
    def number_of_actuators(self) -> int:
        return 8
    @override
    def relays(self) -> list[str | int]:
        return [1,2,3,4,5,6,7,8]
    @override
    def procedure(self) -> TestProcedure:
        return SuperNodeProcedure()
    
    # Features
    @override
    def has_rs485(self) -> bool:
        return False
    @override
    def has_dc_in(self) -> bool:
        return True
    @override
    def has_010V_dimming(self) -> bool:
        return False