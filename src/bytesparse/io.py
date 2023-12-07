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

r"""Streaming utilities."""

import io
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Union

from . import Memory as _Memory
from .base import Address
from .base import AnyBytes
from .base import EllipsisType
from .base import ImmutableMemory
from .base import MutableMemory

# Not all the platforms support sparse files natively, thus they do not provide
# os.SEEK_DATA and os.SEEK_HOLE by themselves; we do it here!
SEEK_SET: int = 0
SEEK_CUR: int = 1
SEEK_END: int = 2
SEEK_DATA: int = 3
SEEK_HOLE: int = 4


class MemoryIO(io.BufferedIOBase):
    r"""Buffered I/O wrapper.

    This class wraps an :obj:`ImmutableMemory` object so that the latter can
    be accessed like a typical Python I/O read-only stream.

    A memory stream is writable if, on its creation (:meth:`__init__`), its
    underlying memory object can be written an empty byte string at its start
    address, without raising any exceptions.

    Any operations executed on a closed stream may fail, raising an exception.

    The stream position (the result of :meth:`tell`) indicates the address
    currently pointed by the stream.
    It is just a number, and as such it is allowed to fall outside the actual
    memory bounds.

    The stream position always refers to absolute address 0; in no way it ever
    refers to the :attr:`ImmutableMemory.start` of the underlying wrapped
    memory object.

    Arguments:
        memory (:obj:`ImmutableMemory`):
            The memory object to wrap.
            If ``None``, it assigns a new empty :obj:`bytesparse.Memory`.

        seek (int):
            If ``Ellipsis``, :meth:`seek` to :attr:`memory.start`.
            If not ``None``, :meth:`seek` to the absolute address `seek`.

    Attributes:
        _memory (:obj:`ImmutableMemory`):
            The underlying wrapped memory object.
            It is set to ``None`` when :attr:`closed`.

        _position (int):
            The current stream position.
            It always refers to absolute address 0.

        _writable (bool):
            The stream is writable on creation.

    See Also:
        :class:`bytesparse.base.ImmutableMemory`
        :class:`bytesparse.base.MutableMemory`
        :meth:`seek`
        :meth:`writable`

    Examples:
        >>> from bytesparse import Memory, MemoryIO

        >>> stream = MemoryIO(seek=3)
        >>> stream.write(b'Hello')
        5
        >>> str(stream.memory)
        "<[[3, b'Hello']]>"
        >>> stream.seek(10)
        10
        >>> stream.write(b'World!')
        6
        >>> str(stream.memory)
        "<[[3, b'Hello'], [10, b'World!']]>"

        >>> memory = Memory.from_bytes(b'Hello, World!')
        >>> stream = MemoryIO(memory, seek=7)
        >>> stream.read()
        b'World!'
        >>> stream.tell()
        13
        >>> stream.seek(-6, SEEK_END)
        7
        >>> stream.write(b'Human')
        5
        >>> bytes(memory)
        b'Hello, Human!'
        >>> stream.truncate(5)
        5
        >>> stream.seek(3, SEEK_CUR)
        8
        >>> stream.write(b'World')
        5
        >>> memory.to_blocks()
        [[0, b'Hello'], [8, b'World']]
        >>> stream.close()

        >>> blocks = [[3, b'Hello'], [10, b'World!']]
        >>> memory = Memory.from_blocks(blocks)
        >>> stream = MemoryIO(memory, seek=...)
        >>> stream.tell()
        3
        >>> stream.read()
        b'Hello'

        >>> blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        >>> with MemoryIO(Memory.from_blocks(blocks)) as stream:
        ...     lines = stream.readlines()
        >>> lines
        [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
        >>> stream.seek(0)
        Traceback (most recent call last):
            ...
        ValueError: I/O operation on closed stream.
    """

    def __del__(self) -> None:
        r"""Prepares the object for destruction.

        It makes sure the stream is closed upon object destruction.
        """

        self.close()

    def __enter__(self) -> 'MemoryIO':
        r"""Context manager enter function.

        Returns:
            :obj:`MemoryIO`: The stream object itself.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            ...     data = stream.read()
            >>> data
            b'Hello, World!'
        """

        self._check_closed()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        r"""Context manager exit function.

        It makes sure the stream is closed upon context exit.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            ...     print(stream.closed)
            False
            >>> print(stream.closed)
            True
        """

        self.close()

    def __init__(
        self,
        memory: Optional[Union[ImmutableMemory, MutableMemory]] = None,
        seek: Optional[Union[Address, EllipsisType]] = None,
    ):

        if memory is None:
            memory = _Memory()
            writable = True
        else:
            start = memory.start
            try:
                memory.write(start, b'')
            except Exception:
                writable = False
            else:
                writable = True

        self._memory: Optional[Union[ImmutableMemory, MutableMemory]] = memory
        self._writable: bool = writable
        self._position: Address = 0

        if seek is Ellipsis:
            self.seek(memory.start)
        elif seek is not None:
            self.seek(seek)

    def __iter__(self) -> Iterator[bytes]:
        r"""Iterates over lines.

        Repeatedly calls :meth:`readline`, as long as it returns byte strings.
        Yields the values returned by such calls.

        Yields:
            bytes: Single line; terminator included.

        See Also:
            :meth:`readline`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
            >>> with MemoryIO(Memory.from_blocks(blocks)) as stream:
            ...     lines = [line for line in stream]
            >>> lines
            [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
        """

        while 1:
            line = self.readline()
            try:
                line < 0
            except TypeError:
                if line:
                    yield line
                else:
                    break

    def __next__(self) -> bytes:
        r"""Next iterated line.

        Calls :meth:`readline` once, returning the value.

        Returns:
            bytes or int: Line read from the stream, or the negative gap size.

        See Also:
            :meth:`readline`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
            >>> with MemoryIO(Memory.from_blocks(blocks), seek=9) as stream:
            ...     print(next(stream))
            b'World!'
        """

        return self.readline()

    def _check_closed(self) -> None:
        r"""Checks if the stream is closed.

        In case the stream is :attr:`closed`, it raises :obj:`ValueError`.

        Raises:
            ValueError: The stream is closed.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            ...     stream._check_closed()
            >>> stream._check_closed()
            Traceback (most recent call last):
                ...
            ValueError: I/O operation on closed stream.
        """

        if self.closed:
            raise ValueError('I/O operation on closed stream.')

    def close(self) -> None:
        r"""Closes the stream.

        Any subsequent operations on the closed stream may fail, and some
        properties may change state.

        The stream no more links to an underlying memory object.

        See Also:
            :attr:`closed`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> stream = MemoryIO(Memory.from_bytes(b'ABC'))
            >>> stream.closed
            False
            >>> stream.memory is None
            False
            >>> stream.readable()
            True
            >>> stream.close()
            >>> stream.closed
            True
            >>> stream.memory is None
            True
            >>> stream.readable()
            Traceback (most recent call last):
                ...
            ValueError: I/O operation on closed stream.
        """

        self._memory = None
        self._writable = False
        self._position = 0

    @property
    def closed(self) -> bool:
        r"""Closed stream.

        Returns:
            bool: Closed stream.

        See Also:
            :meth:`close`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> stream = MemoryIO(Memory.from_bytes(b'ABC'))
            >>> stream.closed
            False
            >>> stream.close()
            >>> stream.closed
            True

            >>> with MemoryIO(Memory.from_bytes(b'ABC')) as stream:
            ...     print(stream.closed)
            False
            >>> print(stream.closed)
            True
        """

        return self._memory is None

    def detach(self) -> None:
        r"""Detaches the underlying raw stream.

        Warnings:
            It always raises :exc:`io.UnsupportedOperation`.
            This method is present only for API compatibility.
            No actual underlying stream is present for this object.

        Raises:
            :exc:`io.UnsupportedOperation`: No underlying raw stream.
        """

        raise io.UnsupportedOperation('detach')

    def fileno(self) -> int:
        r"""File descriptor identifier.

        Warnings:
            It always raises :exc:`io.UnsupportedOperation`.
            This method is present only for API compatibility.
            No actual file descriptor is associated to this object.

        Raises:
            OSError: Not a file stream.
        """

        raise io.UnsupportedOperation('fileno')

    def flush(self) -> None:
        r"""Flushes buffered data into the underlying raw steam.

        Notes:
            Since no underlying stream is associated, this method does nothing.
        """

        pass

    def getbuffer(self) -> memoryview:
        r"""Memory view of the underlying memory object.

        Warnings:
            This method may fail when the underlying memory object has gaps
            within data.

        Returns:
            memoryview: Memory view over the underlying memory object.

        See Also:
            :meth:`ImmutableMemory.view`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            ...     with stream.getbuffer() as buffer:
            ...         print(type(buffer), '=', bytes(buffer))
            <class 'memoryview'> = b'Hello, World!'

            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> with MemoryIO(Memory.from_blocks(blocks)) as stream:
            ...     stream.getbuffer()
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """

        self._check_closed()
        return self._memory.view()

    def getvalue(self) -> bytes:
        r"""Byte string copy of the underlying memory object.

        Warnings:
            This method may fail when the underlying memory object has gaps
            within data.

        Returns:
            bytes: Byte string copy of the underlying memory object.

        See Also:
            :meth:`ImmutableMemory.to_bytes`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> with MemoryIO(Memory.from_bytes(b'Hello, World!')) as stream:
            ...     value = stream.getvalue()
            ...     print(type(value), '=', bytes(value))
            <class 'bytes'> = b'Hello, World!'

            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> with MemoryIO(Memory.from_blocks(blocks)) as stream:
            ...     stream.getvalue()
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """

        self._check_closed()
        return self._memory.to_bytes()

    def isatty(self) -> bool:
        r"""Interactive console stream.

        Returns:
            bool: ``False``, not an interactive console stream.
        """

        return False

    @property
    def memory(self) -> Optional[ImmutableMemory]:
        r""":obj:`ImmutableMemory`: Underlying memory object.

        ``None`` when :attr:`closed`.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> memory = Memory.from_bytes(b'Hello, World!')
            >>> with MemoryIO(memory) as stream:
            ...     print(stream.memory is memory)
            True
            >>> print(stream.memory is memory)
            False
            >>> print(stream.memory is None)
            True
        """

        return self._memory

    def peek(
        self,
        size: Optional[Address] = 0,
        asmemview: bool = False,
    ) -> Union[bytes, memoryview, Address]:
        r"""Previews the next chunk of bytes.

        Similar to :meth:`read`, without moving the stream position instead.
        This method can be used to preview the next chunk of bytes, without
        affecting the stream itself.

        The number of returned bytes may be different from `size`, which acts
        as a mere hint.

        If the current stream position lies within a memory gap, this method
        returns the negative amount of bytes to reach the next data block.

        If the current stream position is after the end of memory data, this
        method returns an empty byte string.

        Arguments:
            size (int):
                Number of bytes to read.
                If negative or ``None``, read as many bytes as possible.

            asmemview (bool):
                Return a :obj:`memoryview` instead of :obj:`bytes`.

        Returns:
            bytes: Chunk of bytes.

        See Also:
            :meth:`read`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> memory = Memory.from_blocks(blocks)
            >>> stream = MemoryIO(memory, seek=4)
            >>> stream.peek()
            b''
            >>> stream.peek(1)
            b'e'
            >>> stream.peek(11)
            b'ello'
            >>> stream.peek(None)
            b'ello'
            >>> stream.tell()
            4
            >>> memview = stream.peek(-1, asmemview=True)
            >>> type(memview)
            <class 'memoryview'>
            >>> bytes(memview)
            b'ello'
            >>> stream.seek(8)
            8
            >>> stream.peek()
            -2
        """

        if size is None:
            size = -1
        self._check_closed()
        start = self._position
        memory = self._memory
        _, block_endex, block_value = memory.block_span(start)

        if block_value is None:
            return start - block_endex

        if size < 0:
            endex = block_endex
        else:
            endex = start + size
            if endex > block_endex:
                endex = block_endex

        if asmemview:
            chunk = memory.view(start=start, endex=endex)
        else:
            chunk = memory.to_bytes(start=start, endex=endex)
        return chunk

    def read(
        self,
        size: Optional[Address] = -1,
        asmemview: bool = False,
    ) -> Union[bytes, memoryview, Address]:
        r"""Reads a chunk of bytes.

        Starting from the current stream position, this method tries to read up
        to `size` bytes (or as much as possible if negative or ``None``).

        The number of bytes can be less than `size` in the case a memory hole
        or the end are encountered.

        If the current stream position lies within a memory gap, this method
        returns the negative amount of bytes to reach the next data block.

        If the current stream position is after the end of memory data, this
        method returns an empty byte string.

        Arguments:
            size (int):
                Number of bytes to read.
                If negative or ``None``, read as many bytes as possible.

            asmemview (bool):
                Return a :obj:`memoryview` instead of :obj:`bytes`.

        Returns:
            bytes: Chunk of up to `size` bytes.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> memory = Memory.from_blocks(blocks)
            >>> stream = MemoryIO(memory, seek=4)
            >>> stream.read(1)
            b'e'
            >>> stream.tell()
            5
            >>> stream.read(99)
            b'llo'
            >>> stream.tell()
            8
            >>> stream.read()
            -2
            >>> stream.tell()
            10
            >>> memview = stream.read(None, asmemview=True)
            >>> type(memview)
            <class 'memoryview'>
            >>> bytes(memview)
            b'World!'
            >>> stream.tell()
            16
            >>> stream.read()
            b''
            >>> stream.tell()
            16
        """

        if size is None:
            size = -1
        self._check_closed()
        start = self._position
        memory = self._memory
        _, block_endex, block_value = memory.block_span(start)

        if block_value is None:
            if block_endex is None:
                return b''
            else:
                self._position = block_endex
                return start - block_endex

        if size < 0:
            endex = block_endex
        else:
            endex = start + size
            if endex > block_endex:
                endex = block_endex

        if asmemview:
            chunk = memory.view(start=start, endex=endex)
        else:
            chunk = memory.to_bytes(start=start, endex=endex)
        self._position = endex
        return chunk

    read1 = read

    def readable(self) -> bool:
        r"""Stream is readable.

        Returns:
            bool: ``True``, stream is always readable.
        """

        self._check_closed()
        return True

    def readline(
        self,
        size: Optional[Address] = -1,
        skipgaps: bool = True,
        asmemview: bool = False,
    ) -> Union[bytes, memoryview, Address]:
        r"""Reads a line.

        A standard line is a sequence of bytes terminating with a ``b'\n'``
        newline character.

        If `size` is provided (not ``None`` nor negative), the current line
        ends there, without a trailing newline character.

        If the stream is pointing after the memory end, an empty byte string
        is returned.

        If a memory hole (gap) is encountered, the current line ends there
        without a trailing newline character.
        The stream is always positioned after the gap.

        If the stream points within a memory hole, it returns the
        negative number of bytes until the next data block.
        The stream is always positioned after the gap.

        Arguments:
            size (int):
                Maximum number of bytes for the line to read.
                If ``None`` or negative, no limit is set.

            skipgaps (bool):
                If false, the negative size of the pointed memory hole.

            asmemview (bool):
                If true, the returned object is a :obj:`memoryview` instead of
                :obj:`bytes`.

        Returns:
            bytes or int: Line read from the stream, or the negative gap size.

        See Also:
            :meth:`read`
            :meth:`readlines`

        Examples:
            >>> from bytesparse import Memory, MemoryIO
            >>> blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.readline()
            b'Hello\n'
            >>> stream.tell()
            9
            >>> stream.readline(None)
            b'World!'
            >>> stream.tell()
            15
            >>> stream.readline(99)
            b'Bye\n'
            >>> stream.tell()
            24
            >>> stream.readline(99)
            b'Bye!'
            >>> stream.tell()
            32
            >>> stream.readline()
            b''
            >>> stream.tell()
            32

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.readline(4)
            b'Hell'
            >>> stream.tell()
            7
            >>> stream.readline(4)
            b'o\n'
            >>> stream.tell()
            9

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> view = stream.readline(asmemview=True)
            >>> type(view) is memoryview
            True
            >>> bytes(view)
            b'Hello\n'

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> # Emulating stream.readlines(skipgaps=False)
            >>> lines = []
            >>> line = True
            >>> while line:
            ...     line = stream.readline(skipgaps=False)
            ...     lines.append(line)
            >>> lines
            [-3, b'Hello\n', b'World!', -5, b'Bye\n', -4, b'Bye!']
            >>> stream.tell()
            32
            >>> stream.readline(skipgaps=False)
            b''
            >>> stream.tell()
            32
        """

        if size is None:
            size = -1
        self._check_closed()
        memory = self._memory
        start = self._position
        try:
            block_start, block_endex = next(memory.intervals(start=start))
        except StopIteration:
            return b''

        if start < block_start:
            if not skipgaps:
                self._position = block_start
                return start - block_start
            start = block_start
            self._position = start

        if size < 0:
            endex = block_endex
        else:
            endex = start + size
            if endex > block_endex:
                endex = block_endex
        try:
            endex = memory.index(b'\n', start=start, endex=endex) + 1
        except ValueError:
            pass

        if asmemview:
            chunk = memory.view(start=start, endex=endex)
        else:
            chunk = memory.to_bytes(start=start, endex=endex)
        self._position = endex
        return chunk

    def readlines(
        self,
        hint: Optional[Address] = -1,
        skipgaps: bool = True,
        asmemview: bool = False,
    ) -> List[Union[bytes, Address]]:
        r"""Reads a list of lines.

        It repeatedly calls :meth:`readline`, collecting the returned values
        into a list, until the total number of bytes read reaches `hint`.

        If a memory hole (gap) is encountered, the current line ends there
        without a trailing newline character, and the stream is positioned
        after the gap.

        If `skipgaps` is false, the list is appended the negative size of each
        encountered memory hole.

        Arguments:
            hint (int):
                Number of bytes after which line reading stops.
                If ``None`` or negative, no limit is set.

            skipgaps (bool):
                If false, the list hosts the negative size of each memory hole.

            asmemview (bool):
                If true, the returned objects are memory views instead of byte
                strings.

        Returns:
            list of bytes or int: List of lines and gaps read from the stream.

        See Also:
            :meth:`__iter__`
            :meth:`read`
            :meth:`readline`

        Examples:
            >>> from bytesparse import Memory, MemoryIO
            >>> blocks = [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.readlines()
            [b'Hello\n', b'World!', b'Bye\n', b'Bye!']
            >>> stream.tell()
            32
            >>> stream.readlines()
            []
            >>> stream.tell()
            32

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.readlines(hint=10)
            [b'Hello\n', b'World!']
            >>> stream.tell()
            15

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> views = stream.readlines(asmemview=True)
            >>> all(type(view) is memoryview for view in views)
            True
            >>> [bytes(view) for view in views]
            [b'Hello\n', b'World!', b'Bye\n', b'Bye!']

            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.readlines(skipgaps=False)
            [-3, b'Hello\n', b'World!', -5, b'Bye\n', -4, b'Bye!']
            >>> stream.tell()
            32
            >>> stream.readlines(skipgaps=False)
            []
            >>> stream.tell()
            32
        """

        if hint is not None and hint < 0:
            hint = None
        total = 0
        lines: List[bytes] = []

        while hint is None or total < hint:
            line = self.readline(skipgaps=skipgaps, asmemview=asmemview)
            try:
                line < 0
            except TypeError:
                if line:
                    lines.append(line)
                    total += len(line)
                else:
                    break
            else:  # skipgaps
                lines.append(line)
        return lines

    def readinto(
        self,
        buffer: Union[bytearray, memoryview, MutableMemory],
        skipgaps: bool = True,
    ) -> Address:
        r"""Reads data into a byte buffer.

        If the stream is pointing after the memory end, no bytes are read.

        If pointing within a memory hole (gap), the negative number of bytes
        until the next data block is returned.
        The stream is always positioned after the gap.

        If a memory hole (gap) is encountered after reading some bytes, the
        reading stops there, and the number of bytes read is returned.
        The stream is always positioned after the gap.

        Standard operation reads data until `buffer` is full, or encountering
        the memory end. It returns the number of bytes read.

        Arguments:
            buffer (bytearray):
                A pre-allocated byte array to fill with bytes read from the
                stream.

            skipgaps (bool):
                If false, it stops reading when a memory hole (gap) is
                encountered.

        Returns:
            int: Number of bytes read, or the negative gap size.

        Examples:
            >>> from bytesparse import Memory, MemoryIO
            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> memory = Memory.from_blocks(blocks)

            >>> stream = MemoryIO(memory, seek=4)
            >>> buffer = bytearray(b'.' * 8)
            >>> stream.readinto(buffer, skipgaps=True)
            8
            >>> buffer
            bytearray(b'elloWorl')
            >>> stream.tell()
            14
            >>> stream.readinto(buffer, skipgaps=True)
            2
            >>> buffer
            bytearray(b'd!loWorl')
            >>> stream.tell()
            16
            >>> stream.readinto(buffer, skipgaps=True)
            0
            >>> buffer
            bytearray(b'd!loWorl')
            >>> stream.tell()
            16

            >>> stream = MemoryIO(memory, seek=4)
            >>> buffer = bytearray(b'.' * 8)
            >>> stream.readinto(buffer, skipgaps=False)
            4
            >>> buffer
            bytearray(b'ello....')
            >>> stream.tell()
            8
            >>> stream.readinto(buffer, skipgaps=False)
            -2
            >>> stream.tell()
            10
            >>> stream.readinto(buffer, skipgaps=False)
            6
            >>> buffer
            bytearray(b'World!..')
            >>> stream.tell()
            16
            >>> stream.readinto(buffer, skipgaps=False)
            0
            >>> buffer
            bytearray(b'World!..')
            >>> stream.tell()
            16
        """

        self._check_closed()
        memory = self._memory
        start = self._position
        size = len(buffer)
        pending = size
        offset = 0

        for block_start, block_endex in memory.intervals(start=start):
            if start < block_start:
                if not skipgaps:
                    if offset:
                        return offset
                    else:
                        self._position = block_start
                        return start - block_start
                start = block_start
                self._position = start

            endex = start + pending
            if endex > block_endex:
                endex = block_endex
            size = endex - start

            with memory.view(start=start, endex=endex) as view:
                buffer[offset:(offset + size)] = view

            start += size
            self._position = start
            offset += size
            pending -= size
            if pending <= 0:
                break
        return offset

    readinto1 = readinto

    def seek(
        self,
        offset: Address,
        whence: int = SEEK_SET,
    ) -> Address:
        r"""Changes the current stream position.

        It performs the classic ``seek()`` I/O operation.

        The `whence` can be any of:

        * :const:`SEEK_SET` (``0`` or ``None``):
            referring to the absolute address 0.

        * :const:`SEEK_CUR` (``1``):
            referring to the current stream position (:meth:`tell`).

        * :const:`SEEK_END` (``2``):
            referring to the memory end (:attr:`ImmutableMemory.endex`).

        * :const:`SEEK_DATA` (``3``):
            if the current stream position lies within a memory hole,
            it moves to the beginning of the next data block;
            no operation is performed otherwise.

        * :const:`SEEK_HOLE` (``4``):
            if the current stream position lies within a data block,
            it moves to the beginning of the next memory hole
            (note: the end of the stream is considered as a memory hole);
            no operation is performed otherwise.

        Arguments:
            offset (int):
                Position offset to apply.

            whence (int):
                Where the offset is referred.
                It can be any of the standard ``SEEK_*`` values.
                By default, it refers to the beginning of the stream.

        Returns:
            int: The updated stream position.

        Notes:
            Stream position is just a number, not related to memory ranges.

        Examples:
            >>> from bytesparse import *

            >>> blocks = [[3, b'Hello'], [12, b'World!']]
            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.seek(5)
            5
            >>> stream.seek(-3, SEEK_END)
            15
            >>> stream.seek(2, SEEK_CUR)
            17
            >>> stream.seek(1, SEEK_SET)
            1
            >>> stream.seek(stream.tell(), SEEK_HOLE)
            1
            >>> stream.seek(stream.tell(), SEEK_DATA)
            3
            >>> stream.seek(stream.tell(), SEEK_HOLE)
            8
            >>> stream.seek(stream.tell(), SEEK_DATA)
            12
            >>> stream.seek(stream.tell(), SEEK_HOLE)  # EOF
            18
            >>> stream.seek(stream.tell(), SEEK_DATA)  # EOF
            18
            >>> stream.seek(22)  # after
            22
            >>> stream.seek(0)  # before
            0
        """

        self._check_closed()

        if whence == SEEK_SET:
            self._position = offset

        elif whence == SEEK_CUR:
            self._position += offset

        elif whence == SEEK_END:
            self._position = self._memory.endex + offset

        elif whence == SEEK_DATA:
            _, block_endex, block_value = self._memory.block_span(offset)
            if block_value is None and block_endex is not None:
                self._position = block_endex

        elif whence == SEEK_HOLE:
            _, block_endex, block_value = self._memory.block_span(offset)
            if block_value is not None:
                self._position = block_endex
        else:
            raise ValueError('invalid whence')
        return self._position

    def seekable(self) -> bool:
        r"""Stream is seekable.

        Returns:
            bool: ``True``, stream is always seekable.
        """

        self._check_closed()
        return True

    def skip_data(self) -> Address:
        r"""Skips a data block.

        It moves the current stream position after the end of the currently
        pointed data block.

        No action is performed if the current stream position lies within a
        memory hole (gap).

        Returns:
            int: Updated stream position.

        See Also:
            :meth:`seek`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [12, b'World!']]
            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.skip_data()
            0
            >>> stream.seek(6)
            6
            >>> stream.skip_data()
            8
            >>> stream.skip_data()
            8
            >>> stream.seek(12)
            12
            >>> stream.skip_data()
            18
            >>> stream.skip_data()
            18
            >>> stream.seek(20)
            20
            >>> stream.skip_data()
            20
        """

        _, block_endex, block_value = self._memory.block_span(self._position)
        if block_value is not None:
            self._position = block_endex
        return self._position

    def skip_hole(self) -> Address:
        r"""Skips a memory hole.

        It moves the current stream position after the end of the currently
        pointed memory hole (gap).

        No action is performed if the current stream position lies within a
        data block.

        Returns:
            int: Updated stream position.

        See Also:
            :meth:`seek`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [12, b'World!']]
            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.skip_hole()
            3
            >>> stream.skip_hole()
            3
            >>> stream.seek(9)
            9
            >>> stream.skip_hole()
            12
            >>> stream.skip_hole()
            12
            >>> stream.seek(20)
            20
            >>> stream.skip_hole()
            20
        """

        _, block_endex, block_value = self._memory.block_span(self._position)
        if block_value is None and block_endex is not None:
            self._position = block_endex
        return self._position

    def tell(self) -> Address:
        r"""Current stream position.

        Returns:
            int: Current stream position.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [12, b'World!']]
            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.tell()
            0
            >>> stream.skip_hole()
            3
            >>> stream.tell()
            3
            >>> stream.read(5)
            b'Hello'
            >>> stream.tell()
            8
            >>> stream.skip_hole()
            12
            >>> stream.read()
            b'World!'
            >>> stream.tell()
            18
            >>> stream.seek(20)
            20
            >>> stream.tell()
            20
        """

        self._check_closed()
        return self._position

    def truncate(
        self,
        size: Optional[Address] = None,
    ) -> Address:
        r"""Truncates stream.

        If `size` is provided, it moves the current stream position to it.

        Any data after the updated stream position are deleted from the
        underlying memory object.

        The updated stream position can lie outside the actual memory bounds
        (i.e. extending after the memory).
        No filling is performed, only the stream position is moved there.

        Arguments:
            size (int):
                If not ``None``, the stream is positioned there.

        Returns:
            int: Updated stream position.

        Raises:
            :exc:`io.UnsupportedOperation`: Stream not writable.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [12, b'World!']]
            >>> stream = MemoryIO(Memory.from_blocks(blocks))
            >>> stream.seek(7)
            7
            >>> stream.truncate()
            7
            >>> stream.tell()
            7
            >>> stream.memory.to_blocks()
            [[3, b'Hell']]
            >>> stream.truncate(10)
            10
            >>> stream.tell()
            10

            >>> memory = Memory.from_bytes(b'Hello, World!')
            >>> setattr(memory, 'write', None)  # exception on write()
            >>> stream = MemoryIO(memory)
            >>> stream.seek(7)
            7
            >>> stream.truncate()
            Traceback (most recent call last):
                ...
            io.UnsupportedOperation: truncate
        """

        self._check_closed()
        if self._writable:
            if size is None:
                size = self._position
            else:
                if size < 0:
                    raise ValueError('negative size value')
            self._memory.delete(start=size)
            self._position = size
            return size
        else:
            raise io.UnsupportedOperation('truncate')

    def writable(self) -> bool:
        r"""Stream is writable.

        Returns:
            bool: Stream is writable.

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> memory = Memory.from_bytes(b'Hello, World!')
            >>> with MemoryIO(memory) as stream:
            ...     print(stream.writable())
            True
            >>> setattr(memory, 'write', None)  # exception on write()
            >>> with MemoryIO(memory) as stream:
            ...     print(stream.writable())
            False
        """

        self._check_closed()
        return self._writable

    def write(
        self,
        buffer: Union[AnyBytes, ImmutableMemory, int],
    ) -> Address:
        r"""Writes data into the stream.

        The behaviour depends on the nature of `buffer`: byte-like or integer.

        Byte-like data are written into the underlying memory object via its
        :meth:`bytesparse.base.MutableMemory.write` method, at the current stream position
        (i.e. :meth:`tell`).
        The stream position is always incremented by the size of `buffer`,
        regardless of the actual number of bytes written into the
        underlying memory object (e.g. when cropped by existing
        :attr:`bytesparse.base.MutableMemory.bounds_span` settings).

        If `buffer` is a positive integer, that is the amount of bytes to
        :meth:`bytesparse.base.MutableMemory.clear` from the current stream position onwards.
        The stream position is incremented by `buffer` bytes.
        It returns `buffer` as a positive number.

        If `buffer` is a negative integer, that is the amount of bytes to
        :meth:`bytesparse.base.MutableMemory.delete` from the current stream position onwards.
        The stream position is not changed.
        It returns `buffer` as a positive number.

        Notes:
            `buffer` is considered an integer if the execution of
            ``buffer.__index__()`` does not raise an :exc:`Exception`.

        Arguments:
            buffer (bytes):
                Byte data to write at the current stream position.

        Returns:
            int: Size of the written `buffer`.

        Raises:
            :exc:`io.UnsupportedOperation`: Stream not writable.

        See Also:
            :meth:`bytesparse.base.MutableMemory.clear`
            :meth:`bytesparse.base.MutableMemory.delete`
            :meth:`bytesparse.base.MutableMemory.write`

        Examples:
            >>> from bytesparse import Memory, MemoryIO

            >>> blocks = [[3, b'Hello'], [10, b'World!']]
            >>> memory = Memory.from_blocks(blocks)
            >>> stream = MemoryIO(memory, seek=10)
            >>> stream.write(b'Human')
            5
            >>> memory.to_blocks()
            [[3, b'Hello'], [10, b'Human!']]
            >>> stream.tell()
            15
            >>> stream.seek(7)
            7
            >>> stream.write(5)  # clear 5 bytes
            5
            >>> memory.to_blocks()
            [[3, b'Hell'], [12, b'man!']]
            >>> stream.tell()
            12
            >>> stream.seek(7)
            7
            >>> stream.write(-5)  # delete 5 bytes
            5
            >>> memory.to_blocks()
            [[3, b'Hellman!']]
            >>> stream.tell()
            7

            >>> memory = Memory.from_bytes(b'Hello, World!')
            >>> setattr(memory, 'write', None)  # exception on write()
            >>> stream = MemoryIO(memory, seek=7)
            >>> stream.write(b'Human')
            Traceback (most recent call last):
                ...
            io.UnsupportedOperation: not writable
        """

        self._check_closed()
        if self._writable:
            start = self._position
            try:
                size = buffer.__index__()
            except Exception:
                size = len(buffer)
                self._memory.write(start, buffer)
                self._position = start + size
            else:
                if size < 0:
                    size = -size
                    endex = start + size
                    self._memory.delete(start=start, endex=endex)
                else:
                    endex = start + size
                    self._memory.clear(start=start, endex=endex)
                    self._position = endex
            return size
        else:
            raise io.UnsupportedOperation('not writable')

    def writelines(
        self,
        lines: Iterable[Union[AnyBytes, int]],
    ) -> None:
        r""" Writes lines to the stream.

        Line separators are not added, so it is usual for each of the lines
        provided to have a line separator at the end.

        If a `line` is an integer, its behavior is as per :meth:`write`
        (positive: clear, negative: delete).

        Arguments:
            lines (list of bytes):
                List of byte strings to write.

        See Also:
            :meth:`bytesparse.base.MutableMemory.clear`
            :meth:`bytesparse.base.MutableMemory.delete`
            :meth:`write`

        Examples:
            >>> from bytesparse import Memory, MemoryIO
            >>> lines = [3, b'Hello\n', b'World!', 5, b'Bye\n', 4, b'Bye!']
            >>> stream = MemoryIO()
            >>> stream.writelines(lines)
            >>> stream.memory.to_blocks()
            [[3, b'Hello\nWorld!'], [20, b'Bye\n'], [28, b'Bye!']]
        """

        for line in lines:
            self.write(line)
