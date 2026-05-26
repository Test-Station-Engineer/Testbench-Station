from dataclasses import dataclass
# from abc import ABC, abstractmethod
from typing import override

from devices.classic import Classic

# from context import TestContext


# from services import coap_client
# from time import sleep

@dataclass
class USBC_2out(Classic):
    @override
    def name(self) -> str:
        return "USBC-Node"
    
    @override
    def test_config_filename(self) -> str:
        return "test_USBC.yaml"
    
    # Features
    @override
    def has_power_meter(self) -> bool:
        return False
    