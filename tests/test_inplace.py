# Copyright (c) 2020-2023, Andrea Zoppi.
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
from bytesparse.inplace import _repeat2
from bytesparse.inplace import bytesparse as _bytesparse


def test__repeat2_empty_pattern_infinite():
    ans_out = bytes(islice(_repeat2(b'abc', 0, None), 8))
    ans_ref = b'abcabcab'
    assert ans_out == ans_ref

    ans_out = bytes(islice(_repeat2(b'abc', 1, None), 8))
    ans_ref = b'bcabcabc'
    assert ans_out == ans_ref

    ans_out = bytes(islice(_repeat2(b'abc', -1, None), 8))
    ans_ref = b'cabcabca'
    assert ans_out == ans_ref


def test__repeat2_empty_pattern_sized():
    ans_out = bytes(_repeat2(b'abc', 0, 8))
    ans_ref = b'abcabcab'

    assert ans_out == ans_ref
    ans_out = bytes(_repeat2(b'abc', 1, 8))
    ans_ref = b'bcabcabc'
    assert ans_out == ans_ref

    ans_out = bytes(_repeat2(b'abc', -1, 8))
    ans_ref = b'cabcabca'
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
        memory2.validate()
        assert memory1.span == memory2.span
        assert memory1.bound_span == memory2.bound_span
        assert memory1.content_span == memory2.content_span
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory1._blocks, memory2._blocks))

    def test___copy___template(self):
        Memory = self.Memory
        blocks = create_template_blocks()
        memory1 = Memory.from_blocks(blocks, copy=False)
        memory2 = memory1.__copy__()
        memory2.validate()
        assert memory1.span == memory2.span
        assert memory1.bound_span == memory2.bound_span
        assert memory1.content_span == memory2.content_span
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory1._blocks, memory2._blocks))

    def test_validate_empty_invalid_bounds(self):
        Memory = self.Memory
        memory = Memory()
        memory._bound_start = 7
        memory._bound_endex = 3

        with pytest.raises(ValueError, match='invalid bounds'):
            memory.validate()

    def test_validate_invalid_block_data_size(self):
        Memory = self.Memory
        blocks = [[0, b'ABC'], [5, b''], [10, b'xyz']]
        memory = Memory.from_blocks(blocks, validate=False)

        with pytest.raises(ValueError, match='invalid block data size'):
            memory.validate()

    def test_validate_invalid_block_bounds(self):
        Memory = self.Memory

        memory = Memory(start=3, endex=6)
        blocks = [[1, b'ABC']]
        blocks = [[start, bytearray(data)] for start, data in blocks]
        memory._blocks = blocks

        with pytest.raises(ValueError, match='invalid block bounds'):
            memory.validate()

        memory = Memory(start=3, endex=6)
        blocks = [[5, b'xyz']]
        blocks = [[start, bytearray(data)] for start, data in blocks]
        memory._blocks = blocks

        with pytest.raises(ValueError, match='invalid block bounds'):
            memory.validate()

        memory = Memory(start=3, endex=6)
        blocks = [[0, b'123'], [10, b'ABC'], [5, b'xyz']]
        blocks = [[start, bytearray(data)] for start, data in blocks]
        memory._blocks = blocks

        with pytest.raises(ValueError, match='invalid block bounds'):
            memory.validate()

    def test__place_nothing(self):
        Memory = self.Memory
        blocks = [[1, b'ABC'], [6, b'xyz']]
        memory = Memory.from_blocks(blocks)
        memory._place(0, bytearray(), True)
        memory.validate()
        assert memory._blocks == blocks

    def test__place_after_extend(self):
        Memory = self.Memory
        blocks = [[1, b'ABC'], [6, b'xyz']]
        memory = Memory.from_blocks(blocks)
        memory._place(4, bytearray(b'123'), True)
        memory.validate()
        assert memory._blocks == [[1, b'ABC123'], [9, b'xyz']]

    def test__place_alone(self):
        Memory = self.Memory
        blocks = [[1, b'ABC'], [9, b'xyz']]
        memory = Memory.from_blocks(blocks)
        memory._place(5, bytearray(b'123'), True)
        memory.validate()
        assert memory._blocks == [[1, b'ABC'], [5, b'123'], [12, b'xyz']]

    def test__place_inside(self):
        Memory = self.Memory
        blocks = [[1, b'ABC'], [6, b'xyz']]
        memory = Memory.from_blocks(blocks)
        memory._place(3, bytearray(b'123'), True)
        memory.validate()
        assert memory._blocks == [[1, b'AB123C'], [9, b'xyz']]


class TestMemoryNonNegative(BaseMemorySuite):
    Memory: Type['_Memory'] = _Memory
    ADDR_NEG: bool = False


class TestBytesparse(BaseBytearraySuite, BaseMemorySuite):
    bytesparse: Type['_bytesparse'] = _bytesparse

    # Reuse some of BaseMemorySuite methods
    Memory: Type['_Memory'] = _bytesparse
    ADDR_NEG: bool = False

    def test_validate_negative(self):
        bytesparse = self.bytesparse
        memory = bytesparse(b'ABC')
        memory._blocks[0][0] = -1
        with pytest.raises(ValueError, match='negative block start'):
            memory.validate()
