# Copyright (c) 2020-2021, Andrea Zoppi.
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

from _common import *

from bytesparse._py import Memory as _Memory


class TestMemory(BaseMemorySuite):
    Memory: type = _Memory

    def test___init___nocopy(self):
        Memory = self.Memory
        data = b'5'
        blocks = [[0, b'0'], [5, data], [9, b'9']]
        offset = 123

        memory = Memory(data=data, copy=False)
        assert memory._blocks[0][1] is data

        memory = Memory(data=data, offset=offset, copy=False)
        assert memory._blocks[0][1] is data

        memory = Memory(blocks=blocks, copy=False)
        assert memory._blocks[1][1] is data

        memory = Memory(blocks=blocks, offset=offset, copy=False)
        assert memory._blocks[1][1] is data

        memory2 = Memory(memory=memory, copy=False)
        assert all(memory._blocks[i][1] is memory2._blocks[i][1] for i in range(3))

        memory2 = Memory(memory=memory, offset=offset, copy=False)
        assert all(memory._blocks[i][1] is memory2._blocks[i][1] for i in range(3))

    def test___init___bounds_invalid2(self):
        Memory = self.Memory
        match = r'invalid bounds'

        with pytest.raises(ValueError, match=match):
            memory = Memory(data=b'\0')
            block_data = memory._blocks[0][1]
            block_data.clear()
            Memory(memory=memory)

    def test__bytearray(self):
        Memory = self.Memory
        memory = Memory()
        assert memory._bytearray() == b''

        memory = Memory(data=b'xyz', offset=5)
        assert memory._bytearray() == b'xyz'

        blocks = [[5, b'xyz']]
        memory = Memory(blocks=blocks, copy=False)
        assert memory._bytearray() is blocks[0][1]

    def test__bytearray_invalid(self):
        Memory = self.Memory
        match = r'non-contiguous data within range'

        memory = Memory(start=1, endex=9)
        with pytest.raises(ValueError, match=match):
            memory._bytearray()

        memory = Memory(data=b'xyz', offset=5, start=1)
        with pytest.raises(ValueError, match=match):
            memory._bytearray()

        memory = Memory(data=b'xyz', offset=5, endex=9)
        with pytest.raises(ValueError, match=match):
            memory._bytearray()

        memory = Memory(blocks=create_template_blocks())
        with pytest.raises(ValueError, match=match):
            memory._bytearray()

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
        memory1 = Memory(blocks=blocks, copy=False)
        memory2 = memory1.__copy__()
        assert memory1.span == memory2.span
        assert memory1.trim_span == memory2.trim_span
        assert memory1.content_span == memory2.content_span
        assert all(b1[1] is b2[1] for b1, b2 in zip(memory1._blocks, memory2._blocks))
