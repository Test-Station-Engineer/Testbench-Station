from devices.base import Device
from typing import override

class ELSNode(Device):
    @override
    def name(self) -> str:
        return "ELS-Node"
    @override
    def test_config_filename(self) -> str:
        return "test_CC.yaml" # NOTE Replace later