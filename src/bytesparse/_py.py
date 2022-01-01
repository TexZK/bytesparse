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

r"""Python implementation."""

from itertools import count as _count
from itertools import islice as _islice
from itertools import repeat as _repeat
from itertools import zip_longest as _zip_longest
from typing import Any
from typing import ByteString
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Type
from typing import Union

Address = int
Value = int
AnyBytes = Union[ByteString, bytes, bytearray, memoryview, Sequence[Value]]
Data = bytearray

Block = List[Union[Address, Data]]  # typed as Tuple[Address, Data]
BlockIndex = int
BlockIterable = Iterable[Block]
BlockSequence = Sequence[Block]
BlockList = List[Block]
MemoryList = List['Memory']

OpenInterval = Tuple[Optional[Address], Optional[Address]]
ClosedInterval = Tuple[Address, Address]

EllipsisType = Type['Ellipsis']

STR_MAX_CONTENT_SIZE = 1000


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

            elif 0 < size:
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

            elif 0 < size:
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


class Memory:
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

    Raises:
        :obj:`ValueError`: More than one of `memory`, `data`, and `blocks`.

    Examples:
        >>> memory = Memory()
        >>> memory._blocks
        []

        >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
        >>> memory._blocks
        [[5, b'Hello, World!']]
    """

    def __init__(
        self: 'Memory',
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

    @classmethod
    def from_blocks(
        cls: Type['Memory'],
        blocks: BlockList,
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

            collapse (bool):
                Collapses the provided blocks, prior to construction.
                Useful when source blocks do not satisfy the requirements of
                the underlying data structure, e.g. blocks are not sorted by
                address or they have some overlapping or contiguity.

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
            >>> memory._blocks
            [[1, b'ABC'], [5, b'xyz']]
            >>> memory = Memory.from_blocks(blocks, offset=3)
            >>> memory._blocks
            [[4, b'ABC'], [8, b'xyz']]

            ~~~

            >>> # Loads data from an Intel HEX record file
            >>> # NOTE: Record files typically require collapsing!
            >>> import hexrec.records as hr
            >>> blocks = hr.load_blocks('records.hex')
            >>> memory = Memory.from_blocks(collapse_blocks(blocks))
            >>> memory
                ...
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
            memory._crop(start, endex, None)

        if validate:
            memory.validate()

        return memory

    @classmethod
    def from_bytes(
        cls: Type['Memory'],
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

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            >>> memory = Memory.from_bytes(b'')
            >>> memory._blocks
            []

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |   |[A | B | C | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_bytes(b'ABCxyz', 2)
            >>> memory._blocks
            [[2, b'ABCxyz']]
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
        cls: Type['Memory'],
        memory: 'Memory',
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

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            >>> memory1 = Memory.from_bytes(b'ABC', 5)
            >>> memory2 = Memory.from_memory(memory1)
            >>> memory2._blocks
            [[5, b'ABC]]
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
            [[7, b'ABC]]
            >>> memory1 == memory2
            False

            ~~~

            >>> memory1 = Memory.from_bytes(b'ABC', 10)
            >>> memory2 = Memory.from_memory(memory2, copy=False)
            >>> all((b1[1] is b2[1])  # compare block data
            ...     for b1, b2 in zip(memory1._blocks, memory2._blocks))
            True
        """

        offset = Address(offset)

        if copy:
            blocks = [[block_start + offset, bytearray(block_data)]
                      for block_start, block_data in memory._blocks]
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

    def __repr__(
        self: 'Memory',
    ) -> str:

        start = self.start
        endex = self.endex
        start = '' if start is None else f'0x{start:X}'
        endex = '' if endex is None else f'0x{endex:X}'
        return f'<{type(self).__name__}[{start}:{endex}]@0x{id(self):X}>'

    def __str__(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [7, b'xyz']])
            >>> memory._blocks
            'ABCxyz'
        """

        if self.content_size < STR_MAX_CONTENT_SIZE:
            return repr(self._blocks)
        else:
            return repr(self)

    def __bool__(
        self: 'Memory',
    ) -> bool:
        r"""Has any items.

        Returns:
            bool: Has any items.

        Examples:
            >>> memory = Memory()
            >>> bool(memory)
            False

            >>> memory = Memory(data=b'Hello, World!', offset=5)
            >>> bool(memory)
            True
        """

        return any(block_data for _, block_data in self._blocks)

    def __eq__(
        self: 'Memory',
        other: Any,
    ) -> bool:
        r"""Equality comparison.

        Arguments:
            other (Memory):
                Data to compare with `self`.

                If it is a :obj:`Memory`, all of its blocks must match.

                If it is a :obj:`list`, it is expected that it contains the
                same blocks as `self`.

                Otherwise, it must match the first stored block, considered
                equal if also starts at 0.

        Returns:
            bool: `self` is equal to `other`.

        Examples:
            >>> data = b'Hello, World!'
            >>> memory = Memory(data=data)
            >>> memory == data
            True
            >>> memory.shift(1)
            >>> memory == data
            False

            >>> data = b'Hello, World!'
            >>> memory = Memory(data=data)
            >>> memory == [[0, data]]
            True
            >>> memory == list(data)
            False
            >>> memory.shift(1)
            >>> memory == [[0, data]]
            False
        """

        if isinstance(other, Memory):
            return self._blocks == other._blocks

        elif isinstance(other, (bytes, bytearray, memoryview)):
            blocks = self._blocks
            if blocks or other:
                return len(blocks) == 1 and blocks[0][1] == other
            else:
                return True

        else:
            iter_self = _islice(self, len(self))  # avoid infinite loop
            iter_other = iter(other)
            return all(a == b for a, b in _zip_longest(iter_self, iter_other, fillvalue=None))

    def __iter__(
        self: 'Memory',
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values.

        Iterates over values between :attr:`start` and :attr:`endex`.

        Yields:
            int: Value as byte integer, or ``None``.
        """

        yield from self.values(self.start, self.endex)

    def __reversed__(
        self: 'Memory',
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values, reversed order.

        Iterates over values between :attr:`start` and :attr:`endex`, in
        reversed order.

        Yields:
            int: Value as byte integer, or ``None``.
        """

        yield from self.rvalues(self.start, self.endex)

    def __add__(
        self: 'Memory',
        value: Union[AnyBytes, 'Memory'],
    ) -> 'Memory':

        memory = type(self).from_memory(self, validate=False)
        memory.extend(value)
        return memory

    def __iadd__(
        self: 'Memory',
        value: Union[AnyBytes, 'Memory'],
    ) -> 'Memory':

        self.extend(value)
        return self

    def __mul__(
        self: 'Memory',
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
            memory = type(self).from_memory(self, validate=False)

            for time in range(times - 1):
                memory.write(offset, self)
                offset += size

            return memory
        else:
            return type(self)()

    def __imul__(
        self: 'Memory',
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
            memory = type(self).from_memory(self, validate=False)

            for time in range(times - 1):
                self.write(offset, memory)
                offset += size
        else:
            blocks.clear()
        return self

    def __len__(
        self: 'Memory',
    ) -> Address:
        r"""Actual length.

        Computes the actual length of the stored items, i.e.
        (:attr:`endex` - :attr:`start`).
        This will consider any trimmings being active.

        Returns:
            int: Memory length.
        """

        return self.endex - self.start

    def ofind(
        self: 'Memory',
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

    def rofind(
        self: 'Memory',
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

    def find(
        self: 'Memory',
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

    def rfind(
        self: 'Memory',
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

    def index(
        self: 'Memory',
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

    def rindex(
        self: 'Memory',
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

    def __contains__(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'123'], [9, b'xyz']])
            >>> b'23' in memory
            True
            >>> ord('y') in memory
            True
            >>> b'$' in memory
            False
        """

        return any(item in block_data for _, block_data in self._blocks)

    def count(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'Bat'], [9, b'tab']])
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

    def __getitem__(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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
            endex = key.stop
            start = self.start if start is None else start
            endex = self.endex if endex is None else endex
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

    def __setitem__(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory[7:10] = None
            >>> memory._blocks
            [[5, b'AB'], [10, b'yz']]
            >>> memory[7] = b'C'
            >>> memory[9] = b'x'
            >>> memory._blocks == [[5, b'ABC'], [9, b'xyz']]
            True
            >>> memory[6:12:3] = None
            >>> memory._blocks
            [[5, b'A'], [7, b'C'], [10, b'yz']]
            >>> memory[6:13:3] = b'123'
            >>> memory._blocks
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

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory[0:4] = b'$'
            >>> memory._blocks
            [[0, b'$'], [2, b'ABC'], [6, b'xyz']]
            >>> memory[4:7] = b'45678'
            >>> memory._blocks
            [[0, b'$'], [2, b'AB45678yz']]
            >>> memory[6:8] = b'<>'
            >>> memory._blocks
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
                    self._erase(start, endex, False, False)  # clear
                else:
                    for address in range(start, endex, step):
                        self._erase(address, address + 1, False, False)  # clear
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
                    self._erase(del_start, del_endex, True, True)  # delete
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

    def __delitem__(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> del memory[4:9]
            >>> memory._blocks
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> del memory[9]
            >>> memory._blocks
            [[1, b'ABCD'], [6, b'$'], [8, b'xz']]
            >>> del memory[3]
            >>> memory._blocks
            [[1, b'ABD'], [5, b'$'], [7, b'xz']]
            >>> del memory[2:10:3]
            >>> memory._blocks
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
                        self._erase(start, endex, True, True)  # delete

                    elif step > 1:
                        for address in reversed(range(start, endex, step)):
                            self._erase(address, address + 1, True, True)  # delete
            else:
                address = key.__index__()
                self._erase(address, address + 1, True, True)  # delete

    def append(
        self: 'Memory',
        item: Union[AnyBytes, Value],
    ) -> None:
        r"""Appends a single item.

        Arguments:
            item (int):
                Value to append. Can be a single byte string or integer.

        Examples:
            >>> memory = Memory()
            >>> memory.append(b'$')
            >>> memory._blocks
            [[0, b'$']]

            ~~~

            >>> memory = Memory()
            >>> memory.append(3)
            >>> memory._blocks
            [[0, b'\x03']]
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

    def extend(
        self: 'Memory',
        items: Union[AnyBytes, 'Memory'],
        offset: Address = 0,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Concatenates items.

        Equivalent to ``self += items``.

        Arguments:
            items (items):
                Items to append at the end of the current virtual space.

                If a :obj:`list`, it is interpreted as a sequence of
                non-overlapping blocks, sorted by start address.

            offset (int):
                Optional offset w.r.t. :attr:`content_endex`.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items.
        """

        if offset < 0:
            raise ValueError('negative extension offset')
        self.write(self.content_endex + offset, items, backups=backups)

    def pop(
        self: 'Memory',
        address: Optional[Address] = None,
    ) -> Optional[Value]:
        r"""Takes a value away.

        Arguments:
            address (int):
                Address of the byte to pop.
                If ``None``, the very last byte is popped.

        Return:
            int: Value at `address`; ``None`` within emptiness.

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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.pop()  # -> ord('z') = 122
            122
            >>> memory.pop(3)  # -> ord('C') = 67
            67
        """

        if address is None:
            blocks = self._blocks
            if blocks:
                _, block_data = blocks[-1]
                backup = block_data.pop()
                if not block_data:
                    blocks.pop()
                return backup
            else:
                return None
        else:
            backup = self.peek(address)
            self._erase(address, address + 1, True, True)  # delete
            return backup

    def _bytearray(
        self: 'Memory',
    ) -> bytearray:
        r"""Underlying bytearray.

        Returns:
            bytearray: The underlying bytearray.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        blocks = self._blocks

        if not blocks:
            start = self._trim_start
            endex = self._trim_endex
            if start is not None and endex is not None and start < endex - 1:
                raise ValueError('non-contiguous data within range')
            return bytearray()

        elif len(blocks) == 1:
            start = self._trim_start
            if start is not None:
                if start != blocks[0][0]:
                    raise ValueError('non-contiguous data within range')

            endex = self._trim_endex
            if endex is not None:
                block_start, block_data = blocks[-1]
                if endex != block_start + len(block_data):
                    raise ValueError('non-contiguous data within range')

            return blocks[0][1]

        else:
            raise ValueError('non-contiguous data within range')

    def __bytes__(
        self: 'Memory',
    ) -> bytes:
        r"""Creates a bytes clone.

        Returns:
            :obj:`bytes`: Cloned data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        return bytes(self._bytearray())

    def to_bytes(
        self: 'Memory',
    ) -> bytes:
        r"""Creates a bytes clone.

        Returns:
            :obj:`bytes`: Cloned data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        return bytes(self._bytearray())

    def to_bytearray(
        self: 'Memory',
        copy: bool = True,
    ) -> bytearray:
        r"""Creates a bytearray clone.

        Arguments:
            copy (bool):
                Creates a clone of the underlying :obj:`bytearray` data
                structure.

        Returns:
            :obj:`bytearray`: Cloned data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        block_data = self._bytearray()
        return bytearray(block_data) if copy else block_data

    def to_memoryview(
        self: 'Memory',
    ) -> memoryview:
        r"""Creates a memory view.

        Returns:
            :obj:`memoryview`: View over data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """

        return memoryview(self._bytearray())

    def __copy__(
        self: 'Memory',
    ) -> 'Memory':
        r"""Creates a shallow copy.

        Returns:
            :obj:`Memory`: Shallow copy.
        """

        return type(self).from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=False)

    def __deepcopy__(
        self: 'Memory',
    ) -> 'Memory':
        r"""Creates a deep copy.

        Returns:
            :obj:`Memory`: Deep copy.
        """

        return type(self).from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=True)

    @property
    def contiguous(
        self: 'Memory',
    ) -> bool:
        r"""bool: Contains contiguous data.

        The memory is considered to have contiguous data if there is no empty
        space between blocks.

        If trimming is defined, there must be no empty space also towards it.
        """

        try:
            self._bytearray()
            return True
        except ValueError:
            return False

    @property
    def trim_start(
        self: 'Memory',
    ) -> Optional[Address]:
        r"""int: Trimming start address.

        Any data before this address is automatically discarded.
        Disabled if ``None``.
        """

        return self._trim_start

    @trim_start.setter
    def trim_start(
        self: 'Memory',
        trim_start: Address,
    ) -> None:

        trim_endex = self._trim_endex
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_endex = trim_endex = trim_start

        self._trim_start = trim_start
        if trim_start is not None:
            self._crop(trim_start, trim_endex, None)

    @property
    def trim_endex(
        self: 'Memory',
    ) -> Optional[Address]:
        r"""int: Trimming exclusive end address.

        Any data at or after this address is automatically discarded.
        Disabled if ``None``.
        """

        return self._trim_endex

    @trim_endex.setter
    def trim_endex(
        self: 'Memory',
        trim_endex: Address,
    ) -> None:

        trim_start = self._trim_start
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_start = trim_start = trim_endex

        self._trim_endex = trim_endex
        if trim_endex is not None:
            self._crop(trim_start, trim_endex, None)

    @property
    def trim_span(
        self: 'Memory',
    ) -> OpenInterval:
        r"""tuple of int: Trimming span addresses.

        A :obj:`tuple` holding :attr:`trim_start` and :attr:`trim_endex`.
        """

        return self._trim_start, self._trim_endex

    @trim_span.setter
    def trim_span(
        self: 'Memory',
        span: OpenInterval,
    ) -> None:

        trim_start, trim_endex = span
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            trim_endex = trim_start

        self._trim_start = trim_start
        self._trim_endex = trim_endex
        if trim_start is not None or trim_endex is not None:
            self._crop(trim_start, trim_endex, None)

    @property
    def start(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'xyz']], start=1)
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

    @property
    def endex(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
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

    @property
    def span(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.span
            (1, 8)
        """

        return self.start, self.endex

    @property
    def endin(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
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

    @property
    def content_start(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'xyz']], start=1)
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

    @property
    def content_endex(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
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

    @property
    def content_span(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_span
            (1, 8)
        """

        return self.content_start, self.content_endex

    @property
    def content_endin(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
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

    @property
    def content_size(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_size
            6

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
            >>> memory.content_size
            3
        """

        return sum(len(block_data) for _, block_data in self._blocks)

    @property
    def content_parts(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.content_parts
            2

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC']], endex=8)
            >>> memory.content_parts
            1
        """

        return len(self._blocks)

    def validate(
        self: 'Memory',
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

    def bound(
        self: 'Memory',
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
            >>> Memory().bound()
            (0, 0)
            >>> Memory().bound(endex=100)
            (0, 0)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [5, b'xyz']])
            >>> memory.bound(0, 30)
            (1, 8)
            >>> memory.bound(2, 6)
            (2, 6)
            >>> memory.bound(endex=6)
            (1, 6)
            >>> memory.bound(start=2)
            (2, 8)

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |[A | B | C]|   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[3, b'ABC']], start=1, endex=8)
            >>> memory.bound()
            (1, 8)
            >>> memory.bound(0, 30)
            (1, 8)
            >>> memory.bound(2, 6)
            (2, 6)
            >>> memory.bound(start=2)
            (2, 8)
            >>> memory.bound(endex=6)
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

    def _block_index_at(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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

    def _block_index_start(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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

    def _block_index_endex(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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

    def peek(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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
        self: 'Memory',
        address: Address,
        item: Optional[Union[AnyBytes, Value]],
    ) -> Optional[Value]:
        r"""Sets the item at an address.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to set, ``None`` to clear the cell.

        Returns:
            int: The previous item at `address`, ``None`` if empty.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.poke(3, b'@')  # -> ord('C') = 67
            67
            >>> memory.peek(3)  # -> ord('@') = 64
            64
            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
            >>> memory.poke(5, '@')
            None
            >>> memory.peek(5)  # -> ord('@') = 64
            64
        """

        if item is None:
            # Standard clear method
            value = self.peek(address)
            self._erase(address, address + 1, False, False)  # clear
            return value

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
                    value = block_data[address]
                    block_data[address] = item
                    return value

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
                    return None

                else:
                    block_index += 1
                    if block_index < len(blocks):
                        block = blocks[block_index]
                        block_start, block_data = block

                        if address + 1 == block_start:
                            # Prepend to the next block
                            block_data.insert(0, item)
                            block[0] -= 1  # update address
                            return None

            # There is no faster way than the standard block writing method
            self._erase(address, address + 1, False, True)  # insert
            self._insert(address, bytearray((item,)), False)

            self._crop(self._trim_start, self._trim_endex, None)
            return None

    def extract(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABCD'], [6, b'$'], [8, b'xyz']])
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
            >>> memory.extract(pattern='.')._blocks
            [[1, b'ABCD.$.xyz']]
            >>> memory.extract(pattern='.', step=3)._blocks
            [[1, b'AD.z']]
        """

        start_ = start
        endex_ = endex
        memory = type(self)()

        if step is None or step == 1:
            start, endex = self.bound(start, endex)
            blocks = self._blocks

            if start < endex and blocks:
                block_index_start = None if start_ is None else self._block_index_start(start)
                block_index_endex = None if endex_ is None else self._block_index_endex(endex)
                blocks = [[block_start, bytearray(block_data)]
                          for block_start, block_data in blocks[block_index_start:block_index_endex]]
                memory._blocks = blocks
                memory._crop(start, endex, None)

                if pattern is not None:
                    memory.flood(start, endex, pattern)
        else:
            step = int(step)
            if step > 1:
                start, endex = self.bound(start, endex)
                blocks = []
                block_start = None
                block_data = None
                offset = start

                for value in _islice(self.values(start, endex, pattern), 0, endex - start, step):
                    if value is None:
                        if block_start is not None:
                            blocks.append([block_start, block_data])
                            block_start = None
                    else:
                        if block_start is None:
                            block_start = offset
                            block_data = bytearray()
                        block_data.append(value)
                    offset += 1

                if block_start is not None:
                    blocks.append([block_start, block_data])

                memory._blocks = blocks
                if bound:
                    endex_ = offset
        if bound:
            memory._trim_start = start_
            memory._trim_endex = endex_

        return memory

    def shift(
        self: 'Memory',
        offset: Address,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Shifts the items.

        Arguments:
            offset (int):
                Signed amount of address shifting.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items, before trimming.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory.shift(-2)
            >>> memory._blocks
            [[3, b'ABC'], [7, b'xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[[[|   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[y | z]|   |   |   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']], start=2)
            >>> backups = []
            >>> memory.shift(-7, backups=backups)
            >>> memory._blocks
            [[2, b'yz']]
            >>> len(backups)
            1
            >>> backups[0]._blocks
            [[5, b'ABC'], [9, b'x']]
        """

        if offset and self._blocks:
            if offset < 0:
                self._pretrim_start(None, -offset, backups)
            else:
                self._pretrim_endex(None, +offset, backups)

            for block in self._blocks:
                block[0] += offset

    def reserve(
        self: 'Memory',
        address: Address,
        size: Address,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Inserts emptiness.

        Reserves emptiness at the provided address.

        Arguments:
            address (int):
                Start address of the emptiness to insert.

            size (int):
                Size of the emptiness to insert.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items, before trimming.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[3, b'ABC'], [7, b'xyz']])
            >>> memory.reserve(4, 2)
            >>> memory._blocks
            [[2, b'A'], [6, b'BC'], [9, b'xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   |[A | B]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']], endex=12)
            >>> backups = []
            >>> memory.reserve(5, 5, backups=backups)
            >>> memory._blocks
            [[10, b'AB']]
            >>> len(backups)
            1
            >>> backups[0]._blocks
            [[7, b'C'], [9, b'xyz']]
        """

        blocks = self._blocks

        if size and blocks:
            self._pretrim_endex(address, size, backups)

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

    def _insert(
        self: 'Memory',
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
                        block_index += 1
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

    def _erase(
        self: 'Memory',
        start: Address,
        endex: Address,
        shift_after: bool,
        merge_deletion: bool,
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

            merge_deletion (bool):
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

            if merge_deletion:
                # Check if inner deletion can be merged
                if inner_start and inner_endex < len(blocks):
                    block_start, block_data = blocks[inner_start - 1]
                    block_endex = block_start + len(block_data)
                    block_start2, block_data2 = blocks[inner_endex]

                    if block_endex + size == block_start2:
                        block_data += block_data2  # merge deletion boundaries
                        inner_endex += 1  # add to inner deletion
                        block_index += 1  # skip address update

            if shift_after:
                # Shift blocks after deletion
                for block_index in range(block_index, len(blocks)):
                    blocks[block_index][0] -= size  # update address

            # Delete inner full blocks
            if inner_start < inner_endex:
                del blocks[inner_start:inner_endex]

    def insert(
        self: 'Memory',
        address: Address,
        data: Union[AnyBytes, Value, 'Memory'],
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Inserts data.

        Inserts data, moving existing items after the insertion address by the
        size of the inserted data.

        Arguments::
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items, before trimming.

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

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.insert(10, b'$')
            >>> memory._blocks
            [[1, b'ABC'], [6, b'xyz'], [10, b'$']]
            >>> memory.insert(8, b'1')
            >>> memory._blocks
            [[1, b'ABC'], [6, b'xy1z'], [11, b'$']]
        """

        if isinstance(data, Memory):
            data_start = data.start
            data_endex = data.endex

            if data_start < data_endex:
                self.reserve(data_start, data_endex, backups=backups)
                self.write(data_start, data)
        else:
            if isinstance(data, Value):
                data = (data,)
            data = bytearray(data)

            self._insert(address, data, True)  # TODO: backups

            if data:
                self._crop(self._trim_start, self._trim_endex, None)  # TODO: pre-trimming

    def delete(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Deletes an address range.

        Arguments:
            start (int):
                Inclusive start address for deletion.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for deletion.
                If ``None``, :attr:`endex` is considered.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items.

        Example:
            +---+---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12| 13|
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | y | z]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory.delete(6, 10)
            >>> memory._blocks
            [[5, b'Ayz']]
        """

        start, endex = self.bound(start, endex)

        if start < endex:
            if backups is not None:
                backups.append(self.extract(start, endex))

            self._erase(start, endex, True, True)  # delete

    def clear(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Clears an address range.

        Arguments:
            start (int):
                Inclusive start address for clearing.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for clearing.
                If ``None``, :attr:`endex` is considered.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the cleared
                items.

        Example:
            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory.clear(6, 10)
            >>> memory._blocks
            [[5, b'A'], [10, b'yz']]
        """

        start, endex = self.bound(start, endex)

        if start < endex:
            if backups is not None:
                backups.append(self.extract(start, endex))

            self._erase(start, endex, False, False)  # clear

    def _pretrim_start(
        self: 'Memory',
        endex_max: Optional[Address],
        size: Address,
        backups: Optional[MemoryList],
    ) -> None:
        r"""Trims initial data.

        Low-level method to manage trimming of data starting from an address.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`trim_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the cleared
                items.
        """

        trim_start = self._trim_start
        if trim_start is not None and size > 0:
            endex = trim_start + size

            if endex_max is not None and endex > endex_max:
                endex = endex_max

            if backups is not None:
                backups.append(self.extract(endex=endex))

            self._erase(self.content_start, endex, False, False)  # clear

    def _pretrim_endex(
        self: 'Memory',
        start_min: Optional[Address],
        size: Address,
        backups: Optional[MemoryList],
    ) -> None:
        r"""Trims final data.

        Low-level method to manage trimming of data starting from an address.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`trim_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the cleared
                items.
        """

        trim_endex = self._trim_endex
        if trim_endex is not None and size > 0:
            start = trim_endex - size

            if start_min is not None and start < start_min:
                start = start_min

            if backups is not None:
                backups.append(self.extract(start=start))

            self._erase(start, self.content_endex, False, False)  # clear

    def _crop(
        self: 'Memory',
        start: Optional[Address],
        endex: Optional[Address],
        backups: Optional[MemoryList],
    ) -> None:
        r"""Keeps data within an address range.

        Low-level method to crop the underlying data structure.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the cleared
                items.
        """

        blocks = self._blocks  # may change

        # Trim blocks exceeding before memory start
        if start is not None and blocks:
            block_start = blocks[0][0]

            if block_start < start:
                if backups is not None:
                    backups.append(self.extract(block_start, start))

                self._erase(block_start, start, False, False)  # clear

        # Trim blocks exceeding after memory end
        if endex is not None and blocks:
            block_start, block_data = blocks[-1]
            block_endex = block_start + len(block_data)

            if endex < block_endex:
                if backups is not None:
                    backups.append(self.extract(endex, block_endex))

                self._erase(endex, block_endex, False, False)  # clear

    def crop(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        backups: Optional[MemoryList] = None,
    ) -> None:
        r"""Keeps data within an address range.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the cleared
                items.

        Example:
            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |[B | C]|   |[x]|   |   |   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[5, b'ABC'], [9, b'xyz']])
            >>> memory.crop(6, 10)
            >>> memory._blocks
            [[6, b'BC'], [9, b'x']]
        """

        self._crop(start, endex, backups)

    def write(
        self: 'Memory',
        address: Address,
        data: Union[AnyBytes, Value, 'Memory'],
        clear: bool = False,
        backups: Optional[MemoryList] = None,
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

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items.

        Example:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[1 | 2 | 3 | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.write(5, b'123')
            >>> memory._blocks
            [[1, b'ABC'], [5, b'123z']]
        """

        if isinstance(data, Memory):
            data_start = data.start
            data_endex = data.endex
            size = data_endex - data_start
            # TODO: trim data to fit within self.trim_span (avoid cropping afterwards)

            if size:
                if clear:
                    # Clear anything between source data boundaries
                    if backups is not None:
                        backups.append(self.extract(data_start, data_endex))

                    self._erase(data_start, data_endex, False, False)  # clear

                else:
                    # Clear only overwritten ranges
                    for block_start, block_data in data._blocks:
                        block_start += address
                        block_endex = block_start + len(block_data)

                        if backups is not None:
                            backups.append(self.extract(block_start, block_endex))

                        self._erase(block_start, block_endex, False, False)  # clear

                for block_start, block_data in data._blocks:
                    self._insert(block_start + address, bytearray(block_data), False)  # insert

                self._crop(self._trim_start, self._trim_endex, None)

        else:
            if isinstance(data, Value):
                data = (data,)
            data = bytearray(data)
            size = len(data)

            if size:
                start = address
                endex = start + size

                trim_endex = self._trim_endex
                if trim_endex is not None:
                    if start >= trim_endex:
                        return
                    elif endex > trim_endex:
                        size -= endex - trim_endex
                        endex = start + size
                        del data[size:]

                trim_start = self._trim_start
                if trim_start is not None:
                    if endex <= trim_start:
                        return
                    elif trim_start > start:
                        offset = trim_start - start
                        size -= offset
                        start += offset
                        endex = start + size
                        del data[:offset]

                if backups is not None:
                    backups.append(self.extract(start, endex))

                blocks = self._blocks
                if blocks:
                    block_start, block_data = blocks[-1]
                    block_endex = block_start + len(block_data)
                    if start == block_endex:
                        block_data += data  # might be faster
                        return

                if size == 1:
                    self.poke(start, data[0])  # might be faster
                else:
                    self._erase(start, endex, False, True)  # insert
                    self._insert(start, data, False)

    def fill(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
        backups: Optional[MemoryList] = None,
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

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items, before trimming.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[1 | 2 | 3 | 1 | 2 | 3 | 1 | 2]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.fill(pattern=b'123')
            >>> memory._blocks
            [[1, b'12312312']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | 1 | 2 | 3 | 1 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.fill(3, 7, b'123')
            >>> memory._blocks
            [[1, b'AB1231yz']]
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

            if backups is not None:
                backups.append(self.extract(start, endex))

            # Resize the pattern to the target range
            size = endex - start
            if pattern_size < size:
                pattern *= (size + (pattern_size - 1)) // pattern_size
            del pattern[size:]

            # Standard write method
            self._erase(start, endex, False, True)  # insert
            self._insert(start, pattern, False)

    def flood(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
        backups: Optional[MemoryList] = None,
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

            backups (list of :obj:`Memory`):
                Optional output list holding backup copies of the deleted
                items, before trimming.

        Examples:
            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 1 | 2 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.flood(pattern=b'123')
            >>> memory._blocks
            [[1, b'ABC12xyz']]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 2 | 3 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> memory.flood(3, 7, b'123')
            >>> memory._blocks
            [[1, b'ABC23xyz']]
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

            if backups is not None:
                cls = type(self)
                for gap_start, gap_endex in self.gaps(start, endex):
                    backups.append(cls(start=gap_start, endex=gap_endex))

            size = endex - start
            pattern *= (size + (pattern_size - 1)) // pattern_size
            del pattern[size:]

            blocks_inner = blocks[block_index_start:block_index_endex]
            blocks[block_index_start:block_index_endex] = [[start, pattern]]

            for block_start, block_data in blocks_inner:
                block_endex = block_start + len(block_data)
                pattern[(block_start - start):(block_endex - start)] = block_data

    def keys(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.keys())
            [1, 2, 3, 4, 5, 6, 7, 8]
            >>> list(memory.keys(endex=8))
            [0, 1, 2, 3, 4, 5, 6, 7]
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

    def values(
        self: 'Memory',
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
            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.values(endex=8))
            [None, None, None, None, None, None, None]
            >>> list(memory.values(3, 8))
            [None, None, None, None, None]
            >>> list(islice(memory.values(3, ...), 7))
            [None, None, None, None, None, None, None]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67|   |   |120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.values())
            [65, 66, 67, None, None, 120, 121, 122]
            >>> list(memory.values(3, 8))
            [67, None, None, 120, 121]
            >>> list(islice(memory.values(3, ...), 7))
            [67, None, None, 120, 121, 122, None]
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

    def rvalues(
        self: 'Memory',
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
            >>> from itertools import islice
            >>> memory = Memory()
            >>> list(memory.values(endex=8))
            [None, None, None, None, None, None, None]
            >>> list(memory.values(3, 8))
            [None, None, None, None, None]
            >>> list(islice(memory.values(3, ...), 7))
            [None, None, None, None, None, None, None]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67|   |   |120|121|122|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
            >>> list(memory.values())
            [65, 66, 67, None, None, 120, 121, 122]
            >>> list(memory.values(3, 8))
            [67, None, None, 120, 121]
            >>> list(islice(memory.values(3, ...), 7))
            [67, None, None, 120, 121, 122, None]
        """

        if start is None or start is Ellipsis:
            if pattern is not None:
                if isinstance(pattern, Value):
                    pattern = (pattern,)
                    pattern = bytearray(pattern)
                if not pattern:
                    raise ValueError('non-empty pattern required')

            blocks = self._blocks
            if endex is None:
                endex = self.endex
                block_index = len(blocks)
            else:
                block_index = self._block_index_endex(endex)
            endex_ = endex

            if 0 < block_index:
                block_start, block_data = blocks[block_index - 1]
                block_endex = block_start + len(block_data)

                if block_endex < endex:
                    yield from _repeat2(pattern, endex - endex_, endex - block_endex)
                    yield from reversed(block_data)
                else:
                    yield from reversed(memoryview(block_data)[:(endex - block_start)])
                endex = block_start

                for block_index in range(block_index - 2, -1, -1):
                    block_start, block_data = blocks[block_index]
                    block_endex = block_start + len(block_data)
                    yield from _repeat2(pattern, endex - endex_, endex - block_endex)
                    yield from reversed(block_data)
                    endex = block_start

            if start is Ellipsis:
                yield from _repeat2(pattern, endex - endex_, None)

        else:
            if endex is None:
                endex = self.endex
            if start < endex:
                yield from _islice(self.rvalues(Ellipsis, endex, pattern), (endex - start))

    def items(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[1, b'ABC'], [6, b'xyz']])
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

    def intervals(
        self: 'Memory',
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

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'AB'], [5, b'x'], [7, b'123']])
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

    def gaps(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        bound: bool = False,
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

            bound (bool):
                Only gaps within blocks are considered; emptiness before and
                after global data bounds are ignored.

        Yields:
            couple of addresses: Block data interval boundaries.

        Example:
            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory(blocks=[[1, b'AB'], [5, b'x'], [7, b'123']])
            >>> list(memory.gaps())
            [(None, 1), (3, 5), (6, 7), (10, None)]
            >>> list(memory.gaps(bound=True))
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
                if not bound:
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

            if endex_ is None and not bound:
                yield start, None
            elif start < endex:
                yield start, endex

        elif not bound:
            yield None, None

    def equal_span(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[0, b'ABBBC'], [7, b'CCD']])
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

    def block_span(
        self: 'Memory',
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

            >>> memory = Memory(blocks=[[0, b'ABBBC'], [7, b'CCD']])
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
