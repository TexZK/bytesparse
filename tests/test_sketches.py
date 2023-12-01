
from typing import Type

from bytesparse.base import MutableMemory
from bytesparse.inplace import Memory as _Memory


class TestMemorySketches:

    Memory: Type[MutableMemory] = _Memory  # replace by subclassing 'Memory'
    ADDR_NEG: bool = True

    def test__walk_intervals(self):
        Memory = self.Memory

        blocks = [

        ]
