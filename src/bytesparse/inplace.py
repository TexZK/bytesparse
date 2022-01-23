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

r"""In-place implementation.

This implementation in pure Python uses the basic :obj:``bytearray`` data type
to hold block data, which allows mutable in-place operations.
"""

from itertools import count as _count
from itertools import islice as _islice
from itertools import repeat as _repeat
from itertools import zip_longest as _zip_longest
from typing import Any
from typing import ByteString
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union
from typing import cast as _cast

from .base import STR_MAX_CONTENT_SIZE
from .base import Address
from .base import AnyBytes
from .base import BlockIndex
from .base import BlockIterable
from .base import BlockList
from .base import BlockSequence
from .base import ClosedInterval
from .base import EllipsisType
from .base import ImmutableMemory
from .base import MutableMemory
from .base import OpenInterval
from .base import Value


def _repeat2(
    pattern: Optional[ByteString],
    offset: Address,
    size: Optional[Address],
) -> Iterator[Value]:
    r"""Pattern repetition.

    Arguments:
        pattern (list of int):
            The pattern to repeat, made of byte integers, or ``None``.

        offset (int):
            Index of the first value within the pattern. Wraparound supported.

        size (int):
            Size of the repeated pattern; ``None`` for infinite repetition.

    Yields:
        int: Repeated pattern values.
    """

    if pattern is None:
        if size is None:
            yield from _repeat(None)

        elif 0 < size:
            yield from _repeat(None, size)

    else:
        pattern_size = len(pattern)
        if offset:
            offset %= pattern_size

            if size is None:
                while 1:
                    yield from _islice(pattern, offset, pattern_size)
                    yield from _islice(pattern, offset)

            else:
                for _ in range(size // pattern_size):
                    yield from _islice(pattern, offset, pattern_size)
                    yield from _islice(pattern, offset)

                size %= pattern_size
                chunk_size = pattern_size - offset
                if size < chunk_size:
                    chunk_size = size
                yield from _islice(pattern, offset, offset + chunk_size)
                yield from _islice(pattern, size - chunk_size)
        else:
            if size is None:
                while 1:
                    yield from pattern

            else:
                for _ in range(size // pattern_size):
                    yield from pattern

                yield from _islice(pattern, size % pattern_size)


def collapse_blocks(
    blocks: BlockIterable,
) -> BlockList:
    r"""Collapses a generic sequence of blocks.

    Given a generic sequence of blocks, writes them in the same order,
    generating a new sequence of non-contiguous blocks, sorted by address.

    Arguments:
        blocks (sequence of blocks):
            Sequence of blocks to collapse.

    Returns:
        list of blocks: Collapsed block list.

    Examples:
        +---+---+---+---+---+---+---+---+---+---+
        | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
        +===+===+===+===+===+===+===+===+===+===+
        |[0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9]|
        +---+---+---+---+---+---+---+---+---+---+
        |[A | B | C | D]|   |   |   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |   |   |   |[E | F]|   |   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |[$]|   |   |   |   |   |   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |   |   |   |   |   |   |[x | y | z]|   |
        +---+---+---+---+---+---+---+---+---+---+
        |[$ | B | C | E | F | 5 | x | y | z | 9]|
        +---+---+---+---+---+---+---+---+---+---+

        >>> blocks = [
        ...     [0, b'0123456789'],
        ...     [0, b'ABCD'],
        ...     [3, b'EF'],
        ...     [0, b'$'],
        ...     [6, b'xyz'],
        ... ]
        >>> collapse_blocks(blocks)
        [[0, b'$BCEF5xyz9']]

        ~~~

        +---+---+---+---+---+---+---+---+---+---+
        | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
        +===+===+===+===+===+===+===+===+===+===+
        |[0 | 1 | 2]|   |   |   |   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |   |   |   |   |[A | B]|   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |   |   |   |   |   |   |[x | y | z]|   |
        +---+---+---+---+---+---+---+---+---+---+
        |   |[$]|   |   |   |   |   |   |   |   |
        +---+---+---+---+---+---+---+---+---+---+
        |[0 | $ | 2]|   |[A | B | x | y | z]|   |
        +---+---+---+---+---+---+---+---+---+---+

        >>> blocks = [
        ...     [0, b'012'],
        ...     [4, b'AB'],
        ...     [6, b'xyz'],
        ...     [1, b'$'],
        ... ]
        >>> collapse_blocks(blocks)
        [[0, b'0$2'], [4, b'ABxyz']]
    """

    memory = Memory()

    for block_start, block_data in blocks:
        memory.write(block_start, block_data)

    return memory._blocks


class Memory(MutableMemory):
    r"""Virtual memory.

    This class is a handy wrapper around `blocks`, so that it can behave mostly
    like a :obj:`bytearray`, but on sparse chunks of data.

    Please look at examples of each method to get a glimpse of the features of
    this class.

    Attributes:
        _blocks (list of blocks):
            A sequence of spaced blocks, sorted by address.

        _trim_start (int):
            Memory trimming start address. Any data before this address is
            automatically discarded; disabled if ``None``.

        _trim_endex (int):
            Memory trimming exclusive end address. Any data at or after this
            address is automatically discarded; disabled if ``None``.

    Arguments:
        start (int):
            Optional memory start address.
            Anything before will be trimmed away.

        endex (int):
            Optional memory exclusive end address.
            Anything at or after it will be trimmed away.

    Examples:
        >>> memory = Memory()
        >>> memory.to_blocks()
        []

        >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
        >>> memory.to_blocks()
        [[5, b'Hello, World!']]
    """

    def __add__(
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'Memory':

        memory = self.from_memory(self, validate=False)
        memory.extend(value)
        return memory

    def __bool__(
        self,
    ) -> bool:
        r"""Has any items.

        Returns:
            bool: Has any items.

        Examples:
            >>> memory = Memory()
            >>> bool(memory)
            False

            >>> memory = Memory.from_bytes(b'Hello, World!', 5)
            >>> bool(memory)
            True
        """

        return bool(self._blocks)

    def __bytes__(
        self,
    ) -> bytes:
        r"""Creates a bytes clone.

        Returns:
            :obj:`bytes`: Cloned data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        return bytes(self.view())

    def __contains__(
        self,
        item: Union[AnyBytes, Value],
    ) -> bool:
        r"""Checks if some items are contained.

        Arguments:
            item (items):
                Items to find. Can be either some byte string or an integer.

        Returns:
            bool: Item is contained.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[1 | 2 | 3]|   |[x | y | z]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'123'], [9, b'xyz']])
            >>> b'23' in memory
            True
            >>> ord('y') in memory
            True
            >>> b'$' in memory
            False
        """

        return any(item in block_data for _, block_data in self._blocks)

    def __copy__(
        self,
    ) -> 'Memory':
        r"""Creates a shallow copy.

        Returns:
            :obj:`Memory`: Shallow copy.
        """

        return self.from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=False)

    def __deepcopy__(
        self,
    ) -> 'Memory':
        r"""Creates a deep copy.

        Returns:
            :obj:`Memory`: Deep copy.
        """

        return self.from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=True)

    def __delitem__(
        self,
        key: Union[Address, slice],
    ) -> None:
        r"""Deletes data.

        Arguments:
            key (slice or int):
                Deletion range or address.

        Note:
            This method is not optimized for a :class:`slice` where its `step`
            is an integer greater than 1.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | y | z]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> del memory[4:9]
            >>> memory.to_blocks()
            [[1, b'ABCyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | D]|   |[$]|   |[x | z]|   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | D]|   |[$]|   |[x | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | D]|   |   |[x]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> del memory[9]
            >>> memory.to_blocks()
            [[1, b'ABCD'], [6, b'$'], [8, b'xz']]
            >>> del memory[3]
            >>> memory.to_blocks()
            [[1, b'ABD'], [5, b'$'], [7, b'xz']]
            >>> del memory[2:10:3]
            >>> memory.to_blocks()
            [[1, b'AD'], [5, b'x']]
        """

        if self._blocks:
            if isinstance(key, slice):
                start = key.start
                if start is None:
                    start = self.start

                endex = key.stop
                if endex is None:
                    endex = self.endex

                if start < endex:
                    step = key.step
                    if step is None or step == 1:
                        self._erase(start, endex, True)  # delete

                    elif step > 1:
                        for address in reversed(range(start, endex, step)):
                            self._erase(address, address + 1, True)  # delete
            else:
                address = key.__index__()
                self._erase(address, address + 1, True)  # delete

    def __eq__(
        self,
        other: Any,
    ) -> bool:
        r"""Equality comparison.

        Arguments:
            other (Memory):
                Data to compare with `self`.

                If it is a :obj:`Memory`, all of its blocks must match.

                If it is a :obj:`bytes`, a :obj:`bytearray`, or a
                :obj:`memoryview`, it is expected to match the first and only
                stored block.

                Otherwise, it must match the first and only stored block,
                via iteration over the stored values.

        Returns:
            bool: `self` is equal to `other`.

        Examples:
            >>> data = b'Hello, World!'
            >>> memory = Memory.from_bytes(data)
            >>> memory == data
            True
            >>> memory.shift(1)
            >>> memory == data
            True

            >>> data = b'Hello, World!'
            >>> memory = Memory.from_bytes(data)
            >>> memory == list(data)
            True
            >>> memory.shift(1)
            >>> memory == list(data)
            True
        """

        if isinstance(other, Memory):
            return self._blocks == other._blocks

        elif isinstance(other, ImmutableMemory):
            zipping = _zip_longest(self._blocks, other.blocks(), fillvalue=(0, b''))
            return all(b1 == b2 for b1, b2 in zipping)

        elif isinstance(other, (bytes, bytearray, memoryview)):
            blocks = self._blocks
            block_count = len(blocks)
            if block_count > 1:
                return False
            elif block_count:
                return blocks[0][1] == other
            else:
                return len(other) == 0

        else:
            iter_self = self.values()
            iter_other = iter(other)
            return all(a == b for a, b in _zip_longest(iter_self, iter_other, fillvalue=None))

    def __getitem__(
        self,
        key: Union[Address, slice],
    ) -> Any:
        r"""Gets data.

        Arguments:
            key (slice or int):
                Selection range or address.
                If it is a :obj:`slice` with bytes-like `step`, the latter is
                interpreted as the filling pattern.

        Returns:
            items: Items from the requested range.

        Note:
            This method is not optimized for a :class:`slice` where its `step`
            is an integer greater than 1.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|
            +---+---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67| 68|   | 36|   |120|121|122|
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory[9]  # -> ord('y') = 121
            121
            >>> memory[:3]._blocks
            [[1, b'AB']]
            >>> memory[3:10]._blocks
            [[3, b'CD'], [6, b'$'], [8, b'xy']]
            >>> bytes(memory[3:10:b'.'])
            b'CD.$.xy'
            >>> memory[memory.endex]
            None
            >>> bytes(memory[3:10:3])
            b'C$y'
            >>> memory[3:10:2]._blocks
            [[3, b'C'], [6, b'y']]
            >>> bytes(memory[3:10:2])
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """

        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = self.start
            endex = key.stop
            if endex is None:
                endex = self.endex
            step = key.step

            if isinstance(step, Value):
                if step >= 1:
                    return self.extract(start, endex, step=step)
                else:
                    return Memory()  # empty
            else:
                return self.extract(start, endex, pattern=step)
        else:
            return self.peek(key.__index__())

    def __iadd__(
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'Memory':

        self.extend(value)
        return self

    def __imul__(
        self,
        times: int,
    ) -> 'Memory':

        times = int(times)
        if times < 0:
            times = 0
        blocks = self._blocks
        if times and blocks:
            start = self.start
            size = self.endex - start
            offset = size
            memory = self.from_memory(self, validate=False)

            for time in range(times - 1):
                self.write(offset, memory)
                offset += size
        else:
            blocks.clear()
        return self

    def __init__(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ):

        if start is not None:
            start = Address(start)
        if endex is not None:
            endex = Address(endex)
            if start is not None and endex < start:
                endex = start

        self._blocks: BlockList = []
        self._trim_start: Optional[Address] = start
        self._trim_endex: Optional[Address] = endex

    def __iter__(
        self,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values.

        Iterates over values between :attr:`start` and :attr:`endex`.

        Yields:
            int: Value as byte integer, or ``None``.
        """

        yield from self.values(self.start, self.endex)

    def __len__(
        self,
    ) -> Address:
        r"""Actual length.

        Computes the actual length of the stored items, i.e.
        (:attr:`endex` - :attr:`start`).
        This will consider any trimmings being active.

        Returns:
            int: Memory length.
        """

        return self.endex - self.start

    def __mul__(
        self,
        times: int,
    ) -> 'Memory':

        times = int(times)
        if times < 0:
            times = 0
        blocks = self._blocks
        if times and blocks:
            start = self.start
            size = self.endex - start
            offset = size  # adjust first write
            memory = self.from_memory(self, validate=False)

            for time in range(times - 1):
                memory.write(offset, self)
                offset += size

            return memory
        else:
            return self.__class__()

    def __repr__(
        self,
    ) -> str:

        return f'<{self.__class__.__name__}[0x{self.start:X}:0x{self.endex:X}]@0x{id(self):X}>'

    def __reversed__(
        self,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values, reversed order.

        Iterates over values between :attr:`start` and :attr:`endex`, in
        reversed order.

        Yields:
            int: Value as byte integer, or ``None``.
        """

        yield from self.rvalues(self.start, self.endex)

    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Optional[Union[AnyBytes, Value]],
    ) -> None:
        r"""Sets data.

        Arguments:
            key (slice or int):
                Selection range or address.

            value (items):
                Items to write at the selection address.
                If `value` is null, the range is cleared.

        Note:
            This method is not optimized for a :class:`slice` where its `step`
            is an integer greater than 1.

        Examples:
            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |[C]|   |   | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A | 1 | C]|   |[2 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory[7:10] = None
            >>> memory.to_blocks()
            [[5, b'AB'], [10, b'yz']]
            >>> memory[7] = b'C'
            >>> memory[9] = b'x'
            >>> memory.to_blocks() == [[5, b'ABC'], [9, b'xyz']]
            True
            >>> memory[6:12:3] = None
            >>> memory.to_blocks()
            [[5, b'A'], [7, b'C'], [10, b'yz']]
            >>> memory[6:13:3] = b'123'
            >>> memory.to_blocks()
            [[5, b'A1C'], [9, b'2yz3']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |   |   |[A | B | C]|   |[x | y | z]|
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |[$]|   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |[$]|   |[A | B | 4 | 5 | 6 | 7 | 8 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |[$]|   |[A | B | 4 | 5 | < | > | 8 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory[0:4] = b'$'
            >>> memory.to_blocks()
            [[0, b'$'], [2, b'ABC'], [6, b'xyz']]
            >>> memory[4:7] = b'45678'
            >>> memory.to_blocks()
            [[0, b'$'], [2, b'AB45678yz']]
            >>> memory[6:8] = b'<>'
            >>> memory.to_blocks()
            [[0, b'$'], [2, b'AB45<>8yz']]
        """

        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = self.start

            endex = key.stop
            if endex is None:
                endex = self.endex

            if endex < start:
                endex = start

            step = key.step
            if step is None or step == 1:
                step = None
            elif step < 1:
                return  # empty range

            if value is None:
                # Clear range
                if step is None:
                    self._erase(start, endex, False)  # clear
                else:
                    for address in range(start, endex, step):
                        self._erase(address, address + 1, False)  # clear
                return  # nothing to write

            slice_size = endex - start
            if step is not None:
                slice_size = (slice_size + step - 1) // step

            if isinstance(value, Value):
                value = bytearray((value,))
                value *= slice_size
            value_size = len(value)

            if value_size < slice_size:
                # Shrink: remove excess, overwrite existing
                if step is None:
                    del_start = start + value_size
                    del_endex = del_start + (slice_size - value_size)
                    self._erase(del_start, del_endex, True)  # delete
                    self.write(start, value)
                else:
                    raise ValueError(f'attempt to assign bytes of size {value_size}'
                                     f' to extended slice of size {slice_size}')
            elif slice_size < value_size:
                # Enlarge: insert excess, overwrite existing
                if step is None:
                    self.insert(endex, value[slice_size:])
                    self.write(start, value[:slice_size])
                else:
                    raise ValueError(f'attempt to assign bytes of size {value_size}'
                                     f' to extended slice of size {slice_size}')
            else:
                # Same size: overwrite existing
                if step is None:
                    self.write(start, value)
                else:
                    for offset, item in enumerate(value):
                        self.poke(start + (step * offset), item)
        else:
            self.poke(key.__index__(), value)

    def __str__(
        self,
    ) -> str:
        r"""String representation.

        If :attr:`content_size` is lesser than ``STR_MAX_CONTENT_SIZE``, then
        the memory is represented as a list of blocks.

        If exceeding, it is equivalent to :meth:`__repr__`.


        Returns:
            str: String representation.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [7, b'xyz']])
            >>> str(memory)
            <[[1, b'ABC'], [7, b'xyz']]>
        """

        if self.content_size < STR_MAX_CONTENT_SIZE:
            trim_start = '' if self._trim_start is None else f'{self._trim_start}, '
            trim_endex = '' if self._trim_endex is None else f', {self._trim_endex}'

            inner = ', '.join(f'[{block_start}, b{block_data.decode()!r}]'
                              for block_start, block_data in self._blocks)

            return f'<{trim_start}[{inner}]{trim_endex}>'
        else:
            return repr(self)

    def _block_index_at(
        self,
        address: Address,
    ) -> Optional[BlockIndex]:
        r"""Locates the block enclosing an address.

        Returns the index of the block enclosing the given address.

        Arguments:
            address (int):
                Address of the target item.

        Returns:
            int: Block index if found, ``None`` otherwise.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   | 0 | 0 | 0 | 0 |   | 1 |   | 2 | 2 | 2 |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> [memory._block_index_at(i) for i in range(12)]
            [None, 0, 0, 0, 0, None, 1, None, 2, 2, 2, None]
        """

        blocks = self._blocks
        if blocks:
            if address < blocks[0][0]:
                return None

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:
                return None
        else:
            return None

        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:
                left = center + 1
            elif address < block_start:
                right = center - 1
            else:
                return center
        else:
            return None

    def _block_index_endex(
        self,
        address: Address,
    ) -> BlockIndex:
        r"""Locates the first block after an address range.

        Returns the index of the first block whose end address is lesser than or
        equal to `address`.

        Useful to find the termination block index in a ranged search.

        Arguments:
            address (int):
                Exclusive end address of the scanned range.

        Returns:
            int: First block index after `address`.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 3 | 3 | 3 | 3 |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> [memory._block_index_endex(i) for i in range(12)]
            [0, 1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 3]
        """

        blocks = self._blocks
        if blocks:
            if address < blocks[0][0]:
                return 0

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:
                return len(blocks)
        else:
            return 0

        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:
                left = center + 1
            elif address < block_start:
                right = center - 1
            else:
                return center + 1
        else:
            return right + 1

    def _block_index_start(
        self,
        address: Address,
    ) -> BlockIndex:
        r"""Locates the first block inside of an address range.

        Returns the index of the first block whose start address is greater than
        or equal to `address`.

        Useful to find the initial block index in a ranged search.

        Arguments:
            address (int):
                Inclusive start address of the scanned range.

        Returns:
            int: First block index since `address`.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 2 | 2 | 2 | 2 | 3 |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> [memory._block_index_start(i) for i in range(12)]
            [0, 0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 3]
        """

        blocks = self._blocks
        if blocks:
            if address <= blocks[0][0]:
                return 0

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:
                return len(blocks)
        else:
            return 0

        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:
                left = center + 1
            elif address < block_start:
                right = center - 1
            else:
                return center
        else:
            return left

    def _erase(
        self,
        start: Address,
        endex: Address,
        shift_after: bool,
    ) -> None:
        r"""Erases an address range.

        Low-level method to erase data within the underlying data structure.

        Arguments:
            start (int):
                Start address of the erasure range.

            endex (int):
                Exclusive end address of the erasure range.

            shift_after (bool):
                Shifts addresses of blocks after the end of the range,
                subtracting the size of the range itself.
                If data blocks before and after the address range are
                contiguous after erasure, merge the two blocks together.
        """

        size = endex - start
        if size > 0:
            blocks = self._blocks
            block_index = self._block_index_start(start)

            # Delete final/inner part of deletion start block
            if block_index < len(blocks):
                block_start, block_data = blocks[block_index]
                if start > block_start:
                    if shift_after:
                        del block_data[(start - block_start):(endex - block_start)]
                    else:
                        block_data = block_data[:(start - block_start)]
                        blocks.insert(block_index, [block_start, block_data])
                    block_index += 1  # skip this from inner part

            # Delete initial part of deletion end block
            inner_start = block_index
            for block_index in range(block_index, len(blocks)):
                block_start, block_data = blocks[block_index]
                if endex <= block_start:
                    break  # inner ends before here

                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    offset = endex - block_start
                    del block_data[:offset]
                    blocks[block_index][0] += offset  # update address
                    break  # inner ends before here
            else:
                block_index = len(blocks)
            inner_endex = block_index

            if shift_after:
                # Check if inner deletion can be merged
                if inner_start and inner_endex < len(blocks):
                    block_start, block_data = blocks[inner_start - 1]
                    block_endex = block_start + len(block_data)
                    block_start2, block_data2 = blocks[inner_endex]

                    if block_endex + size == block_start2:
                        block_data += block_data2  # merge deletion boundaries
                        inner_endex += 1  # add to inner deletion
                        block_index += 1  # skip address update

                # Shift blocks after deletion
                for block_index in range(block_index, len(blocks)):
                    blocks[block_index][0] -= size  # update address

            # Delete inner full blocks
            if inner_start < inner_endex:
                del blocks[inner_start:inner_endex]

    def _place(
        self,
        address: Address,
        data: bytearray,
        shift_after: bool,
    ) -> None:
        r"""Inserts data.

        Low-level method to insert data into the underlying data structure.

        Arguments:
            address (int):
                Address of the insertion point.

            data (:obj:`bytearray`):
                Data to insert.

            shift_after (bool):
                Shifts the addresses of blocks after the insertion point,
                adding the size of the inserted data.
        """

        size = len(data)
        if size:
            blocks = self._blocks
            block_index = self._block_index_start(address)

            if block_index:
                block_start, block_data = blocks[block_index - 1]
                block_endex = block_start + len(block_data)

                if block_endex == address:
                    # Extend previous block
                    block_data += data

                    # Shift blocks after
                    if shift_after:
                        for block_index in range(block_index, len(blocks)):
                            blocks[block_index][0] += size
                    else:
                        if block_index < len(blocks):
                            block_endex += size
                            block_start2, block_data2 = blocks[block_index]

                            # Merge with next block
                            if block_endex == block_start2:
                                block_data += block_data2
                                blocks.pop(block_index)
                    return

            if block_index < len(blocks):
                block_start, block_data = blocks[block_index]

                if address < block_start:
                    if shift_after:
                        # Insert a standalone block before
                        blocks.insert(block_index, [address, data])
                    else:
                        if address + len(data) == block_start:
                            # Merge with next block
                            blocks[block_index][0] = address
                            block_data[0:0] = data
                        else:
                            # Insert a standalone block before
                            blocks.insert(block_index, [address, data])
                else:
                    # Insert data into the current block
                    offset = address - block_start
                    block_data[offset:offset] = data

                # Shift blocks after
                if shift_after:
                    for block_index in range(block_index + 1, len(blocks)):
                        blocks[block_index][0] += size

            else:
                # Append a standalone block after
                blocks.append([address, data[:]])

    def _pretrim_endex(
        self,
        start_min: Optional[Address],
        size: Address,
    ) -> None:
        r"""Trims final data.

        Low-level method to manage trimming of data starting from an address.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`trim_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

        See Also:
            :meth:`_pretrim_endex_backup`
        """

        trim_endex = self._trim_endex
        if trim_endex is not None and size > 0:
            start = trim_endex - size

            if start_min is not None and start < start_min:
                start = start_min

            self._erase(start, self.content_endex, False)  # clear

    def _pretrim_endex_backup(
        self,
        start_min: Optional[Address],
        size: Address,
    ) -> ImmutableMemory:
        r"""Backups a `_pretrim_endex()` operation.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`trim_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`Memory`: Backup memory region.

        See Also:
            :meth:`_pretrim_endex`
        """

        trim_endex = self._trim_endex
        if trim_endex is not None and size > 0:
            start = trim_endex - size
            if start_min is not None and start < start_min:
                start = start_min
            return self.extract(start, None)
        else:
            return self.__class__()

    def _pretrim_start(
        self,
        endex_max: Optional[Address],
        size: Address,
    ) -> None:
        r"""Trims initial data.

        Low-level method to manage trimming of data starting from an address.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`trim_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

        See Also:
            :meth:`_pretrim_start_backup`
        """

        trim_start = self._trim_start
        if trim_start is not None and size > 0:
            endex = trim_start + size

            if endex_max is not None and endex > endex_max:
                endex = endex_max

            self._erase(self.content_start, endex, False)  # clear

    def _pretrim_start_backup(
        self,
        endex_max: Optional[Address],
        size: Address,
    ) -> ImmutableMemory:
        r"""Backups a `_pretrim_start()` operation.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`trim_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`Memory`: Backup memory region.

        See Also:
            :meth:`_pretrim_start`
        """

        trim_start = self._trim_start
        if trim_start is not None and size > 0:
            endex = trim_start + size
            if endex_max is not None and endex > endex_max:
                endex = endex_max
            return self.extract(None, endex)
        else:
            return self.__class__()

    def append(
        self,
        item: Union[AnyBytes, Value],
    ) -> None:
        r"""Appends a single item.

        Arguments:
            item (int):
                Value to append. Can be a single byte string or integer.

        Examples:
            >>> memory = Memory()
            >>> memory.append(b'$')
            >>> memory.to_blocks()
            [[0, b'$']]

            ~~~

            >>> memory = Memory()
            >>> memory.append(3)
            >>> memory.to_blocks()
            [[0, b'\x03']]

        See Also:
            :meth:`append_backup`
            :meth:`append_restore`
        """

        if not isinstance(item, Value):
            if len(item) != 1:
                raise ValueError('expecting single item')
            item = item[0]

        blocks = self._blocks
        if blocks:
            blocks[-1][1].append(item)
        else:
            blocks.append([0, bytearray((item,))])

    # noinspection PyMethodMayBeStatic
    def append_backup(
        self,
    ) -> None:
        r"""Backups an `append()` operation.

        Returns:
            None: Nothing.

        See Also:
            :meth:`append`
            :meth:`append_restore`
        """

        return None

    def append_restore(
        self,
    ) -> None:
        r"""Restores an `append()` operation.

        See Also:
            :meth:`append`
            :meth:`append_backup`
        """

        self.pop()

    def block_span(
        self,
        address: Address,
    ) -> Tuple[Optional[Address], Optional[Address], Optional[Value]]:
        r"""Span of block data.

        It searches for the biggest chunk of data adjacent to the given
        address.

        If the address is within a gap, its bounds are returned, and its
        value is ``None``.

        If the address is before or after any data, bounds are ``None``.

        Arguments:
            address (int):
                Reference address.

        Returns:
            tuple: Start bound, exclusive end bound, and reference value.

        Examples:
            >>> memory = Memory()
            >>> memory.block_span(0)
            (None, None, None)

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |[A | B | B | B | C]|   |   |[C | C | D]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            | 65| 66| 66| 66| 67|   |   | 67| 67| 68|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[0, b'ABBBC'], [7, b'CCD']])
            >>> memory.block_span(2)
            (0, 5, 66)
            >>> memory.block_span(4)
            (0, 5, 67)
            >>> memory.block_span(5)
            (5, 7, None)
            >>> memory.block_span(10)
            (10, None, None)
        """

        block_index = self._block_index_start(address)
        blocks = self._blocks

        if block_index < len(blocks):
            block_start, block_data = blocks[block_index]
            block_endex = block_start + len(block_data)

            if block_start <= address < block_endex:
                # Address within a block
                value = block_data[address - block_start]
                return block_start, block_endex, value  # block span

            elif block_index:
                # Address within a gap
                block_endex = block_start  # end gap before next block
                block_start, block_data = blocks[block_index - 1]
                block_start += len(block_data)  # start gap after previous block
                return block_start, block_endex, None  # gap span

            else:
                # Address before content
                return None, block_start, None  # open left

        else:
            # Address after content
            if blocks:
                block_start, block_data = blocks[-1]
                block_endex = block_start + len(block_data)
                return block_endex, None, None  # open right

            else:
                return None, None, None  # fully open

    def blocks(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[Tuple[Address, Union[memoryview, bytearray]]]:
        r"""Iterates over blocks.

        Iterates over data blocks within an address range.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            (start, memoryview): Start and data view of each block/slice.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'AB'], [5, b'x'], [7, b'123']])
            >>> [[s, bytes(d)] for s, d in memory.blocks()]
            [[1, b'AB'], [5, b'x'], [7, b'123']]
            >>> [[s, bytes(d)] for s, d in memory.blocks(2, 9)]
            [[2, b'B'], [5, b'x'], [7, b'12']]
            >>> [[s, bytes(d)] for s, d in memory.blocks(3, 5)]
            []

        See Also:
            :meth:`intervals`
            :meth:`to_blocks`
        """

        blocks = self._blocks
        if blocks:
            if start is None and endex is None:  # faster
                yield from blocks

            else:
                block_index_start = 0 if start is None else self._block_index_start(start)
                block_index_endex = len(blocks) if endex is None else self._block_index_endex(endex)
                start, endex = self.bound(start, endex)
                block_iterator = _islice(blocks, block_index_start, block_index_endex)

                for block_start, block_data in block_iterator:
                    block_endex = block_start + len(block_data)
                    slice_start = block_start if start < block_start else start
                    slice_endex = endex if endex < block_endex else block_endex
                    if slice_start < slice_endex:
                        slice_view = memoryview(block_data)
                        slice_view = slice_view[(slice_start - block_start):(slice_endex - block_start)]
                        yield slice_start, slice_view

    def bound(
        self,
        start: Optional[Address],
        endex: Optional[Address],
    ) -> ClosedInterval:
        r"""Bounds addresses.

        It bounds the given addresses to stay within memory limits.
        ``None`` is used to ignore a limit for the `start` or `endex`
        directions.

        In case of stored data, :attr:`content_start` and
        :attr:`content_endex` are used as bounds.

        In case of trimming limits, :attr:`trim_start` or :attr:`trim_endex`
        are used as bounds, when not ``None``.

        In case `start` and `endex` are in the wrong order, one clamps
        the other if present (see the Python implementation for details).

        Returns:
            tuple of int: Bounded `start` and `endex`, closed interval.

        Examples:
            >>> Memory().bound(None, None)
            (0, 0)
            >>> Memory().bound(None, 100)
            (0, 100)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.bound(0, 30)
            (0, 30)
            >>> memory.bound(2, 6)
            (2, 6)
            >>> memory.bound(None, 6)
            (1, 6)
            >>> memory.bound(2, None)
            (2, 8)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |[A | B | C]|   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[3, b'ABC']], start=1, endex=8)
            >>> memory.bound(None, None)
            (1, 8)
            >>> memory.bound(0, 30)
            (1, 8)
            >>> memory.bound(2, 6)
            (2, 6)
            >>> memory.bound(2, None)
            (2, 8)
            >>> memory.bound(None, 6)
            (1, 6)
        """

        blocks = self._blocks
        trim_start = self._trim_start
        trim_endex = self._trim_endex

        if start is None:
            if trim_start is None:
                if blocks:
                    start = blocks[0][0]
                else:
                    start = 0
            else:
                start = trim_start
        else:
            if trim_start is not None:
                if start < trim_start:
                    start = trim_start
            if endex is not None:
                if endex < start:
                    endex = start

        if endex is None:
            if trim_endex is None:
                if blocks:
                    block_start, block_data = blocks[-1]
                    endex = block_start + len(block_data)
                else:
                    endex = start
            else:
                endex = trim_endex
        else:
            if trim_endex is not None:
                if endex > trim_endex:
                    endex = trim_endex
            if start > endex:
                start = endex

        return start, endex

    def clear(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:
        r"""Clears an address range.

        Arguments:
            start (int):
                Inclusive start address for clearing.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for clearing.
                If ``None``, :attr:`endex` is considered.

        Example:
            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory.clear(6, 10)
            >>> memory.to_blocks()
            [[5, b'A'], [10, b'yz']]

        See Also:
            :meth:`clear_backup`
            :meth:`clear_restore`
        """

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        if start < endex:
            self._erase(start, endex, False)  # clear

    def clear_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:
        r"""Backups a `clear()` operation.

        Arguments:
            start (int):
                Inclusive start address for clearing.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for clearing.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`Memory`: Backup memory region.

        See Also:
            :meth:`clear`
            :meth:`clear_restore`
        """

        return self.extract(start, endex)

    def clear_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `clear()` operation.

        Arguments:
            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`clear`
            :meth:`clear_backup`
        """

        self.write(0, backup, clear=True)

    @ImmutableMemory.content_endex.getter
    def content_endex(
        self,
    ) -> Address:
        r"""int: Exclusive content end address.

        This property holds the exclusive end address of the memory content.
        By default, it is the current maximmum exclusive end address of
        the last stored block.

        If the memory has no data and no trimming, :attr:`start` is returned.

        Trimming is considered only for an empty memory.

        Examples:
            >>> Memory().content_endex
            0
            >>> Memory(endex=8).content_endex
            0
            >>> Memory(start=1, endex=8).content_endex
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.content_endex
            4
        """

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            return block_start + len(block_data)
        elif self._trim_start is None:  # default to start
            return 0
        else:
            return self._trim_start  # default to start

    @ImmutableMemory.content_endin.getter
    def content_endin(
        self,
    ) -> Address:
        r"""int: Inclusive content end address.

        This property holds the inclusive end address of the memory content.
        By default, it is the current maximmum inclusive end address of
        the last stored block.

        If the memory has no data and no trimming, :attr:`start` minus one is
        returned.

        Trimming is considered only for an empty memory.

        Examples:
            >>> Memory().content_endin
            -1
            >>> Memory(endex=8).content_endin
            -1
            >>> Memory(start=1, endex=8).content_endin
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.content_endin
            3
        """

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            return block_start + len(block_data) - 1
        elif self._trim_start is None:  # default to start-1
            return -1
        else:
            return self._trim_start - 1  # default to start-1

    @ImmutableMemory.content_parts.getter
    def content_parts(
        self,
    ) -> int:
        r"""Number of blocks.

        Returns:
            int: The number of blocks.

        Examples:
            >>> Memory().content_parts
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_parts
            2

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.content_parts
            1
        """

        return len(self._blocks)

    @ImmutableMemory.content_size.getter
    def content_size(
        self,
    ) -> Address:
        r"""Actual content size.

        Returns:
            int: The sum of all block lengths.

        Examples:
            >>> Memory().content_size
            0
            >>> Memory(start=1, endex=8).content_size
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_size
            6

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.content_size
            3
        """

        return sum(len(block_data) for _, block_data in self._blocks)

    @ImmutableMemory.content_span.getter
    def content_span(
        self,
    ) -> ClosedInterval:
        r"""tuple of int: Memory content address span.

        A :attr:`tuple` holding both :attr:`content_start` and
        :attr:`content_endex`.

        Examples:
            >>> Memory().content_span
            (0, 0)
            >>> Memory(start=1).content_span
            (1, 1)
            >>> Memory(endex=8).content_span
            (0, 0)
            >>> Memory(start=1, endex=8).content_span
            (1, 1)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_span
            (1, 8)
        """

        return self.content_start, self.content_endex

    @ImmutableMemory.content_start.getter
    def content_start(
        self,
    ) -> Address:
        r"""int: Inclusive content start address.

        This property holds the inclusive start address of the memory content.
        By default, it is the current minimum inclusive start address of
        the first stored block.

        If the memory has no data and no trimming, 0 is returned.

        Trimming is considered only for an empty memory.

        Examples:
            >>> Memory().content_start
            0
            >>> Memory(start=1).content_start
            1
            >>> Memory(start=1, endex=8).content_start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'xyz']], start=1)
            >>> memory.content_start
            5
        """

        blocks = self._blocks
        if blocks:
            return blocks[0][0]
        elif self._trim_start is None:
            return 0
        else:
            return self._trim_start

    @ImmutableMemory.contiguous.getter
    def contiguous(
        self,
    ) -> bool:
        r"""bool: Contains contiguous data.

        The memory is considered to have contiguous data if there is no empty
        space between blocks.

        If trimming is defined, there must be no empty space also towards it.
        """

        start = self.start
        endex = self.endex

        if start < endex:
            block_index = self._block_index_at(start)

            if block_index is not None:
                block_start, block_data = self._blocks[block_index]

                if endex <= block_start + len(block_data):
                    return True

            return False
        else:
            return True

    def count(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> int:
        r"""Counts items.

        Arguments:
            item (items):
                Reference value to count.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The number of items equal to `value`.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[B | a | t]|   |[t | a | b]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'Bat'], [9, b'tab']])
            >>> memory.count(b'a')
            2
        """

        # Faster code for unbounded slice
        if start is None and endex is None:
            return sum(block_data.count(item) for _, block_data in self._blocks)

        # Bounded slice
        count = 0
        start, endex = self.bound(start, endex)
        block_index_start = self._block_index_start(start)
        block_index_endex = self._block_index_endex(endex)
        block_iterator = _islice(self._blocks, block_index_start, block_index_endex)

        for block_start, block_data in block_iterator:
            slice_start = start - block_start
            if slice_start < 0:
                slice_start = 0

            slice_endex = endex - block_start
            # if slice_endex < slice_start:
            #     slice_endex = slice_start

            count += block_data.count(item, slice_start, slice_endex)
        return count

    def copy(
        self,
    ) -> 'Memory':
        r"""Creates a shallow copy.

        Returns:
            :obj:`Memory`: Shallow copy.
        """

        return self.__copy__()

    def crop(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:
        r"""Keeps data within an address range.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

        Example:
            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |[B | C]|   |[x]|   |   |   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory.crop(6, 10)
            >>> memory.to_blocks()
            [[6, b'BC'], [9, b'x']]

        See Also:
            :meth:`crop_backup`
            :meth:`crop_restore`
        """

        blocks = self._blocks  # may change during execution

        # Trim blocks exceeding before memory start
        if start is not None and blocks:
            block_start = blocks[0][0]

            if block_start < start:
                self._erase(block_start, start, False)  # clear

        # Trim blocks exceeding after memory end
        if endex is not None and blocks:
            block_start, block_data = blocks[-1]
            block_endex = block_start + len(block_data)

            if endex < block_endex:
                self._erase(endex, block_endex, False)  # clear

    def crop_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Tuple[Optional[ImmutableMemory], Optional[ImmutableMemory]]:
        r"""Backups a `crop()` operation.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`Memory` couple: Backup memory regions.

        See Also:
            :meth:`crop`
            :meth:`crop_restore`
        """

        backup_start = None
        backup_endex = None

        blocks = self._blocks  # may change
        if blocks:
            if start is not None:
                block_start = blocks[0][0]
                if block_start < start:
                    backup_start = self.extract(block_start, start)

            if endex is not None:
                block_start, block_data = blocks[-1]
                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    backup_endex = self.extract(endex, block_endex)

        return backup_start, backup_endex

    def crop_restore(
        self,
        backup_start: Optional[ImmutableMemory],
        backup_endex: Optional[ImmutableMemory],
    ) -> None:
        r"""Restores a `crop()` operation.

        Arguments:
            backup_start (:obj:`Memory`):
                Backup memory region to restore at the beginning.

            backup_endex (:obj:`Memory`):
                Backup memory region to restore at the end.

        See Also:
            :meth:`crop`
            :meth:`crop_backup`
        """

        if backup_start is not None:
            self.write(0, backup_start, clear=True)
        if backup_endex is not None:
            self.write(0, backup_endex, clear=True)

    def cut(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        bound: bool = True,
    ) -> 'Memory':
        r"""Cuts a slice of memory.

        Arguments:
            start (int):
                Inclusive start address for cutting.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cutting.
                If ``None``, :attr:`endex` is considered.

            bound (bool):
                The selected address range is applied to the resulting memory
                as its trimming range. This retains information about any
                initial and final emptiness of that range, which would be lost
                otherwise.

        Returns:
            :obj:`Memory`: A copy of the memory from the selected range.
        """

        start_ = start
        endex_ = endex
        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex
        if endex < start:
            endex = start

        memory = self.__class__()
        blocks = self._blocks

        if start < endex and blocks:
            # Copy all the blocks except those completely outside selection
            block_index_start = 0 if start_ is None else self._block_index_start(start)
            block_index_endex = len(blocks) if endex_ is None else self._block_index_endex(endex)

            if block_index_start < block_index_endex:
                memory_blocks = _islice(blocks, block_index_start, block_index_endex)
                memory_blocks = [[block_start, block_data]
                                 for block_start, block_data in memory_blocks]

                # Trim cloned data before the selection start address
                block_start, block_data = memory_blocks[0]
                if block_start < start:
                    memory_blocks[0] = [start, block_data[(start - block_start):]]

                # Trim cloned data after the selection end address
                block_start, block_data = memory_blocks[-1]
                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    if block_start < endex:
                        memory_blocks[-1] = [block_start, block_data[:(endex - block_start)]]
                    else:
                        memory_blocks.pop()

                memory._blocks = memory_blocks
                self._erase(start, endex, False)  # clear

        if bound:
            memory._trim_start = start
            memory._trim_endex = endex

        return memory

    def delete(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:
        r"""Deletes an address range.

        Arguments:
            start (int):
                Inclusive start address for deletion.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for deletion.
                If ``None``, :attr:`endex` is considered.

        Example:
            +---+---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12| 13|
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | y | z]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory.delete(6, 10)
            >>> memory.to_blocks()
            [[5, b'Ayz']]

        See Also:
            :meth:`delete_backup`
            :meth:`delete_restore`
        """

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        if start < endex:
            self._erase(start, endex, True)  # delete

    def delete_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:
        r"""Backups a `delete()` operation.

        Arguments:
            start (int):
                Inclusive start address for deletion.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for deletion.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`Memory`: Backup memory region.

        See Also:
            :meth:`delete`
            :meth:`delete_restore`
        """

        return self.extract(start, endex)

    def delete_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `delete()` operation.

        Arguments:
            backup (:obj:`Memory`):
                Backup memory region.

        See Also:
            :meth:`delete`
            :meth:`delete_backup`
        """

        self.reserve(backup.start, len(backup))
        self.write(0, backup)

    @ImmutableMemory.endex.getter
    def endex(
        self,
    ) -> Address:
        r"""int: Exclusive end address.

        This property holds the exclusive end address of the virtual space.
        By default, it is the current maximmum exclusive end address of
        the last stored block.

        If  :attr:`trim_endex` not ``None``, that is returned.

        If the memory has no data and no trimming, :attr:`start` is returned.

        Examples:
            >>> Memory().endex
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.endex
            8
        """

        trim_endex = self._trim_endex
        if trim_endex is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                block_start, block_data = blocks[-1]
                return block_start + len(block_data)
            else:
                return self.start
        else:
            return trim_endex

    @ImmutableMemory.endin.getter
    def endin(
        self,
    ) -> Address:
        r"""int: Inclusive end address.

        This property holds the inclusive end address of the virtual space.
        By default, it is the current maximmum inclusive end address of
        the last stored block.

        If  :attr:`trim_endex` not ``None``, that minus one is returned.

        If the memory has no data and no trimming, :attr:`start` is returned.

        Examples:
            >>> Memory().endin
            -1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC']], endex=8)
            >>> memory.endin
            7
        """

        trim_endex = self._trim_endex
        if trim_endex is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                block_start, block_data = blocks[-1]
                return block_start + len(block_data) - 1
            else:
                return self.start - 1
        else:
            return trim_endex - 1

    def equal_span(
        self,
        address: Address,
    ) -> Tuple[Optional[Address], Optional[Address], Optional[Value]]:
        r"""Span of homogeneous data.

        It searches for the biggest chunk of data adjacent to the given
        address, with the same value at that address.

        If the address is within a gap, its bounds are returned, and its
        value is ``None``.

        If the address is before or after any data, bounds are ``None``.

        Arguments:
            address (int):
                Reference address.

        Returns:
            tuple: Start bound, exclusive end bound, and reference value.

        Examples:
            >>> memory = Memory()
            >>> memory.equal_span(0)
            (None, None, None)

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |[A | B | B | B | C]|   |   |[C | C | D]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            | 65| 66| 66| 66| 67|   |   | 67| 67| 68|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[0, b'ABBBC'], [7, b'CCD']])
            >>> memory.equal_span(2)
            (1, 4, 66)
            >>> memory.equal_span(4)
            (4, 5, 67)
            >>> memory.equal_span(5)
            (5, 7, None)
            >>> memory.equal_span(10)
            (10, None, None)
        """

        block_index = self._block_index_start(address)
        blocks = self._blocks

        if block_index < len(blocks):
            block_start, block_data = blocks[block_index]
            block_endex = block_start + len(block_data)

            if block_start <= address < block_endex:
                # Address within a block
                offset = address - block_start
                start = offset
                endex = offset + 1
                value = block_data[offset]

                for start in range(start, -1, -1):
                    if block_data[start] != value:
                        start += 1
                        break
                else:
                    start = 0

                for endex in range(endex, len(block_data)):
                    if block_data[endex] != value:
                        break
                else:
                    endex = len(block_data)

                block_endex = block_start + endex
                block_start = block_start + start
                return block_start, block_endex, value  # equal data span

            elif block_index:
                # Address within a gap
                block_endex = block_start  # end gap before next block
                block_start, block_data = blocks[block_index - 1]
                block_start += len(block_data)  # start gap after previous block
                return block_start, block_endex, None  # gap span

            else:
                # Address before content
                return None, block_start, None  # open left

        else:
            # Address after content
            if blocks:
                block_start, block_data = blocks[-1]
                block_endex = block_start + len(block_data)
                return block_endex, None, None  # open right

            else:
                return None, None, None  # fully open

    def extend(
        self,
        items: Union[AnyBytes, ImmutableMemory],
        offset: Address = 0,
    ) -> None:
        r"""Concatenates items.

        Equivalent to ``self += items``.

        Arguments:
            items (items):
                Items to append at the end of the current virtual space.

            offset (int):
                Optional offset w.r.t. :attr:`content_endex`.

        See Also:
            :meth:`extend_backup`
            :meth:`extend_restore`
        """

        if offset < 0:
            raise ValueError('negative extension offset')
        self.write(self.content_endex + offset, items)

    def extend_backup(
        self,
        offset: Address = 0,
    ) -> Address:
        r"""Backups an `extend()` operation.

        Arguments:
            offset (int):
                Optional offset w.r.t. :attr:`content_endex`.

        Returns:
            int: Content exclusive end address.

        See Also:
            :meth:`extend`
            :meth:`extend_restore`
        """

        if offset < 0:
            raise ValueError('negative extension offset')
        return self.content_endex + offset

    def extend_restore(
        self,
        content_endex: Address,
    ) -> None:
        r"""Restores an `extend()` operation.

        Arguments:
            content_endex (int):
                Content exclusive end address to restore.

        See Also:
            :meth:`extend`
            :meth:`extend_backup`
        """

        self.clear(content_endex)

    def extract(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
        step: Optional[Address] = None,
        bound: bool = True,
    ) -> 'Memory':
        r"""Selects items from a range.

        Arguments:
            start (int):
                Inclusive start of the extracted range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the extracted range.
                If ``None``, :attr:`endex` is considered.

            pattern (items):
                Optional pattern of items to fill the emptiness.

            step (int):
                Optional address stepping between bytes extracted from the
                range. It has the same meaning of Python's :attr:`slice.step`,
                but negative steps are ignored.
                Please note that a `step` greater than 1 could take much more
                time to process than the default unitary step.

            bound (bool):
                The selected address range is applied to the resulting memory
                as its trimming range. This retains information about any
                initial and final emptiness of that range, which would be lost
                otherwise.

        Returns:
            :obj:`Memory`: A copy of the memory from the selected range.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.extract()._blocks
            [[1, b'ABCD'], [6, b'$'], [8, b'xyz']]
            >>> memory.extract(2, 9)._blocks
            [[2, b'BCD'], [6, b'$'], [8, b'x']]
            >>> memory.extract(start=2)._blocks
            [[2, b'BCD'], [6, b'$'], [8, b'xyz']]
            >>> memory.extract(endex=9)._blocks
            [[1, b'ABCD'], [6, b'$'], [8, b'x']]
            >>> memory.extract(5, 8).span
            (5, 8)
            >>> memory.extract(pattern=b'.')._blocks
            [[1, b'ABCD.$.xyz']]
            >>> memory.extract(pattern=b'.', step=3)._blocks
            [[1, b'AD.z']]
        """

        start_ = start
        endex_ = endex
        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex
        if endex < start:
            endex = start
        memory = self.__class__()

        if step is None or step == 1:
            blocks = self._blocks

            if start < endex and blocks:
                # Copy all the blocks except those completely outside selection
                block_index_start = 0 if start_ is None else self._block_index_start(start)
                block_index_endex = len(blocks) if endex_ is None else self._block_index_endex(endex)

                if block_index_start < block_index_endex:
                    memory_blocks = _islice(blocks, block_index_start, block_index_endex)
                    memory_blocks = [[block_start, bytearray(block_data)]
                                     for block_start, block_data in memory_blocks]

                    # Trim cloned data before the selection start address
                    block_start, block_data = memory_blocks[0]
                    if block_start < start:
                        del block_data[:(start - block_start)]
                        memory_blocks[0] = [start, block_data]

                    # Trim cloned data after the selection end address
                    block_start, block_data = memory_blocks[-1]
                    block_endex = block_start + len(block_data)
                    if endex < block_endex:
                        if block_start < endex:
                            del block_data[(endex - block_start):]
                            memory_blocks[-1] = [block_start, block_data]
                        else:
                            memory_blocks.pop()

                    memory._blocks = memory_blocks

                if pattern is not None:
                    memory.flood(start, endex, pattern)
        else:
            step = int(step)
            if step > 1:
                memory_blocks = []
                block_start = None
                block_data = None
                offset = start

                for value in _islice(self.values(start, endex, pattern), 0, endex - start, step):
                    if value is None:
                        if block_start is not None:
                            memory_blocks.append([block_start, block_data])
                            block_start = None
                    else:
                        if block_start is None:
                            block_start = offset
                            block_data = bytearray()
                        block_data.append(value)
                    offset += 1

                if block_start is not None:
                    memory_blocks.append([block_start, block_data])

                memory._blocks = memory_blocks
                if bound:
                    endex = offset

        if bound:
            memory._trim_start = start
            memory._trim_endex = endex

        return memory

    def fill(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:
        r"""Overwrites a range with a pattern.

        Arguments:
            start (int):
                Inclusive start address for filling.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for filling.
                If ``None``, :attr:`endex` is considered.

            pattern (items):
                Pattern of items to fill the range.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[1 | 2 | 3 | 1 | 2 | 3 | 1 | 2]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.fill(pattern=b'123')
            >>> memory.to_blocks()
            [[1, b'12312312']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | 1 | 2 | 3 | 1 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.fill(3, 7, b'123')
            >>> memory.to_blocks()
            [[1, b'AB1231yz']]

        See Also:
            :meth:`fill_backup`
            :meth:`fill_restore`
        """

        start_ = start
        start, endex = self.bound(start, endex)
        if start < endex:
            if isinstance(pattern, Value):
                pattern = bytearray((pattern,))
                pattern_size = len(pattern)
            else:
                pattern_size = len(pattern)
                if not pattern_size:
                    raise ValueError('non-empty pattern required')
                pattern = bytearray(pattern)
                if start_ is not None and start > start_:
                    offset = (start - start_) % pattern_size
                    pattern = pattern[offset:] + pattern[:offset]  # rotate

            # Resize the pattern to the target range
            size = endex - start
            if pattern_size < size:
                pattern *= (size + (pattern_size - 1)) // pattern_size
            del pattern[size:]

            # Standard write method
            self._erase(start, endex, False)  # clear
            self._place(start, pattern, False)  # write

    def fill_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:
        r"""Backups a `fill()` operation.

        Arguments:
            start (int):
                Inclusive start address for filling.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for filling.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`Memory`: Backup memory region.

        See Also:
            :meth:`fill`
            :meth:`fill_restore`
        """

        return self.extract(start, endex)

    def fill_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `fill()` operation.

        Arguments:
            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`fill`
            :meth:`fill_backup`
        """

        self.write(0, backup, clear=True)

    def find(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:
        r"""Index of an item.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`endex` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the first item equal to `value`, or -1.
        """

        try:
            return self.index(item, start, endex)
        except ValueError:
            return -1

    def flood(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:
        r"""Fills emptiness between non-touching blocks.

        Arguments:
            start (int):
                Inclusive start address for flooding.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for flooding.
                If ``None``, :attr:`endex` is considered.

            pattern (items):
                Pattern of items to fill the range.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 1 | 2 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.flood(pattern=b'123')
            >>> memory.to_blocks()
            [[1, b'ABC12xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 2 | 3 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.flood(3, 7, b'123')
            >>> memory.to_blocks()
            [[1, b'ABC23xyz']]

        See Also:
            :meth:`flood_backup`
            :meth:`flood_restore`
        """

        start, endex = self.bound(start, endex)
        if start < endex:
            if isinstance(pattern, Value):
                pattern = (pattern,)
            else:
                if not pattern:
                    raise ValueError('non-empty pattern required')
            pattern = bytearray(pattern)
            pattern_size = len(pattern)

            blocks = self._blocks
            block_index_start = self._block_index_start(start)

            # Check if touching previous block
            if block_index_start:
                block_start, block_data = blocks[block_index_start - 1]
                block_endex = block_start + len(block_data)
                if block_endex == start:
                    block_index_start -= 1

            # Manage block near start
            if block_index_start < len(blocks):
                block_start, block_data = blocks[block_index_start]
                block_endex = block_start + len(block_data)

                if block_start <= start and endex <= block_endex:
                    return  # no emptiness to flood

                if block_start < start:
                    offset = (block_start - start) % pattern_size
                    pattern = pattern[offset:] + pattern[:offset]  # rotate
                    start = block_start

            # Manage block near end
            block_index_endex = self._block_index_endex(endex)
            if block_index_start < block_index_endex:
                block_start, block_data = blocks[block_index_endex - 1]
                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    endex = block_endex

            size = endex - start
            pattern *= (size + (pattern_size - 1)) // pattern_size
            del pattern[size:]

            blocks_inner = blocks[block_index_start:block_index_endex]
            blocks[block_index_start:block_index_endex] = [[start, pattern]]

            for block_start, block_data in blocks_inner:
                block_endex = block_start + len(block_data)
                pattern[(block_start - start):(block_endex - start)] = block_data

    def flood_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> List[OpenInterval]:
        r"""Backups a `flood()` operation.

        Arguments:
            start (int):
                Inclusive start address for filling.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for filling.
                If ``None``, :attr:`endex` is considered.

        Returns:
            list of open intervals: Backup memory gaps.

        See Also:
            :meth:`flood`
            :meth:`flood_restore`
        """

        return list(self.gaps(start, endex))

    def flood_restore(
        self,
        gaps: List[OpenInterval],
    ) -> None:
        r"""Restores a `flood()` operation.

        Arguments:
            gaps (list of open intervals):
                Backup memory gaps to restore.

        See Also:
            :meth:`flood`
            :meth:`flood_backup`
        """

        for gap_start, gap_endex in gaps:
            self.clear(gap_start, gap_endex)

    @classmethod
    def from_blocks(
        cls,
        blocks: BlockSequence,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':
        r"""Creates a virtual memory from blocks.

        Arguments:
            blocks (list of blocks):
                A sequence of non-overlapping blocks, sorted by address.

            offset (int):
                Some address offset applied to all the blocks.

            start (int):
                Optional memory start address.
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data.

            validate (bool):
                Validates the resulting :obj:`Memory` object.

        Returns:
            :obj:`Memory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> blocks = [[1, b'ABC'], [5, b'xyz']]
            >>> memory = Memory.from_blocks(blocks)
            >>> memory.to_blocks()
            [[1, b'ABC'], [5, b'xyz']]
            >>> memory = Memory.from_blocks(blocks, offset=3)
            >>> memory.to_blocks()
            [[4, b'ABC'], [8, b'xyz']]

            ~~~

            >>> # Loads data from an Intel HEX record file
            >>> # NOTE: Record files typically require collapsing!
            >>> import hexrec.records as hr
            >>> blocks = hr.load_blocks('records.hex')
            >>> memory = Memory.from_blocks(collapse_blocks(blocks))
            >>> memory
                ...

        See Also:
            :meth:`to_blocks`
        """

        offset = Address(offset)

        if copy:
            blocks = [[block_start + offset, bytearray(block_data)]
                      for block_start, block_data in blocks]
        elif offset:
            blocks = [[block_start + offset, block_data]
                      for block_start, block_data in blocks]

        memory = Memory(start, endex)
        memory._blocks = blocks

        if (start is not None or endex is not None) and validate:  # fast check
            memory.crop(start, endex)

        if validate:
            memory.validate()

        return memory

    @classmethod
    def from_bytes(
        cls,
        data: AnyBytes,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':
        r"""Creates a virtual memory from a byte-like chunk.

        Arguments:
            data (byte-like data):
                A byte-like chunk of data (e.g. :obj:`bytes`,
                :obj:`bytearray`, :obj:`memoryview`).

            offset (int):
                Start address of the block of data.

            start (int):
                Optional memory start address.
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`Memory` object.

        Returns:
            :obj:`Memory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            >>> memory = Memory.from_bytes(b'')
            >>> memory.to_blocks()
            []

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |   |[A | B | C | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_bytes(b'ABCxyz', 2)
            >>> memory.to_blocks()
            [[2, b'ABCxyz']]

        See Also:
            :meth:`to_bytes`
        """

        if data:
            if copy:
                data = bytearray(data)
            blocks = [[offset, data]]
        else:
            blocks = []

        return cls.from_blocks(
            blocks,
            start=start,
            endex=endex,
            copy=False,
            validate=validate,
        )

    @classmethod
    def from_memory(
        cls,
        memory: Union[ImmutableMemory, 'Memory'],
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':
        r"""Creates a virtual memory from another one.

        Arguments:
            memory (Memory):
                A :obj:`Memory` to copy data from.

            offset (int):
                Some address offset applied to all the blocks.

            start (int):
                Optional memory start address.
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`Memory` object.

        Returns:
            :obj:`Memory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            >>> memory1 = Memory.from_bytes(b'ABC', 5)
            >>> memory2 = Memory.from_memory(memory1)
            >>> memory2._blocks
            [[5, b'ABC']]
            >>> memory1 == memory2
            True
            >>> memory1 is memory2
            False
            >>> memory1._blocks is memory2._blocks
            False

            ~~~

            >>> memory1 = Memory.from_bytes(b'ABC', 10)
            >>> memory2 = Memory.from_memory(memory1, -3)
            >>> memory2._blocks
            [[7, b'ABC']]
            >>> memory1 == memory2
            False

            ~~~

            >>> memory1 = Memory.from_bytes(b'ABC', 10)
            >>> memory2 = Memory.from_memory(memory1, copy=False)
            >>> all((b1[1] is b2[1])  # compare block data
            ...     for b1, b2 in zip(memory1._blocks, memory2._blocks))
            True
        """

        offset = Address(offset)
        is_memory = isinstance(memory, Memory)

        if copy or not is_memory:
            memory_blocks = memory._blocks if is_memory else memory.blocks()

            blocks = [[block_start + offset, bytearray(block_data)]
                      for block_start, block_data in memory_blocks]
        else:
            if offset:
                blocks = [[block_start + offset, block_data]
                          for block_start, block_data in memory._blocks]
            else:
                blocks = memory._blocks

        return cls.from_blocks(
            blocks,
            start=start,
            endex=endex,
            copy=False,
            validate=validate,
        )

    @classmethod
    def fromhex(
        cls,
        string: str,
    ) -> 'Memory':
        r"""Creates a virtual memory from an hexadecimal string.

        Arguments:
            string (str):
                Hexadecimal string.

        Returns:
            :obj:`Memory`: The resulting memory object.

        Examples:
            >>> memory = Memory.fromhex('')
            >>> bytes(memory)
            b''

            ~~~

            >>> memory = Memory.fromhex('48656C6C6F2C20576F726C6421')
            >>> bytes(memory)
            b'Hello, World!'
        """

        data = bytearray.fromhex(string)
        obj = cls()
        if data:
            obj._blocks.append([0, data])
        return obj

    def gaps(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[OpenInterval]:
        r"""Iterates over block gaps.

        Iterates over gaps emptiness bounds within an address range.
        If a yielded bound is ``None``, that direction is infinitely empty
        (valid before or after global data bounds).

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            couple of addresses: Block data interval boundaries.

        See Also:
            :meth:`intervals`

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'AB'], [5, b'x'], [7, b'123']])
            >>> list(memory.gaps())
            [(None, 1), (3, 5), (6, 7), (10, None)]
            >>> list(memory.gaps(0, 11))
            [(0, 1), (3, 5), (6, 7), (10, 11)]
            >>> list(memory.gaps(*memory.span))
            [(3, 5), (6, 7)]
            >>> list(memory.gaps(2, 6))
            [(3, 5)]
        """

        blocks = self._blocks
        if blocks:
            start_ = start
            endex_ = endex
            start, endex = self.bound(start, endex)

            if start_ is None:
                start = blocks[0][0]  # override trim start
                yield None, start
                block_index_start = 0
            else:
                block_index_start = self._block_index_start(start)

            if endex_ is None:
                block_index_endex = len(blocks)
            else:
                block_index_endex = self._block_index_endex(endex)

            block_iterator = _islice(blocks, block_index_start, block_index_endex)
            for block_start, block_data in block_iterator:
                if start < block_start:
                    yield start, block_start
                start = block_start + len(block_data)

            if endex_ is None:
                yield start, None
            elif start < endex:
                yield start, endex

        else:
            yield None, None

    def get(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, `default` if empty.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.get(3)  # -> ord('C') = 67
            67
            >>> memory.get(6)  # -> ord('$') = 36
            36
            >>> memory.get(10)  # -> ord('z') = 122
            122
            >>> memory.get(0)  # -> empty -> default = None
            None
            >>> memory.get(7)  # -> empty -> default = None
            None
            >>> memory.get(11)  # -> empty -> default = None
            None
            >>> memory.get(0, 123)  # -> empty -> default = 123
            123
            >>> memory.get(7, 123)  # -> empty -> default = 123
            123
            >>> memory.get(11, 123)  # -> empty -> default = 123
            123
        """

        block_index = self._block_index_at(address)
        if block_index is None:
            return default
        else:
            block_start, block_data = self._blocks[block_index]
            return block_data[address - block_start]

    def hex(
        self,
        *args: Any,  # see docstring
    ) -> str:
        r"""Converts into an hexadecimal string.

        The memory is required to be :attr:`contiguous`.

        Arguments:
            sep (str):
                Separator string between bytes.
                Defaults to an emoty string if not provided.
                Available since Python 3.8.

            bytes_per_sep (int):
                Number of bytes grouped between separators.
                Grouping is performed from the right.
                Defaults to one byte per group.
                Available since Python 3.8.

        Returns:
            str: Hexadecimal string representation.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> Memory().hex() == ''
            True

            ~~~

            >>> memory = Memory.from_bytes(b'Hello, World!')
            >>> memory.hex()
            48656c6c6f2c20576f726c6421
            >>> memory.hex('.')
            48.65.6c.6c.6f.2c.20.57.6f.72.6c.64.21
            >>> memory.hex('.', 4)
            48.656c6c6f.2c20576f.726c6421
        """

        block_count = len(self._blocks)
        if not block_count:
            return ''
        if block_count > 1:
            raise ValueError('non-contiguous data within range')

        data = self._blocks[0][1]
        return data.hex(*args)

    def index(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:
        r"""Index of an item.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the first item equal to `value`.

        Raises:
            :obj:`ValueError`: Item not found.
        """

        # Faster code for unbounded slice
        if start is None and endex is None:
            for block_start, block_data in self._blocks:
                try:
                    offset = block_data.index(item)
                except ValueError:
                    continue
                else:
                    return block_start + offset
            raise ValueError('subsection not found')

        # Bounded slice
        start, endex = self.bound(start, endex)
        block_index_start = self._block_index_start(start)
        block_index_endex = self._block_index_endex(endex)
        block_iterator = _islice(self._blocks, block_index_start, block_index_endex)

        for block_start, block_data in block_iterator:
            slice_start = 0 if start < block_start else start - block_start
            slice_endex = endex - block_start
            try:
                offset = block_data.index(item, slice_start, slice_endex)
            except ValueError:
                pass
            else:
                return block_start + offset
        else:
            raise ValueError('subsection not found')

    def insert(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> None:
        r"""Inserts data.

        Inserts data, moving existing items after the insertion address by the
        size of the inserted data.

        Arguments::
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |   |[x | y | z]|   |[$]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |   |[x | y | 1 | z]|   |[$]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.insert(10, b'$')
            >>> memory.to_blocks()
            [[1, b'ABC'], [6, b'xyz'], [10, b'$']]
            >>> memory.insert(8, b'1')
            >>> memory.to_blocks()
            [[1, b'ABC'], [6, b'xy1z'], [11, b'$']]

        See Also:
            :meth:`insert_backup`
            :meth:`insert_restore`
        """

        size = 1 if isinstance(data, Value) else len(data)
        self.reserve(address, size)
        self.write(address, data, clear=True)

    def insert_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> Tuple[Address, ImmutableMemory]:
        r"""Backups an `insert()` operation.

        Arguments:
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

        Returns:
            (int, :obj:`Memory`): Insertion address, backup memory region.

        See Also:
            :meth:`insert`
            :meth:`insert_restore`
        """

        size = 1 if isinstance(data, Value) else len(data)
        backup = self._pretrim_endex_backup(address, size)
        return address, backup

    def insert_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores an `insert()` operation.

        Arguments:
            address (int):
                Address of the insertion point.

            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`insert`
            :meth:`insert_backup`
        """

        self.delete(address, address + len(backup))
        self.write(0, backup, clear=True)

    def intervals(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[ClosedInterval]:
        r"""Iterates over block intervals.

        Iterates over data boundaries within an address range.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            couple of addresses: Block data interval boundaries.

        See Also:
            :meth:`blocks`
            :meth:`gaps`

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'AB'], [5, b'x'], [7, b'123']])
            >>> list(memory.intervals())
            [(1, 3), (5, 6), (7, 10)]
            >>> list(memory.intervals(2, 9))
            [(2, 3), (5, 6), (7, 9)]
            >>> list(memory.intervals(3, 5))
            []
        """

        blocks = self._blocks
        if blocks:
            block_index_start = 0 if start is None else self._block_index_start(start)
            block_index_endex = len(blocks) if endex is None else self._block_index_endex(endex)
            start, endex = self.bound(start, endex)
            block_iterator = _islice(blocks, block_index_start, block_index_endex)

            for block_start, block_data in block_iterator:
                block_endex = block_start + len(block_data)
                slice_start = block_start if start < block_start else start
                slice_endex = endex if endex < block_endex else block_endex
                if slice_start < slice_endex:
                    yield slice_start, slice_endex

    def items(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Tuple[Address, Value]]:
        r"""Iterates over address and value couples.

        Iterates over address and value couples, from `start` to `endex`.
        Implemets the interface of :obj:`dict`.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.
                If ``Ellipsis``, the iterator is infinite.

            pattern (items):
                Pattern of values to fill emptiness.

        Yields:
            int: Range address and value couples.

        Examples:
            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.items(endex=8))
            [(0, None), (1, None), (2, None), (3, None), (4, None), (5, None), (6, None), (7, None)]
            >>> list(memory.items(3, 8))
            [(3, None), (4, None), (5, None), (6, None), (7, None)]
            >>> list(islice(memory.items(3, ...), 7))
            [(3, None), (4, None), (5, None), (6, None), (7, None), (8, None), (9, None)]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67|   |   |120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.items())
            [(1, 65), (2, 66), (3, 67), (4, None), (5, None), (6, 120), (7, 121), (8, 122)]
            >>> list(memory.items(3, 8))
            [(3, 67), (4, None), (5, None), (6, 120), (7, 121)]
            >>> list(islice(memory.items(3, ...), 7))
            [(3, 67), (4, None), (5, None), (6, 120), (7, 121), (8, 122), (9, None)]
        """

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        yield from zip(self.keys(start, endex), self.values(start, endex, pattern))

    def keys(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
    ) -> Iterator[Address]:
        r"""Iterates over addresses.

        Iterates over addresses, from `start` to `endex`.
        Implemets the interface of :obj:`dict`.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.
                If ``Ellipsis``, the iterator is infinite.

        Yields:
            int: Range address.

        Examples:
            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.keys())
            []
            >>> list(memory.keys(endex=8))
            [0, 1, 2, 3, 4, 5, 6, 7]
            >>> list(memory.keys(3, 8))
            [3, 4, 5, 6, 7]
            >>> list(islice(memory.keys(3, ...), 7))
            [3, 4, 5, 6, 7, 8, 9]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.keys())
            [1, 2, 3, 4, 5, 6, 7, 8]
            >>> list(memory.keys(endex=8))
            [1, 2, 3, 4, 5, 6, 7]
            >>> list(memory.keys(3, 8))
            [3, 4, 5, 6, 7]
            >>> list(islice(memory.keys(3, ...), 7))
            [3, 4, 5, 6, 7, 8, 9]
        """

        if start is None:
            start = self.start

        if endex is Ellipsis:
            yield from _count(start)
        else:
            if endex is None:
                endex = self.endex
            yield from range(start, endex)

    def ofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:
        r"""Index of an item.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the first item equal to `value`, or ``None``.
        """

        try:
            return self.index(item, start, endex)
        except ValueError:
            return None

    def peek(
        self,
        address: Address,
    ) -> Optional[Value]:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, ``None`` if empty.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.peek(3)  # -> ord('C') = 67
            67
            >>> memory.peek(6)  # -> ord('$') = 36
            36
            >>> memory.peek(10)  # -> ord('z') = 122
            122
            >>> memory.peek(0)
            None
            >>> memory.peek(7)
            None
            >>> memory.peek(11)
            None
        """

        block_index = self._block_index_at(address)
        if block_index is None:
            return None
        else:
            block_start, block_data = self._blocks[block_index]
            return block_data[address - block_start]

    def poke(
        self,
        address: Address,
        item: Optional[Union[AnyBytes, Value]],
    ) -> None:
        r"""Sets the item at an address.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to set, ``None`` to clear the cell.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.poke(3, b'@')
            >>> memory.peek(3)  # -> ord('@') = 64
            64
            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.poke(5, b'@')
            >>> memory.peek(5)  # -> ord('@') = 64
            64

        See Also:
            :meth:`poke_backup`
            :meth:`poke_restore`
        """

        if self._trim_start is not None and address < self._trim_start:
            return
        if self._trim_endex is not None and address >= self._trim_endex:
            return

        if item is None:
            # Standard clear method
            self._erase(address, address + 1, False)  # clear

        else:
            if not isinstance(item, Value):
                if len(item) != 1:
                    raise ValueError('expecting single item')
                item = item[0]

            blocks = self._blocks
            block_index = self._block_index_endex(address) - 1

            if 0 <= block_index < len(blocks):
                block_start, block_data = blocks[block_index]
                block_endex = block_start + len(block_data)

                if block_start <= address < block_endex:
                    # Address within existing block, update directly
                    address -= block_start
                    block_data[address] = item
                    return

                elif address == block_endex:
                    # Address just after the end of the block, append
                    block_data.append(item)

                    block_index += 1
                    if block_index < len(blocks):
                        block_start2, block_data2 = blocks[block_index]

                        if block_endex + 1 == block_start2:
                            # Merge with the following contiguous block
                            block_data += block_data2
                            blocks.pop(block_index)
                    return

                else:
                    block_index += 1
                    if block_index < len(blocks):
                        block = blocks[block_index]
                        block_start, block_data = block

                        if address + 1 == block_start:
                            # Prepend to the next block
                            block_data.insert(0, item)
                            block[0] -= 1  # update address
                            return

            # There is no faster way than the standard block writing method
            self._erase(address, address + 1, False)  # clear
            self._place(address, bytearray((item,)), False)  # write

            self.crop(self._trim_start, self._trim_endex)

    def poke_backup(
        self,
        address: Address,
    ) -> Tuple[Address, Optional[Value]]:
        r"""Backups a `poke()` operation.

        Arguments:
            address (int):
                Address of the target item.

        Returns:
            (int, int): `address`, item at `address` (``None`` if empty).

        See Also:
            :meth:`poke`
            :meth:`poke_restore`
        """

        return address, self.peek(address)

    def poke_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:
        r"""Restores a `poke()` operation.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to restore.

        See Also:
            :meth:`poke`
            :meth:`poke_backup`
        """

        self.poke(address, item)

    def pop(
        self,
        address: Optional[Address] = None,
        default: Optional[Value] = None,
    ) -> Optional[Value]:
        r"""Takes a value away.

        Arguments:
            address (int):
                Address of the byte to pop.
                If ``None``, the very last byte is popped.

            default (int):
                Value to return if `address` is within emptiness.

        Return:
            int: Value at `address`; `default` within emptiness.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | D]|   |[$]|   |[x | y]|   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | D]|   |[$]|   |[x | y]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.pop()  # -> ord('z') = 122
            122
            >>> memory.pop(3)  # -> ord('C') = 67
            67
            >>> memory.pop(6, 63)  # -> ord('?') = 67
            63

        See Also:
            :meth:`pop_backup`
            :meth:`pop_restore`
        """

        if address is None:
            blocks = self._blocks
            if blocks:
                block_data = blocks[-1][1]
                backup = block_data.pop()
                if not block_data:
                    blocks.pop()
                return backup
            else:
                return default
        else:
            backup = self.peek(address)
            self._erase(address, address + 1, True)  # delete
            return default if backup is None else backup

    def pop_backup(
        self,
        address: Optional[Address] = None,
    ) -> Tuple[Address, Optional[Value]]:
        r"""Backups a `pop()` operation.

        Arguments:
            address (int):
                Address of the byte to pop.
                If ``None``, the very last byte is popped.

        Returns:
            (int, int): `address`, item at `address` (``None`` if empty).

        See Also:
            :meth:`pop`
            :meth:`pop_restore`
        """

        if address is None:
            address = self.endex - 1
        return address, self.peek(address)

    def pop_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:
        r"""Restores a `pop()` operation.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to restore, ``None`` if empty.

        See Also:
            :meth:`pop`
            :meth:`pop_backup`
        """

        if item is None:
            self.reserve(address, 1)
        else:
            if address == self.content_endex:
                self.append(item)
            else:
                self.insert(address, item)

    def popitem(
        self,
    ) -> Tuple[Address, Value]:
        r"""Pops the last item.

        Return:
            (int, int): Address and value of the last item.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A]|   |   |   |   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'A'], [9, b'yz']])
            >>> memory.popitem()  # -> ord('z') = 122
            (10, 122)
            >>> memory.popitem()  # -> ord('y') = 121
            (9, 121)
            >>> memory.popitem()  # -> ord('A') = 65
            (1, 65)
            >>> memory.popitem()
            Traceback (most recent call last):
                ...
            KeyError: empty

        See Also:
            :meth:`popitem_backup`
            :meth:`popitem_restore`
        """

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            value = block_data.pop()
            address = block_start + len(block_data)
            if not block_data:
                blocks.pop()
            return address, value
        raise KeyError('empty')

    def popitem_backup(
        self,
    ) -> Tuple[Address, Value]:
        r"""Backups a `popitem()` operation.

        Returns:
            (int, int): Address and value of the last item.

        See Also:
            :meth:`popitem`
            :meth:`popitem_restore`
        """

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            value = block_data[-1]
            address = block_start + len(block_data) - 1
            return address, value
        raise KeyError('empty')

    def popitem_restore(
        self,
        item: Value,
    ) -> None:
        r"""Restores a `popitem()` operation.

        Arguments:
            item (int or byte):
                Item to restore.

        See Also:
            :meth:`popitem`
            :meth:`popitem_backup`
        """

        self.append(item)

    def remove(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:
        r"""Removes an item.

        Searches and deletes the first occurrence of an item.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Raises:
            :obj:`ValueError`: Item not found.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | D]|   |[$]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | D]|   |   |[x | y | z]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.remove(b'BC')
            >>> memory.to_blocks()
            [[1, b'AD'], [4, b'$'], [6, b'xyz']]
            >>> memory.remove(ord('$'))
            >>> memory.to_blocks()
            [[1, b'AD'], [5, b'xyz']]
            >>> memory.remove(b'?')
            Traceback (most recent call last):
                ...
            ValueError: subsection not found

        See Also:
            :meth:`remove_backup`
            :meth:`remove_restore`
        """

        address = self.index(item, start, endex)
        size = 1 if isinstance(item, Value) else len(item)
        self._erase(address, address + size, True)  # delete

    def remove_backup(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:
        r"""Backups a `remove()` operation.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`Memory`: Backup memory region.

        Raises:
            :obj:`ValueError`: Item not found.

        See Also:
            :meth:`remove`
            :meth:`remove_restore`
        """

        address = self.index(item, start, endex)
        size = 1 if isinstance(item, Value) else len(item)
        return self.extract(address, address + size)

    def remove_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `remove()` operation.

        Arguments:
            backup (:obj:`Memory`):
                Backup memory region.

        See Also:
            :meth:`remove`
            :meth:`remove_backup`
        """

        self.reserve(backup.start, len(backup))
        self.write(0, backup)

    def reserve(
        self,
        address: Address,
        size: Address,
    ) -> None:
        r"""Inserts emptiness.

        Reserves emptiness at the provided address.

        Arguments:
            address (int):
                Start address of the emptiness to insert.

            size (int):
                Size of the emptiness to insert.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[3, b'ABC'], [7, b'xyz']])
            >>> memory.reserve(4, 2)
            >>> memory.to_blocks()
            [[3, b'A'], [6, b'BC'], [9, b'xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   |[A | B]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']], endex=12)
            >>> memory.reserve(5, 5)
            >>> memory.to_blocks()
            [[10, b'AB']]

        See Also:
            :meth:`reserve_backup`
            :meth:`reserve_restore`
        """

        blocks = self._blocks

        if size > 0 and blocks:
            self._pretrim_endex(address, size)
            block_index = self._block_index_start(address)

            if block_index < len(blocks):
                block = blocks[block_index]
                block_start, block_data = block

                if address > block_start:
                    # Split into two blocks, reserving emptiness
                    offset = address - block_start
                    data_after = block_data[offset:]
                    del block_data[offset:]
                    block_index += 1

                    blocks.insert(block_index, [address + size, data_after])
                    block_index += 1

                for block_index in range(block_index, len(blocks)):
                    blocks[block_index][0] += size

    def reserve_backup(
        self,
        address: Address,
        size: Address,
    ) -> Tuple[Address, ImmutableMemory]:
        r"""Backups a `reserve()` operation.

        Arguments:
            address (int):
                Start address of the emptiness to insert.

            size (int):
                Size of the emptiness to insert.

        Returns:
            (int, :obj:`Memory`): Reservation address, backup memory region.

        See Also:
            :meth:`reserve`
            :meth:`reserve_restore`
        """

        backup = self._pretrim_endex_backup(address, size)
        return address, backup

    def reserve_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `reserve()` operation.

        Arguments:
            address (int):
                Address of the reservation point.

            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`reserve`
            :meth:`reserve_backup`
        """

        self.delete(address, address + len(backup))
        self.write(0, backup, clear=True)

    def reverse(
        self,
    ) -> None:
        r"""Reverses the memory in-place.

        Data is reversed within the memory :attr:`span`.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[z | y | x]|   |[$]|   |[D | C | B | A]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.reverse()
            >>> memory.to_blocks()
            [[1, b'zyx'], [5, b'$'], [7, b'DCBA']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |   |[[[|   |[A | B | C]|   |   |   |)))|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |   |[[[|   |   |[C | B | A]|   |   |)))|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_bytes(b'ABCD', 3, start=2, endex=10)
            >>> memory.reverse()
            >>> memory.to_blocks()
            [[5, b'CBA']]
        """

        blocks = self._blocks
        if blocks:
            start, endex = self.span

            for block in blocks:
                block_start, block_data = block
                block_data.reverse()
                block[0] = endex - block_start - len(block_data) + start

            blocks.reverse()

    def rfind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:
        r"""Index of an item, reversed search.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the last item equal to `value`, or -1.
        """

        try:
            return self.rindex(item, start, endex)
        except ValueError:
            return -1

    def rindex(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:
        r"""Index of an item, reversed search.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the last item equal to `value`.

        Raises:
            :obj:`ValueError`: Item not found.
        """

        # Faster code for unbounded slice
        if start is None and endex is None:
            for block_start, block_data in reversed(self._blocks):
                try:
                    offset = block_data.index(item)
                except ValueError:
                    continue
                else:
                    return block_start + offset
            else:
                raise ValueError('subsection not found')

        # Bounded slice
        start, endex = self.bound(start, endex)
        block_index_start = self._block_index_start(start)
        block_index_endex = self._block_index_endex(endex)
        blocks = self._blocks

        for block_index in reversed(range(block_index_start, block_index_endex)):
            block_start, block_data = blocks[block_index]
            slice_start = 0 if start < block_start else start - block_start
            slice_endex = endex - block_start
            try:
                offset = block_data.rindex(item, slice_start, slice_endex)
            except ValueError:
                pass
            else:
                return block_start + offset
        else:
            raise ValueError('subsection not found')

    def rofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:
        r"""Index of an item, reversed search.

        Arguments:
            item (items):
                Value to find. Can be either some byte string or an integer.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The index of the last item equal to `value`, or ``None``.
        """

        try:
            return self.rindex(item, start, endex)
        except ValueError:
            return None

    def rvalues(
        self,
        start: Optional[Union[Address, EllipsisType]] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values, reversed order.

        Iterates over values, from `endex` to `start`.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.
                If ``Ellipsis``, the iterator is infinite.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

            pattern (items):
                Pattern of values to fill emptiness.

        Yields:
            int: Range values.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |   |   | A | B | C | D | A |   |   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |   |   | 65| 66| 67| 68| 65|   |   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.rvalues(endex=8))
            [None, None, None, None, None, None, None, None]
            >>> list(memory.rvalues(3, 8))
            [None, None, None, None, None]
            >>> list(islice(memory.rvalues(..., 8), 7))
            [None, None, None, None, None, None, None]
            >>> list(memory.rvalues(3, 8, b'ABCD'))
            [65, 68, 67, 66, 65]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|<1 | 2>|[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67|   |   |120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67| 49| 50|120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.rvalues())
            [122, 121, 120, None, None, 67, 66, 65]
            >>> list(memory.rvalues(3, 8))
            [121, 120, None, None, 67]
            >>> list(islice(memory.rvalues(..., 8), 7))
            [121, 120, None, None, 67, 66, 65]
            >>> list(memory.rvalues(3, 8, b'0123'))
            [121, 120, 50, 49, 67]
        """

        if pattern is None:
            pattern_size = 0
        else:
            if isinstance(pattern, Value):
                pattern = (pattern,)
            pattern = bytearray(pattern)
            if not pattern:
                raise ValueError('non-empty pattern required')
            pattern.reverse()
            pattern_size = len(pattern)

        start_ = start
        if start is None or start is Ellipsis:
            start = self.start

        blocks = self._blocks
        if endex is None:
            endex = self.endex
            block_index = len(blocks)
        else:
            block_index = self._block_index_endex(endex)

        if 0 < block_index:
            block_start, block_data = blocks[block_index - 1]
            block_endex = block_start + len(block_data)

            if block_endex < endex:
                yield from _repeat2(pattern, pattern_size - (endex - start), endex - block_endex)
                yield from reversed(block_data)
            else:
                yield from reversed(memoryview(block_data)[:(endex - block_start)])
            endex = block_start

            for block_index in range(block_index - 2, -1, -1):
                block_start, block_data = blocks[block_index]
                block_endex = block_start + len(block_data)
                yield from _repeat2(pattern, pattern_size - (endex - start), endex - block_endex)
                if start <= block_start:
                    yield from reversed(block_data)
                    endex = block_start
                else:
                    yield from reversed(memoryview(block_data)[(start - block_start):])
                    endex = start

        size = None if start_ is Ellipsis else endex - start
        yield from _repeat2(pattern, pattern_size - (endex - start), size)

    def setdefault(
        self,
        address: Address,
        default: Optional[Union[AnyBytes, Value]] = None,
    ) -> Optional[Value]:
        r"""Defaults a value.

        Arguments:
            address (int):
                Address of the byte to set.

            default (int):
                Value to set if `address` is within emptiness.

        Return:
            int: Value at `address`; `default` within emptiness.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.setdefault(3, b'@')  # -> ord('C') = 67
            67
            >>> memory.peek(3)  # -> ord('C') = 67
            67
            >>> memory.setdefault(5, 64)  # -> ord('@') = 64
            64
            >>> memory.peek(5)  # -> ord('@') = 64
            64
            >>> memory.setdefault(9) is None
            False
            >>> memory.peek(9) is None
            False
            >>> memory.setdefault(7) is None
            True
            >>> memory.peek(7) is None
            True

        See Also:
            :meth:`setdefault_backup`
            :meth:`setdefault_restore`
        """

        backup = self.peek(address)
        if backup is None:
            if default is not None:
                if not isinstance(default, Value):
                    if len(default) != 1:
                        raise ValueError('expecting single item')
                    default = default[0]
                self.poke(address, default)
            return default
        else:
            return backup

    def setdefault_backup(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Tuple[Address, Optional[Value]]:
        r"""Backups a `setdefault()` operation.

        Arguments:
            address (int):
                Address of the byte to set.

            default (int):
                Value to set if `address` is within emptiness.

        Returns:
            (int, int): `address`, item at `address` (``None`` if empty).

        See Also:
            :meth:`setdefault`
            :meth:`setdefault_restore`
        """

        backup = self.peek(address)
        if backup is None:
            return address, default
        else:
            return address, backup

    def setdefault_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:
        r"""Restores a `setdefault()` operation.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to restore, ``None`` if empty.

        See Also:
            :meth:`setdefault`
            :meth:`setdefault_backup`
        """

        self.poke(address, item)

    def shift(
        self,
        offset: Address,
    ) -> None:
        r"""Shifts the items.

        Arguments:
            offset (int):
                Signed amount of address shifting.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']])
            >>> memory.shift(-2)
            >>> memory.to_blocks()
            [[3, b'ABC'], [7, b'xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[[[|   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[y | z]|   |   |   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'ABC'], [9, b'xyz']], start=3)
            >>> memory.shift(-8)
            >>> memory.to_blocks()
            [[2, b'yz']]

        See Also:
            :meth:`shift_backup`
            :meth:`shift_restore`
        """

        if offset and self._blocks:
            if offset < 0:
                self._pretrim_start(None, -offset)
            else:
                self._pretrim_endex(None, +offset)

            for block in self._blocks:
                block[0] += offset

    def shift_backup(
        self,
        offset: Address,
    ) -> Tuple[Address, ImmutableMemory]:
        r"""Backups a `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

        Returns:
            (int, :obj:`Memory`): Shifting, backup memory region.

        See Also:
            :meth:`shift`
            :meth:`shift_restore`
        """

        if offset < 0:
            backup = self._pretrim_start_backup(None, -offset)
        else:
            backup = self._pretrim_endex_backup(None, +offset)
        return offset, backup

    def shift_restore(
        self,
        offset: Address,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores an `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`shift`
            :meth:`shift_backup`
        """

        self.shift(-offset)
        self.write(0, backup, clear=True)

    @ImmutableMemory.span.getter
    def span(
        self,
    ) -> ClosedInterval:
        r"""tuple of int: Memory address span.

        A :obj:`tuple` holding both :attr:`start` and :attr:`endex`.

        Examples:
            >>> Memory().span
            (0, 0)
            >>> Memory(start=1, endex=8).span
            (1, 8)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.span
            (1, 8)
        """

        return self.start, self.endex

    @ImmutableMemory.start.getter
    def start(
        self,
    ) -> Address:
        r"""int: Inclusive start address.

        This property holds the inclusive start address of the virtual space.
        By default, it is the current minimum inclusive start address of
        the first stored block.

        If :attr:`trim_start` not ``None``, that is returned.

        If the memory has no data and no trimming, 0 is returned.

        Examples:
            >>> Memory().start
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [5, b'xyz']])
            >>> memory.start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[5, b'xyz']], start=1)
            >>> memory.start
            1
        """

        trim_start = self._trim_start
        if trim_start is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                return blocks[0][0]
            else:
                return 0
        else:
            return trim_start

    def to_blocks(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> BlockList:
        r"""Exports into blocks.

        Exports data blocks within an address range, converting them into
        standalone :obj:`bytes` objects.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Returns:
            list of blocks: Exported data blocks.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'AB'], [5, b'x'], [7, b'123']])
            >>> memory.to_blocks()
            [[1, b'AB'], [5, b'x'], [7, b'123']]
            >>> memory.to_blocks(2, 9)
            [[2, b'B'], [5, b'x'], [7, b'12']]
            >>> memory.to_blocks(3, 5)]
            []

        See Also:
            :meth:`blocks`
            :meth:`from_blocks`
        """

        blocks = [[block_start, bytes(block_data)]
                  for block_start, block_data in self.blocks(start, endex)]
        return blocks

    def to_bytes(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> bytes:
        r"""Exports into bytes.

        Exports data within an address range, converting into a standalone
        :obj:`bytes` object.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Returns:
            bytes: Exported data bytes.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> memory = Memory.from_bytes(b'')
            >>> memory.to_bytes()
            b''

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |   |[A | B | C | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_bytes(b'ABCxyz', 2)
            >>> memory.to_bytes()
            b'ABCxyz'
            >>> memory.to_bytes(start=4)
            b'Cxyz'
            >>> memory.to_bytes(endex=6)
            b'ABCx'
            >>> memory.to_bytes(4, 6)
            b'Cx'

        See Also:
            :meth:`from_bytes`
            :meth:`view`
        """

        return bytes(self.view(start, endex))

    @ImmutableMemory.trim_endex.getter
    def trim_endex(
        self,
    ) -> Optional[Address]:
        r"""int: Trimming exclusive end address.

        Any data at or after this address is automatically discarded.
        Disabled if ``None``.
        """

        return self._trim_endex

    @trim_endex.setter
    def trim_endex(
        self,
        trim_endex: Address,
    ) -> None:

        trim_start = self._trim_start
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_start = trim_start = trim_endex

        self._trim_endex = trim_endex
        if trim_endex is not None:
            self.crop(trim_start, trim_endex)

    @ImmutableMemory.trim_span.getter
    def trim_span(
        self,
    ) -> OpenInterval:
        r"""tuple of int: Trimming span addresses.

        A :obj:`tuple` holding :attr:`trim_start` and :attr:`trim_endex`.
        """

        return self._trim_start, self._trim_endex

    @trim_span.setter
    def trim_span(
        self,
        trim_span: OpenInterval,
    ) -> None:

        trim_start, trim_endex = trim_span
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            trim_endex = trim_start

        self._trim_start = trim_start
        self._trim_endex = trim_endex
        if trim_start is not None or trim_endex is not None:
            self.crop(trim_start, trim_endex)

    @ImmutableMemory.trim_start.getter
    def trim_start(
        self,
    ) -> Optional[Address]:
        r"""int: Trimming start address.

        Any data before this address is automatically discarded.
        Disabled if ``None``.
        """

        return self._trim_start

    @trim_start.setter
    def trim_start(
        self,
        trim_start: Address,
    ) -> None:

        trim_endex = self._trim_endex
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_endex = trim_endex = trim_start

        self._trim_start = trim_start
        if trim_start is not None:
            self.crop(trim_start, trim_endex)

    def update(
        self,
        data: Union[Iterable[Tuple[Address, Value]],
                    Mapping[Address, Union[Value, AnyBytes]],
                    ImmutableMemory],
        **kwargs: Any,  # string keys cannot become addresses
    ) -> None:
        r"""Updates data.

        Arguments:
            data (iterable):
                Data to update with.
                Can be either another memory, an (address, value)
                mapping, or an iterable of (address, value) pairs.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |   |   |[A | B | C]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[x | y]|   |   |[A | B | C]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[x | y | @]|   |[A | ? | C]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory()
            >>> memory.update(Memory.from_bytes(b'ABC', 5))
            >>> memory.to_blocks()
            [[5, b'ABC']]
            >>> memory.update({1: b'x', 2: ord('y')})
            >>> memory.to_blocks()
            [[1, b'xy'], [5, b'ABC']]
            >>> memory.update([(6, b'?'), (3, ord('@'))])
            >>> memory.to_blocks()
            [[1, b'xy@'], [5, b'A?C']]
        """

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            self.write(0, data)
        else:
            if isinstance(data, Mapping):
                data = data.items()

            for address, value in data:
                self.poke(address, value)

    def update_backup(
        self,
        data: Union[Iterable[Tuple[Address, Value]], ImmutableMemory],
        **kwargs: Any,  # string keys cannot become addresses
    ) -> ImmutableMemory:
        r"""Backups an `update()` operation.

        Arguments:
            data (iterable):
                Data to update with.
                Can be either another memory, an (address, value)
                mapping, or an iterable of (address, value) pairs.

        Returns:
            :obj:`MutableMemory` list: Backup memory regions.

        See Also:
            :meth:`update`
            :meth:`update_restore`
        """

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            return self.write_backup(0, data)
        else:
            if isinstance(data, Mapping):
                data = data.keys()
            backup = self.__class__()
            poke = backup.poke
            peek = self.peek

            for address, value in data:
                poke(address, peek(address))
            return backup

    def update_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores an `update()` operation.

        Arguments:
            backup (:obj:`ImmutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`update`
            :meth:`update_backup`
        """

        self.write(0, backup)

    def validate(
        self,
    ) -> None:
        r"""Validates internal structure.

        It makes sure that all the allocated blocks are sorted by block start
        address, and that all the blocks are non-overlapping.

        Raises:
            :obj:`ValueError`: Invalid data detected (see exception message).
        """

        start, endex = self.bound(None, None)

        blocks = self._blocks
        if blocks:
            if endex <= start:
                raise ValueError('invalid bounds')

            previous_endex = blocks[0][0] - 1  # before first start

            for block_start, block_data in blocks:
                block_endex = block_start + len(block_data)

                if block_start <= previous_endex:
                    raise ValueError('invalid block interleaving')

                if block_endex <= block_start:
                    raise ValueError('invalid block data size')

                if block_start < start or endex < block_endex:
                    raise ValueError('invalid block bounds')

                previous_endex = block_endex

        else:
            if endex < start:
                raise ValueError('invalid bounds')

    def values(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values.

        Iterates over values, from `start` to `endex`.
        Implemets the interface of :obj:`dict`.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.
                If ``Ellipsis``, the iterator is infinite.

            pattern (items):
                Pattern of values to fill emptiness.

        Yields:
            int: Range values.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |   |   | A | B | C | D | A |   |   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |   |   | 65| 66| 67| 68| 65|   |   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.values(endex=8))
            [None, None, None, None, None, None, None, None]
            >>> list(memory.values(3, 8))
            [None, None, None, None, None]
            >>> list(islice(memory.values(3, ...), 7))
            [None, None, None, None, None, None, None]
            >>> list(memory.values(3, 8, b'ABCD'))
            [65, 66, 67, 68, 65]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|<1 | 2>|[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67|   |   |120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67| 49| 50|120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.values())
            [65, 66, 67, None, None, 120, 121, 122]
            >>> list(memory.values(3, 8))
            [67, None, None, 120, 121]
            >>> list(islice(memory.values(3, ...), 7))
            [67, None, None, 120, 121, 122, None]
            >>> list(memory.values(3, 8, b'0123'))
            [67, 49, 50, 120, 121]
        """

        if endex is None or endex is Ellipsis:
            if pattern is not None:
                if isinstance(pattern, Value):
                    pattern = (pattern,)
                    pattern = bytearray(pattern)
                if not pattern:
                    raise ValueError('non-empty pattern required')

            if start is None:
                start = self.start
                block_index = 0
            else:
                block_index = self._block_index_start(start)
            start_ = start

            blocks = self._blocks
            if block_index < len(blocks):
                block_start, block_data = blocks[block_index]

                if block_start < start:
                    yield from memoryview(block_data)[(start - block_start):]
                else:
                    yield from _repeat2(pattern, (start - start_), (block_start - start))
                    yield from block_data
                start = block_start + len(block_data)

                for block_start, block_data in _islice(blocks, block_index + 1, len(blocks)):
                    yield from _repeat2(pattern, (start - start_), (block_start - start))
                    yield from block_data
                    start = block_start + len(block_data)

            if endex is Ellipsis:
                yield from _repeat2(pattern, (start - start_), None)

        else:
            if start is None:
                start = self.start
            if start < endex:
                yield from _islice(self.values(start, Ellipsis, pattern), (endex - start))

    def view(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> memoryview:
        r"""Creates a view over a range.

        Creates a memory view over the selected address range.
        Data within the range is required to be contiguous.

        Arguments:
            start (int):
                Inclusive start of the viewed range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the viewed range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`memoryview`: A view of the selected address range.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> bytes(memory.view(2, 5))
            b'BCD'
            >>> bytes(memory.view(9, 10))
            b'y'
            >>> memory.view()
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
            >>> memory.view(0, 6)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        if start < endex:
            block_index = self._block_index_at(start)

            if block_index is not None:
                block_start, block_data = self._blocks[block_index]

                if endex <= block_start + len(block_data):
                    return memoryview(block_data)[(start - block_start):(endex - block_start)]

            raise ValueError('non-contiguous data within range')
        else:
            return memoryview(b'')

    def write(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory, 'Memory'],
        clear: bool = False,
    ) -> None:
        r"""Writes data.

        Arguments:
            address (int):
                Address where to start writing data.

            data (bytes):
                Data to write.

            clear (bool):
                Clears the target range before writing data.
                Useful only if `data` is a :obj:`Memory` with empty spaces.

        Example:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[1 | 2 | 3 | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([[1, b'ABC'], [6, b'xyz']])
            >>> memory.write(5, b'123')
            >>> memory.to_blocks()
            [[1, b'ABC'], [5, b'123z']]

        See Also:
            :meth:`write_backup`
            :meth:`write_restore`
        """

        if isinstance(data, Value):
            self.poke(address, data)  # faster
            return

        data_is_immutable_memory = isinstance(data, ImmutableMemory)
        if data_is_immutable_memory:
            start = data.start + address
            endex = data.endex + address
            size = endex - start
        else:
            data = bytearray(data)  # clone
            size = len(data)
            if size == 1:
                self.poke(address, data[0])  # faster
                return
            start = address
            endex = start + size

        if not size:
            return

        trim_start = self._trim_start
        if trim_start is not None and endex <= trim_start:
            return

        trim_endex = self._trim_endex
        if trim_endex is not None and trim_endex <= start:
            return

        if data_is_immutable_memory:
            data_is_memory = isinstance(data, Memory)
            if clear:
                # Clear anything between source data boundaries
                self._erase(start, endex, False)  # clear
            else:
                # Clear only overwritten ranges
                data_blocks = data._blocks if data_is_memory else data.blocks()
                for block_start, block_data in data_blocks:
                    block_start = block_start + address
                    block_endex = block_start + len(block_data)
                    self._erase(block_start, block_endex, False)  # clear

            data_blocks = data._blocks if data_is_memory else data.blocks()
            for block_start, block_data in data_blocks:
                block_start = block_start + address
                block_endex = block_start + len(block_data)

                if trim_start is not None and block_endex <= trim_start:
                    continue
                if trim_endex is not None and trim_endex <= block_start:
                    break

                block_data = bytearray(block_data)  # clone

                # Trim before memory
                if trim_start is not None and block_start < trim_start:
                    offset = trim_start - block_start
                    block_start += offset
                    del block_data[:offset]

                # Trim after memory
                if trim_endex is not None and trim_endex < block_endex:
                    offset = block_endex - trim_endex
                    block_endex -= offset
                    del block_data[(block_endex - block_start):]

                self._place(block_start, block_data, False)  # write
        else:
            # Trim before memory
            if trim_start is not None and start < trim_start:
                offset = trim_start - start
                size -= offset
                start += offset
                del data[:offset]

            # Trim after memory
            if trim_endex is not None and trim_endex < endex:
                offset = endex - trim_endex
                size -= offset
                endex -= offset
                del data[size:]

            # Check if extending the actual content
            blocks = self._blocks
            if blocks:
                block_start, block_data = blocks[-1]
                block_endex = block_start + len(block_data)
                if start == block_endex:
                    block_data += data  # faster
                    return

            # Standard write method
            self._erase(start, endex, False)  # clear
            self._place(start, data, False)  # write

    def write_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> ImmutableMemory:
        r"""Backups a `write()` operation.

        Arguments:
            address (int):
                Address where to start writing data.

            data (bytes):
                Data to write.

        Returns:
            :obj:`Memory` list: Backup memory regions.

        See Also:
            :meth:`write`
            :meth:`write_restore`
        """

        size = 1 if isinstance(data, Value) else len(data)
        return self.extract(address, address + size)

    def write_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `write()` operation.

        Arguments:
            backup (:obj:`Memory`):
                Backup memory region to restore.

        See Also:
            :meth:`write`
            :meth:`write_backup`
        """

        self.write(0, backup, clear=True)


class bytesparse(Memory):
    r"""Wrapper for more `bytearray` compatibility.

    This wrapper class can make :class:`Memory` closer to the actual
    :class:`bytearray` API.

    For instantiation, please refer to :meth:`bytearray.__init__`.

    With respect to :class:`Memory`, negative addresses are not allowed.
    Instead, negative addresses are to consider as referred to :attr:`endex`.

    Arguments:
        source:
            The optional `source` parameter can be used to initialize the
            array in a few different ways:

            * If it is a string, you must also give the `encoding` (and
              optionally, `errors`) parameters; it then converts the string to
              bytes using :meth:`str.encode`.

            * If it is an integer, the array will have that size and will be
              initialized with null bytes.

            * If it is an object conforming to the buffer interface, a
              read-only buffer of the object will be used to initialize the byte
              array.

            * If it is an iterable, it must be an iterable of integers in the
              range 0 <= x < 256, which are used as the initial contents of the
              array.

        encoding (str):
            Optional string encoding.

        errors (str):
            Optional string error management.

        start (int):
            Optional memory start address.
            Anything before will be trimmed away.
            If `source` is provided, its data start at this address
            (0 if `start` is ``None``).

        endex (int):
            Optional memory exclusive end address.
            Anything at or after it will be trimmed away.
    """

    def __init__(
        self,
        *args: Any,  # see bytearray.__init__()
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ):

        super().__init__(start, endex)

        data = bytearray(*args)
        if data:
            if start is None:
                start = 0

            if endex is not None:
                if endex < start:
                    endex = start

                del data[(endex - start):]

            self._blocks.append([start, data])

    def __delitem__(
        self,
        key: Union[Address, slice],
    ) -> None:

        if isinstance(key, slice):
            start, endex = self._rectify_span(key.start, key.stop)
            key = slice(start, endex, key.step)
        else:
            key = self._rectify_address(key)

        super().__delitem__(key)

    def __getitem__(
        self,
        key: Union[Address, slice],
    ) -> Any:

        if isinstance(key, slice):
            start, endex = self._rectify_span(key.start, key.stop)
            key = slice(start, endex, key.step)
        else:
            key = self._rectify_address(key)

        return super().__getitem__(key)

    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Optional[Union[AnyBytes, Value]],
    ) -> None:

        if isinstance(key, slice):
            start, endex = self._rectify_span(key.start, key.stop)
            key = slice(start, endex, key.step)
        else:
            key = self._rectify_address(key)

        super().__setitem__(key, value)

    def _rectify_address(
        self,
        address: Address,
    ) -> Address:
        r"""Rectifies an address.

        In case the provided `address` is negative, it is recomputed as
        referred to :attr:`endex`.

        In case the rectified address would still be negative, an
        exception is raised.

        Arguments:
            address:
                Address to be rectified.

        Returns:
            int: Rectified address.

        Raises:
            IndexError: The rectified address would still be negative.
        """

        address = address.__index__()

        if address < 0:
            span_start, span_endex = self.span
            address = span_endex + address
            if address < 0:
                raise IndexError('index out of range')

        return address

    def _rectify_span(
        self,
        start: Optional[Address],
        endex: Optional[Address],
    ) -> OpenInterval:
        r"""Rectifies an address span.

        In case a provided address is negative, it is recomputed as
        referred to :attr:`endex`.

        In case the rectified address would still be negative, it is
        clamped to address zero.

        Arguments:
            start (int):
                Inclusive start address for rectification.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for rectification.
                If ``None``, :attr:`endex` is considered.

        Returns:
            couple of int: Rectified address span.
        """

        span_start = None
        span_endex = None

        if start is not None and start < 0:
            span_start, span_endex = self.span
            start = span_endex + start
            if start < 0:
                start = 0

        if endex is not None and endex < 0:
            if span_start is None:
                span_start, span_endex = self.span
            endex = span_endex + endex
            if endex < 0:
                endex = 0

        return start, endex

    def block_span(
        self,
        address: Address,
    ) -> Tuple[Optional[Address], Optional[Address], Optional[Value]]:

        address = self._rectify_address(address)
        return super().block_span(address)

    def blocks(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[Tuple[Address, memoryview]]:

        start, endex = self._rectify_span(start, endex)
        yield from super().blocks(start, endex)

    def bound(
        self,
        start: Optional[Address],
        endex: Optional[Address],
    ) -> ClosedInterval:

        start, endex = self._rectify_span(start, endex)
        return super().bound(start, endex)

    def clear(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().clear(start, endex)

    def clear_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().clear_backup(start, endex)

    def count(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> int:

        start, endex = self._rectify_span(start, endex)
        return super().count(item, start, endex)

    def crop(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().crop(start, endex)

    def crop_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Tuple[Optional[ImmutableMemory], Optional[ImmutableMemory]]:

        start, endex = self._rectify_span(start, endex)
        return super().crop_backup(start, endex)

    def cut(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        bound: bool = True,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().cut(start, endex)

    def delete(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().delete(start, endex)

    def delete_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().delete_backup(start, endex)

    def equal_span(
        self,
        address: Address,
    ) -> Tuple[Optional[Address], Optional[Address], Optional[Value]]:

        address = self._rectify_address(address)
        return super().equal_span(address)

    def extract(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
        step: Optional[Address] = None,
        bound: bool = True,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().extract(start, endex, pattern, step, bound)

    def fill(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().fill(start, endex, pattern)

    def fill_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().fill_backup(start, endex)

    def find(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().find(item, start, endex)

    def flood(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().flood(start, endex, pattern)

    def flood_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> List[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        return super().flood_backup(start, endex)

    @classmethod
    def from_blocks(
        cls,
        blocks: BlockSequence,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'bytesparse':

        if blocks:
            block_start = blocks[0][0]
            if block_start + offset < 0:
                raise ValueError('negative offseted start')

        if start is not None and start < 0:
            raise ValueError('negative start')
        if endex is not None and endex < 0:
            raise ValueError('negative endex')

        memory = super().from_blocks(blocks, offset, start, endex, copy, validate)
        memory = _cast(bytesparse, memory)
        return memory

    @classmethod
    def from_bytes(
        cls,
        data: AnyBytes,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'bytesparse':

        if offset < 0:
            raise ValueError('negative offset')
        if start is not None and start < 0:
            raise ValueError('negative start')
        if endex is not None and endex < 0:
            raise ValueError('negative endex')

        memory = super().from_bytes(data, offset, start, endex, copy)
        memory = _cast(bytesparse, memory)
        return memory

    @classmethod
    def from_memory(
        cls,
        memory: Memory,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'bytesparse':

        blocks = memory._blocks
        if blocks:
            block_start = blocks[0][0]
            if block_start + offset < 0:
                raise ValueError('negative offseted start')

        if start is not None and start < 0:
            raise ValueError('negative start')
        if endex is not None and endex < 0:
            raise ValueError('negative endex')

        memory = super().from_memory(memory, offset, start, endex, copy)
        memory = _cast(bytesparse, memory)
        return memory

    def gaps(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        yield from super().gaps(start, endex)

    def get(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

        address = self._rectify_address(address)
        return super().get(address, default)

    def index(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().index(item, start, endex)

    def insert(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> None:

        address = self._rectify_address(address)
        super().insert(address, data)

    def insert_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> Tuple[Address, ImmutableMemory]:

        address = self._rectify_address(address)
        return super().insert_backup(address, data)

    def intervals(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[ClosedInterval]:

        start, endex = self._rectify_span(start, endex)
        yield from super().intervals(start, endex)

    def items(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Tuple[Address, Value]]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().items(start, endex)

    def keys(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
    ) -> Iterator[Address]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().keys(start, endex_)

    def ofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:

        start, endex = self._rectify_span(start, endex)
        return super().ofind(item, start, endex)

    def peek(
        self,
        address: Address,
    ) -> Optional[Value]:

        address = self._rectify_address(address)
        return super().peek(address)

    def poke(
        self,
        address: Address,
        item: Optional[Union[AnyBytes, Value]],
    ) -> None:

        address = self._rectify_address(address)
        super().poke(address, item)

    def poke_backup(
        self,
        address: Address,
    ) -> Tuple[Address, Optional[Value]]:

        address = self._rectify_address(address)
        return super().poke_backup(address)

    def pop(
        self,
        address: Optional[Address] = None,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

        if address is not None:
            address = self._rectify_address(address)
        return super().pop(address, default)

    def pop_backup(
        self,
        address: Optional[Address] = None,
    ) -> Tuple[Address, Optional[Value]]:

        address = self._rectify_address(address)
        return super().pop_backup(address)

    def remove(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().remove(item, start, endex)

    def remove_backup(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().remove_backup(item, start, endex)

    def reserve(
        self,
        address: Address,
        size: Address,
    ) -> None:

        address = self._rectify_address(address)
        super().reserve(address, size)

    def reserve_backup(
        self,
        address: Address,
        size: Address,
    ) -> Tuple[Address, ImmutableMemory]:

        address = self._rectify_address(address)
        return super().reserve_backup(address, size)

    def rfind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().rfind(item, start, endex)

    def rindex(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().rindex(item, start, endex)

    def rofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:

        start, endex = self._rectify_span(start, endex)
        return super().rofind(item, start, endex)

    def rvalues(
        self,
        start: Optional[Union[Address, EllipsisType]] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Optional[Value]]:

        start_ = start  # backup
        if start is Ellipsis:
            start = None
        start, endex = self._rectify_span(start, endex)
        if start_ is Ellipsis:
            start = start_  # restore
        yield from super().rvalues(start, endex, pattern)

    def setdefault(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

        address = self._rectify_address(address)
        return super().setdefault(address, default)

    def setdefault_backup(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Tuple[Address, Optional[Value]]:

        address = self._rectify_address(address)
        return super().setdefault_backup(address, default)

    def shift(
        self,
        offset: Address,
    ) -> None:

        if offset < 0:
            blocks = self._blocks
            if blocks:
                block_start = blocks[0][0]
                if block_start + offset < 0:
                    raise ValueError('negative offseted start')

        super().shift(offset)

    def shift_backup(
        self,
        offset: Address,
    ) -> Tuple[Address, ImmutableMemory]:

        if offset < 0:
            blocks = self._blocks
            if blocks:
                block_start = blocks[0][0]
                if block_start + offset < 0:
                    raise ValueError('negative offseted start')

        return super().shift_backup(offset)

    @ImmutableMemory.trim_endex.getter
    def trim_endex(
        self,
    ) -> Optional[Address]:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._trim_endex

    @trim_endex.setter
    def trim_endex(
        self,
        trim_endex: Address,
    ) -> None:

        if trim_endex is not None and trim_endex < 0:
            raise ValueError('negative endex')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        trim_start = self._trim_start
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_start = trim_start = trim_endex

        self._trim_endex = trim_endex
        if trim_endex is not None:
            self.crop(trim_start, trim_endex)

    @ImmutableMemory.trim_span.getter
    def trim_span(
        self,
    ) -> OpenInterval:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._trim_start, self._trim_endex

    @trim_span.setter
    def trim_span(
        self,
        trim_span: OpenInterval,
    ) -> None:

        trim_start, trim_endex = trim_span
        if trim_start is not None and trim_start < 0:
            raise ValueError('negative start')
        if trim_endex is not None and trim_endex < 0:
            raise ValueError('negative endex')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        trim_start, trim_endex = trim_span
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            trim_endex = trim_start

        self._trim_start = trim_start
        self._trim_endex = trim_endex
        if trim_start is not None or trim_endex is not None:
            self.crop(trim_start, trim_endex)

    @ImmutableMemory.trim_start.getter
    def trim_start(
        self,
    ) -> Optional[Address]:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._trim_start

    @trim_start.setter
    def trim_start(
        self,
        trim_start: Address,
    ) -> None:

        if trim_start is not None and trim_start < 0:
            raise ValueError('negative start')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        trim_endex = self._trim_endex
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_endex = trim_endex = trim_start

        self._trim_start = trim_start
        if trim_start is not None:
            self.crop(trim_start, trim_endex)

    def validate(
        self,
    ) -> None:

        for block in self._blocks:
            if block[0] < 0:
                raise ValueError('negative block start')

        super().validate()

    def values(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Optional[Value]]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().values(start, endex)

    def view(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> memoryview:

        start, endex = self._rectify_span(start, endex)
        return super().view(start, endex)

    def write(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
        clear: bool = False,
    ) -> None:

        address = self._rectify_address(address)
        super().write(address, data, clear)

    def write_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> ImmutableMemory:

        address = self._rectify_address(address)
        return super().write_backup(address, data)
