from devices.base import Device
from typing import override

from procedures.test_procedure import TestProcedure
from procedures.battery_backup_procedure import BatteryBackupProcedure

class BatteryBackup(Device):

    @override
    def name(self) -> str:
        return "Battery-Backup"
    @override
    def test_config_filename(self) -> str:
        return "test_battery_backup.yaml"
    @override
    def procedure(self) -> TestProcedure:
        return BatteryBackupProcedure()

    @override
    def all_actuators_integer(self) -> int:
        return 0
    @override
    def number_of_actuators(self) -> int:
        return 1
    @override
    def first_actuator(self) -> int:
        return 1
    @override
    def relays(self) -> list[int | str]:
        return [1]