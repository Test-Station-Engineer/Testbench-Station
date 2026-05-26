from dataclasses import dataclass
# from abc import ABC, abstractmethod
from typing import override

from devices.classic import Classic

@dataclass
class CCUV_2out(Classic):
    @override
    def name(self) -> str:
        return "CCUV"
    
    @override
    def test_config_filename(self) -> str:
        return "test_CCUV.yaml"
    