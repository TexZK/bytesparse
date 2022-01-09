# Copyright (c) 2020-2022, Andrea Zoppi.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from typing import Type

from _common import *

from bytesparse.inplace import Memory as _Memory
from bytesparse.inplace import bytesparse as _bytesparse
from bytesparse.inplace import collapse_blocks


def test_collapse_blocks___doctest__():
    blocks = [
        [0, b'0123456789'],
        [0, b'ABCD'],
        [3, b'EF'],
        [0, b'$'],
        [6, b'xyz'],
    ]
    ans_out = collapse_blocks(blocks)
    ans_ref = [[0, b'$BCEF5xyz9']]
    assert ans_out == ans_ref

    blocks = [
        [0, b'012'],
        [4, b'AB'],
        [6, b'xyz'],
        [1, b'$'],
    ]
    ans_out = collapse_blocks(blocks)
    ans_ref = [[0, b'0$2'], [4, b'ABxyz']]
    assert ans_out == ans_ref


class TestMemory(BaseMemorySuite):
    Memory: Type['_Memory'] = _Memory

    def test___init___nocopy(self):
        Memory = self.Memory
        data = b'5'
        blocks = [[0, b'0'], [5, data], [9, b'9']]
        offset = 123

        memory = Memory.from_bytes(data, copy=False)
        assert memory._blocks[0][1] is data

        memory = Memory.from_bytes(data, offset, copy=False)
        assert memory._blocks[0][1] is data

        memory = Memory.from_blocks(blocks, copy=False)
        assert memory._blocks[1][1] is data

        memory = Memory.from_blocks(blocks, offset, copy=False)
        assert memory._blocks[1][1] is data

        memory2 = Memory.from_memory(memory, copy=False)
        assert all(memory._blocks[i][1] is memory2._blocks[i][1] for i in range(3))

        memory2 = Memory.from_memory(memory, offset, copy=False)
        assert all(memory._blocks[i][1] is memory2._blocks[i][1] for i in range(3))

    def test___init___bounds_invalid2(self):
        Memory = self.Memory
        match = r'invalid bounds'

        with pytest.raises(ValueError, match=match):
            memory = Memory.from_bytes(b'\0')
            block_data = memory._blocks[0][1]
            block_data.clear()
            Memory.from_memory(memory)

    def test_from_blocks_nocopy(self):
        Memory = self.Memory
        blocks = [[1, b'ABC'], [5, b'xyz']]
        memory = Memory.from_blocks(blocks, copy=False, validate=False)
        assert memory._blocks == blocks
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory._blocks, blocks))

    def test___copy___empty(self):
        Memory = self.Memory
        memory1 = Memory()
        memory2 = memory1.__copy__()
        assert memory1.span == memory2.span
        assert memory1.trim_span == memory2.trim_span
        assert memory1.content_span == memory2.content_span
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory1._blocks, memory2._blocks))

    def test___copy___template(self):
        Memory = self.Memory
        blocks = create_template_blocks()
        memory1 = Memory.from_blocks(blocks, copy=False)
        memory2 = memory1.__copy__()
        assert memory1.span == memory2.span
        assert memory1.trim_span == memory2.trim_span
        assert memory1.content_span == memory2.content_span
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory1._blocks, memory2._blocks))

    def test_validate_empty_invalid_bounds(self):
        Memory = self.Memory
        memory = Memory()
        memory._trim_start = 7
        memory._trim_endex = 3

        with pytest.raises(ValueError, match='invalid bounds'):
            memory.validate()

    def test_validate_invalid_block_data_size(self):
        Memory = self.Memory
        blocks = [[0, b'ABC'], [5, b''], [10, b'xyz']]
        memory = Memory.from_blocks(blocks, validate=False)

        with pytest.raises(ValueError, match='invalid block data size'):
            memory.validate()


class TestMemoryNonNegative(BaseMemorySuite):
    Memory: Type['_Memory'] = _Memory
    ADDR_NEG: bool = False


class TestBytesparse(BaseBytearraySuite):
    bytesparse: Type['_bytesparse'] = _bytesparse
