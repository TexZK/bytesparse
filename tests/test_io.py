# Copyright (c) 2020-2024, Andrea Zoppi.
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

import io

import pytest

from bytesparse.inplace import Memory
from bytesparse.io import SEEK_CUR
from bytesparse.io import SEEK_DATA
from bytesparse.io import SEEK_END
from bytesparse.io import SEEK_HOLE
from bytesparse.io import SEEK_SET
from bytesparse.io import MemoryIO


class TestMemoryIO:

    def test___del__(self):
        stream = MemoryIO(Memory.from_bytes(b'Hello, World!'))
        stream.__del__()
        assert stream.closed is True

    def test___enter___doctest(self):
        with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            data = stream.read()
        assert data == b'Hello, World!'

    def test___exit___doctest(self):
        with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            assert stream.closed is False
        assert stream.closed is True

    def test___init___doctest(self):
        stream = MemoryIO(seek=3)
        assert stream.write(b'Hello') == 5
        ref = [[3, b'Hello']]
        assert stream.memory.to_blocks() == ref
        assert stream.seek(10) == 10
        assert stream.write(b'World!') == 6
        ref = [[3, b'Hello'], [10, b'World!']]
        assert stream.memory.to_blocks() == ref

        memory = Memory.from_bytes(b'Hello, World!')
        stream = MemoryIO(memory, seek=7)
        assert stream.read() == b'World!'
        assert stream.tell() == 13
        assert stream.seek(-6, SEEK_END) == 7
        assert stream.write(b'Human') == 5
        assert bytes(memory) == b'Hello, Human!'
        assert stream.truncate(5) == 5
        assert stream.seek(3, SEEK_CUR) == 8
        assert stream.write(b'World') == 5
        assert memory.to_blocks() == [[0, b'Hello'], [8, b'World']]
        stream.close()

        blocks = [[3, b'Hello'], [10, b'World!']]
        memory = Memory.from_blocks(blocks)
        stream = MemoryIO(memory, seek=...)
        assert stream.tell() == 3
        assert stream.read() == b'Hello'

        blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        with MemoryIO(Memory.from_blocks(blocks)) as stream:
            lines = stream.readlines()
        assert lines == [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
        with pytest.raises(ValueError, match='I/O operation on closed stream'):
            stream.seek(0)

    def test___iter___doctest(self):
        blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        with MemoryIO(Memory.from_blocks(blocks)) as stream:
            lines = [line for line in stream]
        assert lines == [b'Hello\n', b'World!', b'Bye\n', b'Bye!']

    def test___next__doctest(self):
        blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        with MemoryIO(Memory.from_blocks(blocks), seek=9) as stream:
            assert next(stream) == b'World!'

    def test__check_closed_doctest(self):
        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            stream._check_closed()
        with pytest.raises(ValueError, match='I/O operation on closed stream'):
            stream._check_closed()

    def test_close_doctest(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        assert stream.closed is False
        assert (stream.memory is None) is False
        assert stream.readable() is True
        stream.close()
        assert stream.closed is True
        assert (stream.memory is None) is True
        with pytest.raises(ValueError, match='I/O operation on closed stream'):
            stream.readable()

    def test_closed_doctest(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        assert stream.closed is False
        stream.close()
        assert stream.closed is True

        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            assert stream.closed is False
        assert stream.closed is True

    def test_detach(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        with pytest.raises(io.UnsupportedOperation, match='detach'):
            stream.detach()

    def test_fileno(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        with pytest.raises(io.UnsupportedOperation, match='fileno'):
            stream.fileno()

    def test_flush(self):
        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            stream.flush()

    def test_getbuffer_doctest(self):
        with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            with stream.getbuffer() as buffer:
                assert type(buffer) is memoryview
                assert bytes(buffer) ==  b'Hello, World!'

        blocks = [[3, b'Hello'], [10, b'World!']]
        with pytest.raises(ValueError, match='non-contiguous data within range'):
            with MemoryIO(Memory.from_blocks(blocks)) as stream:
                stream.getbuffer()

    def test_getvalue(self):
        with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            value = stream.getvalue()
            assert type(value) is bytes
            assert bytes(value) ==  b'Hello, World!'

        blocks = [[3, b'Hello'], [10, b'World!']]
        with MemoryIO(Memory.from_blocks(blocks)) as stream:
            with pytest.raises(ValueError, match='non-contiguous data within range'):
                stream.getvalue()

    def test_isatty(self):
        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            assert stream.isatty() is False

    def test_memory_doctest(self):
        memory = Memory.from_bytes(b'Hello, World!')
        with MemoryIO(memory) as stream:
            assert (stream.memory is memory) is True
        assert (stream.memory is memory) is False
        assert (stream.memory is None) is True

    def test_peek_doctest(self):
        blocks = [[3, b'Hello'], [10, b'World!']]
        memory = Memory.from_blocks(blocks)
        stream = MemoryIO(memory, seek=4)
        assert stream.peek() == b''
        assert stream.peek(1) == b'e'
        assert stream.peek(11) == b'ello'
        assert stream.peek(None) == b'ello'
        assert stream.tell() == 4
        memview = stream.peek(-1, asmemview=True)
        assert type(memview) is memoryview
        assert bytes(memview) == b'ello'
        assert stream.seek(8) == 8
        assert stream.peek() == -2

    def test_read_doctest(self):
        blocks = [[3, b'Hello'], [10, b'World!']]
        memory = Memory.from_blocks(blocks)
        stream = MemoryIO(memory, seek=4)
        assert stream.read(1) == b'e'
        assert stream.tell() == 5
        assert stream.read(99) == b'llo'
        assert stream.tell() == 8
        assert stream.read() == -2
        assert stream.tell() == 10
        memview = stream.read(None, asmemview=True)
        assert type(memview) is memoryview
        assert bytes(memview) == b'World!'
        assert stream.tell() == 16
        assert stream.read() == b''
        assert stream.tell() == 16

    def test_readable(self):
        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            assert stream.readable() is True

    def test_readline_doctest(self):
        blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]

        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.readline() == b'Hello\n'
        assert stream.tell() == 9
        assert stream.readline(99) == b'World!'
        assert stream.tell() == 15
        assert stream.readline(99) == b'Bye\n'
        assert stream.tell() == 24
        assert stream.readline(None) == b'Bye!'
        assert stream.tell() == 32
        assert stream.readline() == b''
        assert stream.tell() == 32

        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.readline(4) == b'Hell'
        assert stream.tell() == 7
        assert stream.readline(4) == b'o\n'
        assert stream.tell() == 9

        stream = MemoryIO(Memory.from_blocks(blocks))
        view = stream.readline(asmemview=True)
        assert (type(view) is memoryview) is True
        assert bytes(view) == b'Hello\n'

        stream = MemoryIO(Memory.from_blocks(blocks))
        lines = []
        while 1:
            line = stream.readline(skipgaps=False)
            if line:
                lines.append(line)
            else:
                break
        ref = [-3, b'Hello\n', b'World!', -5, b'Bye\n', -4, b'Bye!']
        assert lines == ref
        assert stream.tell() == 32
        assert stream.readline(skipgaps=False) == b''
        assert stream.tell() == 32

    def test_readlines_doctest(self):
        blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]

        stream = MemoryIO(Memory.from_blocks(blocks))
        ref = [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
        assert stream.readlines() == ref
        assert stream.tell() == 32
        assert stream.readlines() == []
        assert stream.tell() == 32

        stream = MemoryIO(Memory.from_blocks(blocks))
        ref = [b'Hello\n', b'World!']
        assert stream.readlines(hint=10) == ref
        assert stream.tell() == 15

        stream = MemoryIO(Memory.from_blocks(blocks))
        views = stream.readlines(asmemview=True)
        assert all(type(view) is memoryview for view in views) is True
        ref = [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
        assert [bytes(view) for view in views] == ref

        stream = MemoryIO(Memory.from_blocks(blocks))
        ref = [-3, b'Hello\n', b'World!', -5, b'Bye\n', -4, b'Bye!']
        assert stream.readlines(skipgaps=False) == ref
        assert stream.tell() == 32
        assert stream.readlines(skipgaps=False) == []
        assert stream.tell() == 32

    def test_readinto_doctest(self):
        blocks = [[3, b'Hello'], [10, b'World!']]
        memory = Memory.from_blocks(blocks)

        stream = MemoryIO(memory, seek=4)
        buffer = bytearray(b'.' * 8)
        assert stream.readinto(buffer, skipgaps=True) == 8
        assert buffer == b'elloWorl'
        assert stream.tell() == 14
        assert stream.readinto(buffer, skipgaps=True) == 2
        assert buffer == b'd!loWorl'
        assert stream.tell() == 16
        assert stream.readinto(buffer, skipgaps=True) == 0
        assert buffer == b'd!loWorl'
        assert stream.tell() == 16

        stream = MemoryIO(memory, seek=4)
        buffer = bytearray(b'.' * 8)
        assert stream.readinto(buffer, skipgaps=False) == 4
        assert buffer == b'ello....'
        assert stream.tell() == 8
        assert stream.readinto(buffer, skipgaps=False) == -2
        assert stream.tell() == 10
        assert stream.readinto(buffer, skipgaps=False) == 6
        assert buffer == b'World!..'
        assert stream.tell() == 16
        assert stream.readinto(buffer, skipgaps=False) == 0
        assert buffer == b'World!..'
        assert stream.tell() == 16

    def test_seek_doctest(self):
        blocks = [[3, b'Hello'], [12, b'World!']]
        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.seek(5) == 5
        assert stream.seek(-3, SEEK_END) == 15
        assert stream.seek(2, SEEK_CUR) == 17
        assert stream.seek(1, SEEK_SET) == 1
        assert stream.seek(stream.tell(), SEEK_HOLE) == 1
        assert stream.seek(stream.tell(), SEEK_DATA) == 3
        assert stream.seek(stream.tell(), SEEK_HOLE) == 8
        assert stream.seek(stream.tell(), SEEK_DATA) == 12
        assert stream.seek(stream.tell(), SEEK_HOLE) == 18
        assert stream.seek(stream.tell(), SEEK_DATA) == 18
        assert stream.seek(22) == 22
        assert stream.seek(0) == 0

    def test_seek(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        position = stream.tell()
        with pytest.raises(ValueError, match='invalid whence'):
            stream.seek(0, 5)
        assert stream.tell() == position
        with pytest.raises(ValueError, match='invalid whence'):
            stream.seek(0, -1)
        assert stream.tell() == position

    def test_seekable(self):
        with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            assert stream.seekable() is True

    def test_skip_data_doctest(self):
        blocks = [[3, b'Hello'], [12, b'World!']]
        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.skip_data() == 0
        assert stream.seek(6) == 6
        assert stream.skip_data() == 8
        assert stream.skip_data() == 8
        assert stream.seek(12) == 12
        assert stream.skip_data() == 18
        assert stream.skip_data() == 18
        assert stream.seek(20) == 20
        assert stream.skip_data() == 20

    def test_skip_hole_doctest(self):
        blocks = [[3, b'Hello'], [12, b'World!']]
        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.skip_hole() == 3
        assert stream.skip_hole() == 3
        assert stream.seek(9) == 9
        assert stream.skip_hole() == 12
        assert stream.skip_hole() == 12
        assert stream.seek(20) == 20
        assert stream.skip_data() == 20

    def test_tell_doctest(self):
        blocks = [[3, b'Hello'], [12, b'World!']]
        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.tell() == 0
        assert stream.skip_hole() == 3
        assert stream.tell() == 3
        assert stream.read(5) == b'Hello'
        assert stream.tell() == 8
        assert stream.skip_hole() == 12
        assert stream.read() == b'World!'
        assert stream.tell() == 18
        assert stream.seek(20) == 20
        assert stream.tell() == 20

    def test_truncate_doctest(self):
        blocks = [[3, b'Hello'], [12, b'World!']]
        stream = MemoryIO(Memory.from_blocks(blocks))
        assert stream.seek(7) == 7
        assert stream.truncate() == 7
        assert stream.tell() == 7
        assert stream.memory.to_blocks() == [[3, b'Hell']]
        assert stream.truncate(10) == 10
        assert stream.tell() == 10

        memory = Memory.from_bytes(b'Hello, World!')
        setattr(memory, 'write', None)
        stream = MemoryIO(memory)
        assert stream.seek(7) == 7
        with pytest.raises(io.UnsupportedOperation, match='truncate'):
            stream.truncate()

    def test_truncate(self):
        stream = MemoryIO(Memory.from_bytes(b'ABC'))
        with pytest.raises(ValueError, match='negative size value'):
            stream.truncate(-1)

    def test_writable_doctest(self):
        memory = Memory.from_bytes(b'Hello, World!')
        with MemoryIO(memory) as stream:
            assert stream.writable() is True
        setattr(memory, 'write', None)
        with MemoryIO(memory) as stream:
            assert stream.writable() is False

    def test_write_doctest(self):
        blocks = [[3, b'Hello'], [10, b'World!']]
        memory = Memory.from_blocks(blocks)
        stream = MemoryIO(memory, seek=10)
        assert stream.write(b'Human') == 5
        assert memory.to_blocks() == [[3, b'Hello'], [10, b'Human!']]
        assert stream.tell() == 15
        assert stream.seek(7) == 7
        assert stream.write(5) == 5
        assert memory.to_blocks() == [[3, b'Hell'], [12, b'man!']]
        assert stream.tell() == 12
        assert stream.seek(7) == 7
        assert stream.write(-5) == 5
        assert memory.to_blocks() == [[3, b'Hellman!']]
        assert stream.tell() == 7

        memory = Memory.from_bytes(b'Hello, World!')
        setattr(memory, 'write', None)
        stream = MemoryIO(memory, seek=7)
        with pytest.raises(io.UnsupportedOperation, match='not writable'):
            stream.write(b'Human')

    def test_write_fail(self):
        memory = Memory.from_bytes(b'ABC')
        setattr(memory, 'write', None)
        with MemoryIO(memory) as stream:
            with pytest.raises(io.UnsupportedOperation, match='not writable'):
                stream.write(b'')

    def test_writelines_doctest(self):
        lines = [3, b'Hello\n', b'World!', 5, b'Bye\n', 4, b'Bye!']
        stream = MemoryIO()
        assert stream.writelines(lines) is None
        ref = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        assert stream.memory.to_blocks() == ref
