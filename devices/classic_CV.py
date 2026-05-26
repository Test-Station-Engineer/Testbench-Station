from dataclasses import dataclass
# from abc import ABC, abstractmethod
from typing import override

from devices.classic import Classic

# from context import TestContext


# from services import coap_client
# from time import sleep

@dataclass
class CV_2out(Classic):
    @override
    def name(self) -> str:
        return "CV_RS485"
    
    @override
    def test_config_filename(self) -> str:
        return "test_CV.yaml"
    