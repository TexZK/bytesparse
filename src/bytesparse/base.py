# Copyright (c) 2020-2025, Andrea Zoppi.
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

r"""Common stuff, shared across modules."""

import abc
import collections.abc
import io
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any
from typing import Union  # NOTE: type | operator unsupported for Python < 3.10

Address = int
Value = int
OptionalAddress = Union[Address, None]
OptionalValue = Union[Value, None]

ByteString = Union[bytes, bytearray, memoryview]  # NOTE: dropped by Python >= 3.14
AnyBytes = Union[ByteString, Sequence[Value]]
AnyItems = Union[AnyBytes, Value]

Block = tuple[Address, bytearray]
BlockInput = tuple[Address, Union[bytearray, bytes]]

BlockIndex = int
BlockIterable = Iterable[BlockInput]
BlockSequence = Sequence[BlockInput]
BlockList = list[Block]

OpenInterval = tuple[OptionalAddress, OptionalAddress]
ClosedInterval = tuple[Address, Address]

AddressValueMapping = Mapping[Address, Value]

try:
    from types import EllipsisType
except ImportError:  # pragma: no cover
    EllipsisType = type['Ellipsis']  # Python < 3.10

STR_MAX_CONTENT_SIZE: Address = 1000
r"""Maximum memory content size for string representation."""

HUMAN_ASCII = {k: v for k, v in enumerate(
    r'................'
    r'................'
    r' !"#$%&' r"'()*+,-./"
    r'0123456789:;<=>?'
    r'@ABCDEFGHIJKLMNO'
    r'PQRSTUVWXYZ[\]^_'
    r'`abcdefghijklmno'
    r'pqrstuvwxyz{|}~.'
    r'................'
    r'................'
    r'................'
    r'................'
    r'................'
    r'................'
    r'................'
    r'................'
    r' ><'
)}
r"""Mapping from byte to human-readable ASCII characters."""


class ImmutableMemory(collections.abc.Sequence,
                      collections.abc.Mapping):
    r"""Immutable virtual memory.

    This class is a handy wrapper around `blocks`, so that it can behave mostly
    like a :obj:`bytes`, but on sparse chunks of data.

    Being immutable, only getters and queries can be performed against
    instances of this class.

    Please look at examples of each method to get a glimpse of the features of
    this class.

    Arguments:
        start (int):
            Optional memory start address.
            Anything before will be deleted.

        endex (int):
            Optional memory exclusive end address.
            Anything at or after it will be deleted.

    Examples:
        >>> from bytesparse import Memory

        >>> memory = Memory()
        >>> memory.to_blocks()
        []

        >>> memory = Memory(start=3, endex=10)
        >>> memory.bound_span
        (3, 10)
        >>> memory.write(0, b'Hello, World!')
        >>> memory.to_blocks()
        [(3, b'lo, Wor')]

        >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
        >>> memory.to_blocks()
        [(5, b'Hello, World!')]

    Method Groups:

        Addressing:
            :meth:`__len__`
            :meth:`_block_index_at`
            :meth:`_block_index_endex`
            :meth:`_block_index_start`
            :meth:`block_span`
            :meth:`bound`
            :attr:`bound_endex`
            :attr:`bound_span`
            :attr:`bound_start`
            :attr:`content_endex`
            :attr:`content_endin`
            :attr:`content_parts`
            :attr:`content_size`
            :attr:`content_span`
            :attr:`content_start`
            :attr:`count`
            :attr:`endex`
            :attr:`endin`
            :attr:`span`
            :attr:`start`

        Comparison:
            :meth:`__bool__`
            :meth:`__eq__`
            :attr:`contiguous`
            :meth:`validate`

        Creation:
            :meth:`__copy__`
            :meth:`__deepcopy__`
            :meth:`__init__`
            :meth:`copy`
            :meth:`extract`
            :meth:`from_blocks`
            :meth:`from_bytes`
            :meth:`from_items`
            :meth:`from_memory`
            :meth:`from_values`
            :meth:`fromhex`

        Export:
            :meth:`__bytes__`
            :meth:`__repr__`
            :meth:`__str__`
            :meth:`hex`
            :meth:`hexdump`
            :meth:`read`
            :meth:`readinto`
            :meth:`to_blocks`
            :meth:`to_bytes`
            :meth:`view`

        Iteration:
            :meth:`__iter__`
            :meth:`__reversed__`
            :meth:`blocks`
            :meth:`chop`
            :meth:`content_blocks`
            :meth:`content_items`
            :meth:`content_keys`
            :meth:`content_values`
            :meth:`equal_span`
            :meth:`gaps`
            :meth:`intervals`
            :meth:`items`
            :meth:`keys`
            :meth:`rvalues`

        Search:
            :meth:`__contains__`
            :meth:`__getitem__`
            :meth:`count`
            :meth:`equal_span`
            :meth:`find`
            :meth:`index`
            :meth:`rfind`
            :meth:`rindex`

        Vector:
            :meth:`__add__`
            :meth:`__mul__`
            :meth:`__or__`
            :meth:`collapse_blocks`
            :meth:`extract`
            :meth:`get`
            :meth:`peek`
    """

    @abc.abstractmethod
    def __add__(
        self,
        value: Union[AnyBytes, 'ImmutableMemory'],
    ) -> 'ImmutableMemory':
        r"""Concatenates items.

        Equivalent to ``self.copy() += items`` of a :obj:`MutableMemory`.

        See Also:
            :meth:`MutableMemory.__iadd__`

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory.from_bytes(b'ABC')
            >>> memory2 = memory1 + b'xyz'
            >>> memory2.to_blocks()
            [(0, b'ABCxyz')]

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = Memory.from_blocks([(5, b'xyz')])
            >>> memory1.content_endex
            4
            >>> memory3 = memory1 + memory2
            >>> memory3.to_blocks()
            [(1, b'ABC'), (9, b'xyz')]
        """
        ...

    @abc.abstractmethod
    def __bool__(
        self,
    ) -> bool:
        r"""Has any items.

        Returns:
            bool: Has any items.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory()
            >>> bool(memory)
            False

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> bool(memory)
            True
        """
        ...

    @abc.abstractmethod
    def __bytes__(
        self,
    ) -> bytes:
        r"""Creates a bytes clone.

        Returns:
            :obj:`bytes`: Cloned data.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory()
            >>> bytes(memory)
            b''

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> bytes(memory)
            b'Hello, World!'

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5, start=1, endex=20)
            >>> bytes(memory)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> bytes(memory)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """
        ...

    @abc.abstractmethod
    def __contains__(
        self,
        item: Any,
    ) -> bool:
        r"""Checks if some items are contained.

        Arguments:
            item (items):
                Items to find. Can be either some byte string or an integer.

        Returns:
            bool: Item is contained.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[1 | 2 | 3]|   |[x | y | z]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'123'), (9, b'xyz')])
            >>> b'23' in memory
            True
            >>> ord('y') in memory
            True
            >>> b'$' in memory
            False
        """
        ...

    @abc.abstractmethod
    def __copy__(
        self,
    ) -> 'ImmutableMemory':
        r"""Creates a shallow copy.

        Returns:
            :obj:`ImmutableMemory`: Shallow copy.
        """
        ...

    @abc.abstractmethod
    def __deepcopy__(
        self,
    ) -> 'ImmutableMemory':
        r"""Creates a deep copy.

        Returns:
            :obj:`ImmutableMemory`: Deep copy.
        """
        ...

    @abc.abstractmethod
    def __eq__(
        self,
        other: Any,
    ) -> bool:
        r"""Equality comparison.

        Arguments:
            other (Memory):
                Data to compare with `self`.

                If it is a :obj:`ImmutableMemory`, all of its blocks must match.

                If it is a :obj:`bytes`, a :obj:`bytearray`, or a
                :obj:`memoryview`, it is expected to match the first and only
                stored block.

                Otherwise, it must match the first and only stored block,
                via iteration over the stored values.

        Returns:
            bool: `self` is equal to `other`.

        Examples:
            >>> from bytesparse import Memory

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
        ...

    @abc.abstractmethod
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
            This method is typically not optimized for a :class:`slice` where
            its `step` is an integer greater than 1.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|
            +---+---+---+---+---+---+---+---+---+---+---+
            |   | 65| 66| 67| 68|   | 36|   |120|121|122|
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory[9]  # -> ord('y') = 121
            121
            >>> memory[:3]._blocks
            [(1, b'AB')]
            >>> memory[3:10]._blocks
            [(3, b'CD'), (6, b'$'), (8, b'xy')]
            >>> bytes(memory[3:10:b'.'])
            b'CD.$.xy'
            >>> memory[memory.endex]
            None
            >>> bytes(memory[3:10:3])
            b'C$y'
            >>> memory[3:10:2]._blocks
            [(3, b'C'), (6, b'y')]
            >>> bytes(memory[3:10:2])
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """
        ...

    @abc.abstractmethod
    def __init__(
        self,
        start: Union[Address, None] = None,
        endex: Union[Address, None] = None,
    ):
        ...

    @abc.abstractmethod
    def __iter__(
        self,
    ) -> Iterator[Union[Value, None]]:
        r"""Iterates over values.

        Iterates over values between :attr:`start` and :attr:`endex`.

        Yields:
            int: Value as byte integer, or ``None``.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> list(memory)
            [65, 66, 67, None, 120, 121, 122]
        """
        ...

    @abc.abstractmethod
    def __len__(
        self,
    ) -> Address:
        r"""Actual length.

        Computes the actual length of the stored items, i.e.
        (:attr:`endex` - :attr:`start`).
        This will consider any bounds being active.

        Returns:
            int: Memory length.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory()
            >>> len(memory)
            0

            >>> memory = Memory(start=3, endex=10)
            >>> len(memory)
            7

            >>> memory = Memory.from_blocks([(1, b'ABC'), (9, b'xyz')])
            >>> len(memory)
            11

            >>> memory = Memory.from_blocks([(3, b'ABC'), (9, b'xyz')], start=1, endex=15)
            >>> len(memory)
            14
        """
        ...

    @abc.abstractmethod
    def __mul__(
        self,
        times: int,
    ) -> 'ImmutableMemory':
        r"""Concatenates a repeated copy.

        Equivalent to ``self.copy() *= items`` of a :obj:`MutableMemory`.

        See Also:
            :meth:`MutableMemory.__imul__`

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory.from_bytes(b'ABC', offset=2)
            >>> memory2 = memory1 * 3
            >>> memory2.to_blocks()
            [(0, b'ABCABCABC')]

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = memory1 * 3
            >>> memory2.to_blocks()
            [(1, b'ABCABCABC')]
        """
        ...

    @abc.abstractmethod
    def __or__(
        self,
        value: Union[AnyBytes, 'ImmutableMemory'],
    ) -> 'ImmutableMemory':
        r"""Merges memories.

        Equivalent to ``self.copy() |= items`` of a :obj:`MutableMemory`.

        See Also:
            :meth:`MutableMemory.__ior__`

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = Memory.from_blocks([(5, b'xyz')])
            >>> memory3 = memory1 | memory2
            >>> memory3.to_blocks()
            [(1, b'ABC'), (5, b'xyz')]

            >>> memory1 = Memory.from_bytes(b'ABC', offset=2)
            >>> memory2 = memory1 | b'xyz'
            >>> memory2.to_blocks()
            [(0, b'xyzBC')]
        """
        ...

    @abc.abstractmethod
    def __repr__(
        self,
    ) -> str:
        ...

    @abc.abstractmethod
    def __reversed__(
        self,
    ) -> Iterator[Union[Value, None]]:
        r"""Iterates over values, reversed order.

        Iterates over values between :attr:`start` and :attr:`endex`, in
        reversed order.

        Yields:
            int: Value as byte integer, or ``None``.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> list(memory)
            [65, 66, 67, None, 120, 121, 122]
            >>> list(reversed(memory))
            [122, 121, 120, None, 67, 66, 65]
        """
        ...

    @abc.abstractmethod
    def __str__(
        self,
    ) -> str:
        r"""String representation.

        If :attr:`content_size` is lesser than ``STR_MAX_CONTENT_SIZE``, then
        the memory is represented as a list of blocks.

        If exceeding, it is equivalent to :meth:`__repr__`.

        Returns:
            str: String representation.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (7, b'xyz')])
            >>> str(memory)
            <[(1, b'ABC'), (7, b'xyz')]>
        """
        ...

    @abc.abstractmethod
    def _block_index_at(
        self,
        address: Address,
    ) -> Union[BlockIndex, None]:
        r"""Locates the block enclosing an address.

        Returns the index of the block enclosing the given address.

        Arguments:
            address (int):
                Address of the target item.

        Returns:
            int: Block index if found, ``None`` otherwise.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   | 0 | 0 | 0 | 0 |   | 1 |   | 2 | 2 | 2 |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> [memory._block_index_at(i) for i in range(12)]
            [None, 0, 0, 0, 0, None, 1, None, 2, 2, 2, None]
        """
        ...

    @abc.abstractmethod
    def _block_index_endex(
        self,
        address: Address,
    ) -> BlockIndex:
        r"""Locates the last block before an address range.

        Returns the index of the last block whose end address is lesser than or
        equal to `address`.

        Useful to find the termination block index in a ranged search.

        Arguments:
            address (int):
                Exclusive end address of the scanned range.

        Returns:
            int: First block index before `address`.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 3 | 3 | 3 | 3 |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> [memory._block_index_endex(i) for i in range(12)]
            [0, 1, 1, 1, 1, 1, 2, 2, 3, 3, 3, 3]
        """
        ...

    @abc.abstractmethod
    def _block_index_start(
        self,
        address: Address,
    ) -> BlockIndex:
        r"""Locates the first block inside an address range.

        Returns the index of the first block whose start address is greater than
        or equal to `address`.

        Useful to find the initial block index in a ranged search.

        Arguments:
            address (int):
                Inclusive start address of the scanned range.

        Returns:
            int: First block index since `address`.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 2 | 2 | 2 | 2 | 3 |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> [memory._block_index_start(i) for i in range(12)]
            [0, 0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 3]
        """
        ...

    @abc.abstractmethod
    def block_span(
        self,
        address: Address,
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:
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
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(0, b'ABBBC'), (7, b'CCD')])
            >>> memory.block_span(2)
            (0, 5, 66)
            >>> memory.block_span(4)
            (0, 5, 67)
            >>> memory.block_span(5)
            (5, 7, None)
            >>> memory.block_span(10)
            (10, None, None)
        """
        ...

    @abc.abstractmethod
    def blocks(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[tuple[Address, memoryview]]:
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

        See Also:
            :meth:`intervals`
            :meth:`to_blocks`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> [[s, bytes(d)] for s, d in memory.blocks()]
            [(1, b'AB'), (5, b'x'), (7, b'123')]
            >>> [[s, bytes(d)] for s, d in memory.blocks(2, 9)]
            [(2, b'B'), (5, b'x'), (7, b'12')]
            >>> [[s, bytes(d)] for s, d in memory.blocks(3, 5)]
            []
        """
        ...

    @abc.abstractmethod
    def bound(
        self,
        start: OptionalAddress,
        endex: OptionalAddress,
    ) -> ClosedInterval:
        r"""Bounds addresses.

        It bounds the given addresses to stay within memory limits.
        ``None`` is used to ignore a limit for the `start` or `endex`
        directions.

        In case of stored data, :attr:`content_start` and
        :attr:`content_endex` are used as bounds.

        In case of bounds limits, :attr:`bound_start` or :attr:`bound_endex`
        are used as bounds, when not ``None``.

        In case `start` and `endex` are in the wrong order, one clamps
        the other if present (see the Python implementation for details).

        Returns:
            tuple of int: Bounded `start` and `endex`, closed interval.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
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

            >>> memory = Memory.from_blocks([(3, b'ABC')], start=1, endex=8)
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
        ...

    @property
    @abc.abstractmethod
    def bound_endex(
        self,
    ) -> OptionalAddress:
        r"""int: Bounds exclusive end address.

        Any data at or after this address is automatically discarded.
        Disabled if ``None``.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> memory.bound_endex = 10
            >>> memory.to_blocks()
            [(5, b'Hello')]

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5, endex=10)
            >>> memory.to_blocks()
            [(5, b'Hello')]
        """
        ...

    @property
    @abc.abstractmethod
    def bound_span(
        self,
    ) -> OpenInterval:
        r"""tuple of int: Bounds span addresses.

        A :obj:`tuple` holding :attr:`bound_start` and :attr:`bound_endex`.

        Notes:
            Assigning ``None`` to :attr:`MutableMemory.bound_span` sets both
            :attr:`bound_start` and :attr:`bound_endex` to ``None``
            (equivalent to ``(None, None)``).

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> memory.bound_span = (7, 13)
            >>> memory.to_blocks()
            [(7, b'llo, W')]
            >>> memory.bound_span = None
            >>> memory.bound_span
            (None, None)

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5, start=7, endex=13)
            >>> memory.to_blocks()
            [(7, b'llo, W')]
        """
        ...

    @property
    @abc.abstractmethod
    def bound_start(
        self,
    ) -> OptionalAddress:
        r"""int: Bounds start address.

        Any data before this address is automatically discarded.
        Disabled if ``None``.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> memory.bound_start = 10
            >>> memory.to_blocks()
            [(10, b', World!')]

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5, start=10)
            >>> memory.to_blocks()
            [(10, b', World!')]
        """
        ...

    @abc.abstractmethod
    def chop(
        self,
        width: Address,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        align: bool = False,
    ) -> Iterator[tuple[Address, memoryview]]:
        r"""Iterates over chopped blocks.

        The provided range is split into sub-ranges of a fixed width.
        For each sub-range, it yields views of the contained block chunks.

        Arguments:
            width (int):
                Sub-range width.

            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

            align (bool):
                Sub-ranges are aligned to `width`.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B]|[C]|   |   |[x | y]|[z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A]|[B | C]|   |   |[x | y]|[z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> chopping = memory.chop(2, align=False)
            >>> [(address, bytes(view)) for address, view in chopping]
            [(1, b'AB'), (3, b'C'), (6, b'xy'), (8, b'z')]
            >>> chopping = memory.chop(2, align=True)
            >>> [(address, bytes(view)) for address, view in chopping]
            [(1, b'A'), (2, b'BC'), (6, b'xy'), (8, b'z')]
        """
        ...

    @classmethod
    @abc.abstractmethod
    def collapse_blocks(
        cls,
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
            >>> from bytesparse import Memory

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
            ...     (0, b'0123456789'),
            ...     (0, b'ABCD'),
            ...     (3, b'EF'),
            ...     (0, b'$'),
            ...     (6, b'xyz'),
            ... ]
            >>> Memory.collapse_blocks(blocks)
            [(0, b'$BCEF5xyz9')]

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
            ...     (0, b'012'),
            ...     (4, b'AB'),
            ...     (6, b'xyz'),
            ...     (1, b'$'),
            ... ]
            >>> Memory.collapse_blocks(blocks)
            [(0, b'0$2'), (4, b'ABxyz')]
        """
        ...

    @abc.abstractmethod
    def content_blocks(
        self,
        block_index_start: Union[BlockIndex, None] = None,
        block_index_endex: Union[BlockIndex, None] = None,
        block_index_step: Union[BlockIndex, None] = None,
    ) -> Iterator[Union[tuple[Address, Union[memoryview, bytearray]], Block]]:
        r"""Iterates over blocks.

        Iterates over data blocks within a block index range.

        Arguments:
            block_index_start (int):
                Inclusive block start index.
                A negative index is referred to :attr:`content_parts`.
                If ``None``, ``0`` is considered.

            block_index_endex (int):
                Exclusive block end index.
                A negative index is referred to :attr:`content_parts`.
                If ``None``, :attr:`content_parts` is considered.

            block_index_step (int):
                Block index step, which can be negative.
                If ``None``, ``1`` is considered.

        Yields:
            (start, memoryview): Start and data view of each block/slice.

        See Also:
            :attr:`content_parts`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> [[s, bytes(d)] for s, d in memory.content_blocks()]
            [(1, b'AB'), (5, b'x'), (7, b'123')]
            >>> [[s, bytes(d)] for s, d in memory.content_blocks(1, 2)]
            [(5, b'x')]
            >>> [[s, bytes(d)] for s, d in memory.content_blocks(3, 5)]
            []
            >>> [[s, bytes(d)] for s, d in memory.content_blocks(block_index_start=-2)]
            [(5, b'x'), (7, b'123')]
            >>> [[s, bytes(d)] for s, d in memory.content_blocks(block_index_endex=-1)]
            [(1, b'AB'), (5, b'x')]
            >>> [[s, bytes(d)] for s, d in memory.content_blocks(block_index_step=2)]
            [(1, b'AB'), (7, b'123')]
        """
        ...

    @property
    @abc.abstractmethod
    def content_endex(
        self,
    ) -> Address:
        r"""int: Exclusive content end address.

        This property holds the exclusive end address of the memory content.
        By default, it is the current maximmum exclusive end address of
        the last stored block.

        If the memory has no data and no bounds, :attr:`start` is returned.

        Bounds considered only for an empty memory.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.content_endex
            4
        """
        ...

    @property
    @abc.abstractmethod
    def content_endin(
        self,
    ) -> Address:
        r"""int: Inclusive content end address.

        This property holds the inclusive end address of the memory content.
        By default, it is the current maximmum inclusive end address of
        the last stored block.

        If the memory has no data and no bounds, :attr:`start` minus one is
        returned.

        Bounds considered only for an empty memory.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.content_endin
            3
        """
        ...

    @abc.abstractmethod
    def content_items(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[tuple[Address, Value]]:
        r"""Iterates over content address and value pairs.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            int: Content address and value pairs.

        See Also:
            meth:`content_keys`
            meth:`content_values`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> dict(memory.content_items())
            {1: 65, 2: 66, 5: 120, 7: 49, 8: 50, 9: 51}
            >>> dict(memory.content_items(2, 9))
            {2: 66, 5: 120, 7: 49, 8: 50}
            >>> dict(memory.content_items(3, 5))
            {}
        """
        ...

    @abc.abstractmethod
    def content_keys(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[Address]:
        r"""Iterates over content addresses.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            int: Content addresses.

        See Also:
            meth:`content_items`
            meth:`content_values`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> list(memory.content_keys())
            [1, 2, 5, 7, 8, 9]
            >>> list(memory.content_keys(2, 9))
            [2, 5, 7, 8]
            >>> list(memory.content_keys(3, 5))
            []
        """
        ...

    @property
    @abc.abstractmethod
    def content_parts(
        self,
    ) -> int:
        r"""Number of blocks.

        Returns:
            int: The number of blocks.

        Examples:
            >>> from bytesparse import Memory

            >>> Memory().content_parts
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_parts
            2

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.content_parts
            1
        """
        ...

    @property
    @abc.abstractmethod
    def content_size(
        self,
    ) -> Address:
        r"""Actual content size.

        Returns:
            int: The sum of all block lengths.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_size
            6

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.content_size
            3
        """
        ...

    @property
    @abc.abstractmethod
    def content_span(
        self,
    ) -> ClosedInterval:
        r"""tuple of int: Memory content address span.

        A :attr:`tuple` holding both :attr:`content_start` and
        :attr:`content_endex`.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_span
            (1, 8)
        """
        ...

    @property
    @abc.abstractmethod
    def content_start(
        self,
    ) -> Address:
        r"""int: Inclusive content start address.

        This property holds the inclusive start address of the memory content.
        By default, it is the current minimum inclusive start address of
        the first stored block.

        If the memory has no data and no bounds, 0 is returned.

        Bounds considered only for an empty memory.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.content_start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'xyz')], start=1)
            >>> memory.content_start
            5
        """
        ...

    @abc.abstractmethod
    def content_values(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[Value]:
        r"""Iterates over content values.

        Arguments:
            start (int):
                Inclusive start address.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address.
                If ``None``, :attr:`endex` is considered.

        Yields:
            int: Content values.

        See Also:
            meth:`content_items`
            meth:`content_keys`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> list(memory.content_values())
            [65, 66, 120, 49, 50, 51]
            >>> list(memory.content_values(2, 9))
            [66, 120, 49, 50]
            >>> list(memory.content_values(3, 5))
            []
        """
        ...

    @property
    @abc.abstractmethod
    def contiguous(
        self,
    ) -> bool:
        r"""bool: Contains contiguous data.

        The memory is considered to have contiguous data if there is no empty
        space between blocks.

        If bounds are defined, there must be no empty space also towards them.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory()
            >>> memory.contiguous
            True

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> memory.contiguous
            True

            >>> memory = Memory.from_bytes(b'Hello, World!', offset=5, start=1, endex=20)
            >>> memory.contiguous
            False

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory.contiguous
            False
        """
        ...

    @abc.abstractmethod
    def copy(
        self,
    ) -> 'ImmutableMemory':
        r"""Creates a deep copy.

        Returns:
            :obj:`ImmutableMemory`: Deep copy.

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory()
            >>> memory2 = memory1.copy()
            >>> memory2.bound_span
            (None, None)
            >>> memory2.to_blocks()
            []

            >>> memory1 = Memory(start=1, endex=20)
            >>> memory2 = memory1.copy()
            >>> memory2.bound_span
            (1, 20)
            >>> memory2.to_blocks()
            []

            >>> memory1 = Memory.from_bytes(b'Hello, World!', offset=5)
            >>> memory2 = memory1.copy()
            >>> memory2.to_blocks()
            [(5, b'Hello, World!')]

            >>> memory1 = Memory.from_bytes(b'Hello, World!', offset=5, start=1, endex=20)
            >>> memory2 = memory1.copy()
            >>> memory2.bound_span
            (1, 20)
            >>> memory2.to_blocks()
            [(5, b'Hello, World!')]
            >>> memory2.bound_span = (2, 19)
            >>> memory1 == memory2
            True

            >>> memory1 = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory2 = memory1.copy()
            [(5, b'ABC'), (9, b'xyz')]
            >>> memory1 == memory2
            True
        """
        ...

    @abc.abstractmethod
    def count(
        self,
        value: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> int:
        r"""Counts values.

        Arguments:
            value (values):
                Reference value to count.

            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

        Returns:
            int: The number of values equal to `value`.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[B | a | t]|   |[t | a | b]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'Bat'), (9, b'tab')])
            >>> memory.count(b'a')
            2
        """
        ...

    @property
    @abc.abstractmethod
    def endex(
        self,
    ) -> Address:
        r"""int: Exclusive end address.

        This property holds the exclusive end address of the virtual space.
        By default, it is the current maximmum exclusive end address of
        the last stored block.

        If  :attr:`bound_endex` not ``None``, that is returned.

        If the memory has no data and no bounds, :attr:`start` is returned.

        Examples:
            >>> from bytesparse import Memory

            >>> Memory().endex
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.endex
            8

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.endex
            8
        """
        ...

    @property
    @abc.abstractmethod
    def endin(
        self,
    ) -> Address:
        r"""int: Inclusive end address.

        This property holds the inclusive end address of the virtual space.
        By default, it is the current maximmum inclusive end address of
        the last stored block.

        If  :attr:`bound_endex` not ``None``, that minus one is returned.

        If the memory has no data and no bounds, :attr:`start` is returned.

        Examples:
            >>> from bytesparse import Memory

            >>> Memory().endin
            -1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.endin
            7

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |)))|
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC')], endex=8)
            >>> memory.endin
            7
        """
        ...

    @abc.abstractmethod
    def equal_span(
        self,
        address: Address,
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:
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
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(0, b'ABBBC'), (7, b'CCD')])
            >>> memory.equal_span(2)
            (1, 4, 66)
            >>> memory.equal_span(4)
            (4, 5, 67)
            >>> memory.equal_span(5)
            (5, 7, None)
            >>> memory.equal_span(10)
            (10, None, None)
        """
        ...

    @abc.abstractmethod
    def extract(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: Union[ByteString, Value, None] = None,
        step: OptionalAddress = None,
        bound: bool = True,
    ) -> 'ImmutableMemory':
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
                as its bounds range. This retains information about any
                initial and final emptiness of that range, which would be lost
                otherwise.

        Returns:
            :obj:`ImmutableMemory`: A copy of the memory from the selected range.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.extract()._blocks
            [(1, b'ABCD'), (6, b'$'), (8, b'xyz')]
            >>> memory.extract(2, 9)._blocks
            [(2, b'BCD'), (6, b'$'), (8, b'x')]
            >>> memory.extract(start=2)._blocks
            [(2, b'BCD'), (6, b'$'), (8, b'xyz')]
            >>> memory.extract(endex=9)._blocks
            [(1, b'ABCD'), (6, b'$'), (8, b'x')]
            >>> memory.extract(5, 8).span
            (5, 8)
            >>> memory.extract(pattern=b'.')._blocks
            [(1, b'ABCD.$.xyz')]
            >>> memory.extract(pattern=b'.', step=3)._blocks
            [(1, b'AD.z')]
        """
        ...

    @abc.abstractmethod
    def find(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        Warnings:
            If the memory allows negative addresses, :meth:`index` is more
            appropriate, because it raises :obj:`ValueError` if the item is
            not found.

        See Also:
            :meth:`index`
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_blocks(
        cls,
        blocks: BlockSequence,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from blocks.

        Arguments:
            blocks (list of blocks):
                A sequence of non-overlapping blocks, sorted by address.

            offset (int):
                Some address offset applied to all the blocks.

            start (int):
                Optional memory start address.
                Anything before will be deleted.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be deleted.

            copy (bool):
                Forces copy of provided input data.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        See Also:
            :meth:`to_blocks`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> blocks = [(1, b'ABC'), (5, b'xyz')]
            >>> memory = Memory.from_blocks(blocks)
            >>> memory.to_blocks()
            [(1, b'ABC'), (5, b'xyz')]
            >>> memory = Memory.from_blocks(blocks, offset=3)
            >>> memory.to_blocks()
            [(4, b'ABC'), (8, b'xyz')]

            ~~~

            >>> # Loads data from an Intel HEX record file
            >>> # NOTE: Record files typically require collapsing!
            >>> import hexrec.records as hr  # noqa
            >>> blocks = hr.load_blocks('records.hex')
            >>> memory = Memory.from_blocks(Memory.collapse_blocks(blocks))
            >>> memory
                ...
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_bytes(
        cls,
        data: AnyBytes,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from a byte-like chunk.

        Arguments:
            data (byte-like data):
                A byte-like chunk of data (e.g. :obj:`bytes`,
                :obj:`bytearray`, :obj:`memoryview`).

            offset (int):
                Start address of the block of data.

            start (int):
                Optional memory start address.
                Anything before will be deleted.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be deleted.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        See Also:
            :meth:`to_bytes`

        Examples:
            >>> from bytesparse import Memory

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
            [(2, b'ABCxyz')]
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_items(
        cls,
        items: object,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        validate: bool = True,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from a iterable address/byte mapping.

        Arguments:
            items (iterable address/byte mapping):
                An iterable mapping of address to byte values.
                Values of ``None`` are translated as gaps.
                When an address is stated multiple times, the last is kept.

            offset (int):
                An address offset applied to all the values.

            start (int):
                Optional memory start address.
                Anything before will be deleted.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be deleted.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        See Also:
            :meth:`to_bytes`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_values({})
            >>> memory.to_blocks()
            []

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |   |[A | Z]|   |[x]|   |   |   |
            +---+---+---+---+---+---+---+---+---+

            >>> items = [
            ...     (0, ord('A')),
            ...     (1, ord('B')),
            ...     (3, ord('x')),
            ...     (1, ord('Z')),
            ... ]
            >>> memory = Memory.from_items(items, offset=2)
            >>> memory.to_blocks()
            [(2, b'AZ'), (5, b'x')]
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_memory(
        cls,
        memory: 'ImmutableMemory',
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from another one.

        Arguments:
            memory (Memory):
                A :obj:`ImmutableMemory` to copy data from.

            offset (int):
                Some address offset applied to all the blocks.

            start (int):
                Optional memory start address.
                Anything before will be deleted.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be deleted.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`MemorImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory.from_bytes(b'ABC', 5)
            >>> memory2 = Memory.from_memory(memory1)
            >>> memory2._blocks
            [(5, b'ABC')]
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
            [(7, b'ABC')]
            >>> memory1 == memory2
            False

            ~~~

            >>> memory1 = Memory.from_bytes(b'ABC', 10)
            >>> memory2 = Memory.from_memory(memory1, copy=False)
            >>> all((b1[1] is b2[1])  # compare block data
            ...     for b1, b2 in zip(memory1._blocks, memory2._blocks))
            True
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_values(
        cls,
        values: Iterable[OptionalValue],
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        validate: bool = True,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from a byte-like sequence.

        Arguments:
            values (iterable byte-like sequence):
                An iterable sequence of byte values.
                Values of ``None`` are translated as gaps.

            offset (int):
                An address offset applied to all the values.

            start (int):
                Optional memory start address.
                Anything before will be deleted.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be deleted.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.

        See Also:
            :meth:`to_bytes`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_values(range(0))
            >>> memory.to_blocks()
            []

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |   |[A | B | C | D | E]|   |   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_values(range(ord('A'), ord('F')), offset=2)
            >>> memory.to_blocks()
            [(2, b'ABCDE')]
        """
        ...

    @classmethod
    @abc.abstractmethod
    def fromhex(
        cls,
        string: str,
    ) -> 'ImmutableMemory':
        r"""Creates a virtual memory from an hexadecimal string.

        Arguments:
            string (str):
                Hexadecimal string.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.fromhex('')
            >>> bytes(memory)
            b''

            ~~~

            >>> memory = Memory.fromhex('48656C6C6F2C20576F726C6421')
            >>> bytes(memory)
            b'Hello, World!'
        """
        ...

    @abc.abstractmethod
    def gaps(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            pair of addresses: Block data interval boundaries.

        See Also:
            :meth:`intervals`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> list(memory.gaps())
            [(None, 1), (3, 5), (6, 7), (10, None)]
            >>> list(memory.gaps(0, 11))
            [(0, 1), (3, 5), (6, 7), (10, 11)]
            >>> list(memory.gaps(*memory.span))
            [(3, 5), (6, 7)]
            >>> list(memory.gaps(2, 6))
            [(3, 5)]
        """
        ...

    @abc.abstractmethod
    def get(
        self,
        address: Address,
        default: Any = None,
    ) -> OptionalValue:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, `default` if empty.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
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
        ...

    @abc.abstractmethod
    def hex(
        self,
        *args: Any,  # see docstring
    ) -> str:
        r"""Converts into an hexadecimal string.

        Arguments:
            sep (str):
                Separator string between bytes.
                Defaults to an emoty string if not provided.
                Available since Python 3.8.

            bytes_per_sep (int):
                Number of bytes grouped between separators.
                Defaults to one byte per group.
                Available since Python 3.8.

        Returns:
            str: Hexadecimal string representation.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> from bytesparse import Memory

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
        ...

    @abc.abstractmethod
    def hexdump(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        columns: int = 16,
        addrfmt: str = '{:08X} ',
        bytefmt: str = ' {:02X}',
        headfmt: Union[str, EllipsisType, None] = None,  # type: ignore EllipsisType
        charmap: Union[Mapping[int, str], None] = HUMAN_ASCII,
        emptystr: str = ' --',
        beforestr: str = ' >>',
        afterstr: str = ' <<',
        charsep: str = '  |',
        charend: str = '|',
        stream: Union[io.TextIOBase, EllipsisType, None] = Ellipsis,  # type: ignore EllipsisType
    ) -> Union[str, None]:
        r"""Textual hex dump.

        This function generates a hex dump of the bytes within the specified
        range.

        If `stream` is not ``None``, the hex dump is written on it, otherwise
        it is returned as a :obj:`str`.

        The default output is similar to that of ``hexdump`` or ``xxd``
        commands, with some degree of tweaking.
        In case more customized formatting is desired, a dedicated custom
        function can be written by carefully looping over :meth:`values`.

        Arguments:
            start (int):
                Inclusive start of the searched range.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end of the searched range.
                If ``None``, :attr:`endex` is considered.

            columns (int):
                Number of byte columns per row.

            addrfmt (str):
                Address formatting string.

            bytefmt (str):
                Byte formatting string.

            headfmt (str):
                Header offset formatting string.
                If ``Ellipsis``, it applies that of `bytefmt`.
                If ``None``, no header row is generated.

            charmap (mapping):
                Mapping to convert a byte integer into a string character.
                If ``None``, no character data are appended to each row.

                The table is structured this way:

                * The initial 256 bytes map actual byte values.
                * Index ``0x100`` represents an empty byte (``None``).
                * Index ``0x101`` represents a byte before :attr:`start`.
                * Index ``0x102`` represents a byte after :attr:`endex`.

            emptystr (str):
                Placeholder for an empty byte (``None`` value).

            beforestr (str):
                Placeholder for a byte before :attr:`bound_start`.

            afterstr (str):
                Placeholder for a byte after :attr:`bound_endex`.

            charsep (str):
                Separator between byte data and character data.

            charend (str):
                Separator after character data.

            stream (IO stream):
                Stream to write text onto.
                If ``Ellipsis``, it uses ``sys.stdout``.
                If not ``None``, the function returns ``None``.

        Returns:
            str: Textual hex dump, if `stream` is ``None``.

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')], offset=0xDA7A)
            >>> memory.hexdump()
            0000DA7B  41 42 43 -- -- 78 79 7A -- -- -- -- -- -- -- --  |ABC  xyz        |
            >>> memory.hexdump(stream=None)
            '0000DA7B  41 42 43 -- -- 78 79 7A -- -- -- -- -- -- -- --  |ABC  xyz        |'
            >>> memory.hexdump(start=0xDA7A, charmap=None)
            0000DA7A  -- 41 42 43 -- -- 78 79 7A -- -- -- -- -- -- --
            >>> memory.hexdump(start=0xDA7A)
            0000DA7A  -- 41 42 43 -- -- 78 79 7A -- -- -- -- -- -- --  | ABC  xyz       |
            >>> memory.hexdump(start=0xDA70)
            0000DA70  -- -- -- -- -- -- -- -- -- -- -- 41 42 43 -- --  |           ABC  |
            0000DA80  78 79 7A -- -- -- -- -- -- -- -- -- -- -- -- --  |xyz             |
            >>> memory.bound_span = (0xDA78, 0xDA88)
            >>> memory.hexdump(start=0xDA70)
            0000DA70  >> >> >> >> >> >> >> >> -- -- -- 41 42 43 -- --  |>>>>>>>>   ABC  |
            0000DA80  78 79 7A -- -- -- -- -- << << << << << << << <<  |xyz     <<<<<<<<|
            >>> memory.hexdump(start=0xDA70, headfmt=...)
                      00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
            0000DA70  >> >> >> >> >> >> >> >> -- -- -- 41 42 43 -- --  |>>>>>>>>   ABC  |
            0000DA80  78 79 7A -- -- -- -- -- << << << << << << << <<  |xyz     <<<<<<<<|
            >>> memory.hexdump(start=0xDA78, endex=0xDA84, columns=4)
            0000DA78  -- -- -- 41  |   A|
            0000DA7C  42 43 -- --  |BC  |
            0000DA80  78 79 7A --  |xyz |
        """
        ...

    @abc.abstractmethod
    def index(  # type: ignore override
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        See Also:
            :meth:`find`
        """
        ...

    @abc.abstractmethod
    def intervals(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            pair of addresses: Block data interval boundaries.

        See Also:
            :meth:`blocks`
            :meth:`gaps`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> list(memory.intervals())
            [(1, 3), (5, 6), (7, 10)]
            >>> list(memory.intervals(2, 9))
            [(2, 3), (5, 6), (7, 9)]
            >>> list(memory.intervals(3, 5))
            []
        """
        ...

    @abc.abstractmethod
    def items(  # type: ignore override
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,  # type: ignore EllipsisType
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[tuple[Address, OptionalValue]]:
        r"""Iterates over address and value pairs.

        Iterates over address and value pairs, from `start` to `endex`.
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
            int: Range address and value pairs.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> list(memory.items())
            [(1, 65), (2, 66), (3, 67), (4, None), (5, None), (6, 120), (7, 121), (8, 122)]
            >>> list(memory.items(3, 8))
            [(3, 67), (4, None), (5, None), (6, 120), (7, 121)]
            >>> list(islice(memory.items(3, ...), 7))
            [(3, 67), (4, None), (5, None), (6, 120), (7, 121), (8, 122), (9, None)]
        """
        ...

    @abc.abstractmethod
    def keys(  # type: ignore override
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,  # type: ignore EllipsisType
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
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> list(memory.keys())
            [1, 2, 3, 4, 5, 6, 7, 8]
            >>> list(memory.keys(endex=8))
            [1, 2, 3, 4, 5, 6, 7]
            >>> list(memory.keys(3, 8))
            [3, 4, 5, 6, 7]
            >>> list(islice(memory.keys(3, ...), 7))
            [3, 4, 5, 6, 7, 8, 9]
        """
        ...

    @abc.abstractmethod
    def peek(
        self,
        address: Address,
    ) -> OptionalValue:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, ``None`` if empty.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
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
        ...

    @abc.abstractmethod
    def read(
        self,
        address: Address,
        size: Address,
    ) -> memoryview:
        r"""Reads data.

        Reads a chunk of data from an address, with a given size.
        Data within the range is required to be contiguous.

        Arguments:
            address (int):
                Start address of the chunk to read.

            size (int):
                Chunk size.

        Returns:
            :obj:`memoryview`: A view over the addressed chunk.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> bytes(memory.read(2, 3))
            b'BCD'
            >>> bytes(memory.read(9, 1))
            b'y'
            >>> memory.read(4, 3)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
            >>> memory.read(0, 6)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """
        ...

    @abc.abstractmethod
    def readinto(
        self,
        address: Address,
        buffer: Union[bytearray, memoryview],
    ) -> int:
        r"""Reads data into a pre-allocated buffer.

        Provided a pre-allocated writable buffer (*e.g.* a :obj:`bytearray`
        or a :obj:`memoryview` slice of it), this method reads a chunk of data
        from an address, with the size of the target buffer.
        Data within the range is required to be contiguous.

        Arguments:
            address (int):
                Start address of the chunk to read.

            buffer (writable):
                Pre-allocated buffer to fill with data.

        Returns:
            int: Number of bytes read.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> buffer = bytearray(3)
            >>> memory.readinto(2, buffer)
            3
            >>> buffer
            bytearray(b'BCD')
            >>> view = memoryview(buffer)
            >>> memory.readinto(9, view[1:2])
            1
            >>> buffer
            bytearray(b'ByD')
            >>> memory.readinto(4, buffer)
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
            >>> memory.readinto(0, bytearray(6))
            Traceback (most recent call last):
                ...
            ValueError: non-contiguous data within range
        """
        ...

    @abc.abstractmethod
    def rfind(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        Warnings:
            If the memory allows negative addresses, :meth:`rindex` is more
            appropriate, because it raises :obj:`ValueError` if the item is
            not found.

        See Also:
            :meth:`rindex`
        """
        ...

    @abc.abstractmethod
    def rindex(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        Warnings:
            If the memory allows negative addresses, :meth:`index` is more
            appropriate, because it raises :obj:`ValueError` if the item is
            not found.

        See Also:
            :meth:`rfind`
        """
        ...

    @abc.abstractmethod
    def rvalues(
        self,
        start: Union[Address, EllipsisType, None] = None,  # type: ignore EllipsisType
        endex: OptionalAddress = None,
        pattern: Union[AnyBytes, Value, None] = None,
    ) -> Iterator[OptionalValue]:
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
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> list(memory.rvalues())
            [122, 121, 120, None, None, 67, 66, 65]
            >>> list(memory.rvalues(3, 8))
            [121, 120, None, None, 67]
            >>> list(islice(memory.rvalues(..., 8), 7))
            [121, 120, None, None, 67, 66, 65]
            >>> list(memory.rvalues(3, 8, b'0123'))
            [121, 120, 50, 49, 67]
        """
        ...

    @property
    @abc.abstractmethod
    def span(
        self,
    ) -> ClosedInterval:
        r"""tuple of int: Memory address span.

        A :obj:`tuple` holding both :attr:`start` and :attr:`endex`.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.span
            (1, 8)
        """
        ...

    @property
    @abc.abstractmethod
    def start(
        self,
    ) -> Address:
        r"""int: Inclusive start address.

        This property holds the inclusive start address of the virtual space.
        By default, it is the current minimum inclusive start address of
        the first stored block.

        If :attr:`bound_start` not ``None``, that is returned.

        If the memory has no data and no bounds, 0 is returned.

        Examples:
            >>> from bytesparse import Memory

            >>> Memory().start
            0

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.start
            1

            ~~~

            +---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
            +===+===+===+===+===+===+===+===+===+
            |   |[[[|   |   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'xyz')], start=1)
            >>> memory.start
            1
        """
        ...

    @abc.abstractmethod
    def to_blocks(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[tuple[Address, bytes]]:
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

        See Also:
            :meth:`blocks`
            :meth:`from_blocks`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B]|   |   |[x]|   |[1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'AB'), (5, b'x'), (7, b'123')])
            >>> memory.to_blocks()
            [(1, b'AB'), (5, b'x'), (7, b'123')]
            >>> memory.to_blocks(2, 9)
            [(2, b'B'), (5, b'x'), (7, b'12')]
            >>> memory.to_blocks(3, 5)]
            []
        """
        ...

    @abc.abstractmethod
    def to_bytes(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        See Also:
            :meth:`from_bytes`
            :meth:`view`

        Examples:
            >>> from bytesparse import Memory

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
        """
        ...

    @abc.abstractmethod
    def validate(
        self,
    ) -> None:
        r"""Validates internal structure.

        It makes sure that all the allocated blocks are sorted by block start
        address, and that all the blocks are non-overlapping.

        Raises:
            :obj:`ValueError`: Invalid data detected (see exception message).
        """
        ...

    @abc.abstractmethod
    def values(  # type: ignore override
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,  # type: ignore EllispsType
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[OptionalValue]:
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
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> list(memory.values())
            [65, 66, 67, None, None, 120, 121, 122]
            >>> list(memory.values(3, 8))
            [67, None, None, 120, 121]
            >>> list(islice(memory.values(3, ...), 7))
            [67, None, None, 120, 121, 122, None]
            >>> list(memory.values(3, 8, b'0123'))
            [67, 49, 50, 120, 121]
        """
        ...

    @abc.abstractmethod
    def view(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
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
        ...


class MutableMemory(  # type: ignore override
        ImmutableMemory,
        collections.abc.MutableSequence,
        collections.abc.MutableMapping
):
    r"""Mutable virtual memory.

    This class is a handy wrapper around `blocks`, so that it can behave mostly
    like a :obj:`bytearray`, but on sparse chunks of data.

    Being mutable, instances of this class can be updated dynamically.
    All the methods and attributes of an :obj:`ImmutableMemory` are
    available as well.

    Please look at examples of each method to get a glimpse of the features of
    this class.

    See Also:
        :obj:`ImmutableMemory`

    Method Groups:

        Setting:
            :meth:`__setitem__`
            :attr:`bound_endex`
            :attr:`bound_span`
            :attr:`bound_start`
            :meth:`poke`
            :meth:`reverse`
            :meth:`setdefault`
            :meth:`shift`

        Merging:
            :meth:`__ior__`
            :meth:`align`
            :meth:`fill`
            :meth:`flood`
            :meth:`update`

        Extension:
            :meth:`__iadd__`
            :meth:`__imul__`
            :meth:`append`
            :meth:`extend`
            :meth:`insert`
            :meth:`reserve`
            :meth:`write`

        Deletion:
            :meth:`__delitem__`
            :meth:`clear`
            :meth:`crop`
            :meth:`cut`
            :meth:`delete`
            :meth:`pop`
            :meth:`popitem`
            :meth:`remove`

        Backup:
            :meth:`align_backup`
            :meth:`append_backup`
            :meth:`clear_backup`
            :meth:`crop_backup`
            :meth:`delete_backup`
            :meth:`extend_backup`
            :meth:`fill_backup`
            :meth:`flood_backup`
            :meth:`insert_backup`
            :meth:`poke_backup`
            :meth:`pop_backup`
            :meth:`popitem_backup`
            :meth:`remove_backup`
            :meth:`reserve_backup`
            :meth:`setdefault_backup`
            :meth:`shift_backup`
            :meth:`update_backup`
            :meth:`write_backup`

        Restore:
            :meth:`align_restore`
            :meth:`append_restore`
            :meth:`clear_restore`
            :meth:`crop_restore`
            :meth:`delete_restore`
            :meth:`extend_restore`
            :meth:`fill_restore`
            :meth:`flood_restore`
            :meth:`insert_restore`
            :meth:`poke_restore`
            :meth:`pop_restore`
            :meth:`popitem_restore`
            :meth:`remove_restore`
            :meth:`reserve_restore`
            :meth:`setdefault_restore`
            :meth:`shift_restore`
            :meth:`update_restore`
            :meth:`write_restore`

        Internal:
            :meth:`_prebound_endex`
            :meth:`_prebound_endex_backup`
            :meth:`_prebound_start`
            :meth:`_prebound_start_backup`
    """
    __doc__ += ImmutableMemory.__doc__[  # type: ignore __doc__
        ImmutableMemory.__doc__.index('Arguments:'):  # type: ignore __doc__
        ImmutableMemory.__doc__.index('Method Groups:')  # type: ignore __doc__
    ]

    @abc.abstractmethod
    def __delitem__(
        self,
        key: Union[Address, slice],
    ) -> None:
        r"""Deletes data.

        Arguments:
            key (slice or int):
                Deletion range or address.

        Note:
            This method is typically not optimized for a :class:`slice` where
            its `step` is an integer greater than 1.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | y | z]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> del memory[4:9]
            >>> memory.to_blocks()
            [(1, b'ABCyz')]

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

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> del memory[9]
            >>> memory.to_blocks()
            [(1, b'ABCD'), (6, b'$'), (8, b'xz')]
            >>> del memory[3]
            >>> memory.to_blocks()
            [(1, b'ABD'), (5, b'$'), (7, b'xz')]
            >>> del memory[2:10:3]
            >>> memory.to_blocks()
            [(1, b'AD'), (5, b'x')]
        """
        ...

    @abc.abstractmethod
    def __iadd__(  # type: ignore override
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'MutableMemory':
        r"""Concatenates items.

        Equivalent to ``self.extend(value)``.

        See Also:
            :meth:`extend`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_bytes(b'ABC')
            >>> memory += b'xyz'
            >>> memory.to_blocks()
            [(0, b'ABCxyz')]

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = Memory.from_blocks([(5, b'xyz')])
            >>> memory1.content_endex
            4
            >>> memory1 += memory2
            >>> memory1.to_blocks()
            [(1, b'ABC'), (9, b'xyz')]
        """
        ...

    @abc.abstractmethod
    def __imul__(
        self,
        times: int,
    ) -> 'MutableMemory':
        r"""Concatenates a repeated copy.

        Equivalent to ``self.extend(items)`` repeated `times` times.

        See Also:
            :meth:`extend`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_bytes(b'ABC')
            >>> memory *= 3
            >>> memory.to_blocks()
            [(0, b'ABCABCABC')]

            >>> memory = Memory.from_blocks([(1, b'ABC')])
            >>> memory *= 3
            >>> memory.to_blocks()
            [(1, b'ABCABCABC')]
        """
        ...

    @abc.abstractmethod
    def __ior__(
        self,
        value: Union[AnyBytes, 'ImmutableMemory'],
    ) -> 'MutableMemory':
        r"""Merges memories.

        Equivalent to ``self.write(0, value)``.

        See Also:
            :meth:`extend`

        See Also:
            :meth:`MutableMemory.__ior__`

        Examples:
            >>> from bytesparse import Memory

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = Memory.from_blocks([(5, b'xyz')])
            >>> memory1 |= memory2
            >>> memory1.to_blocks()
            [(1, b'ABC'), (5, b'xyz')]

            >>> memory1 = Memory.from_bytes(b'ABC', offset=2)
            >>> memory1 |= b'xyz'
            >>> memory2.to_blocks()
            [(0, b'xyzBC')]
        """
        ...

    @abc.abstractmethod
    def __setitem__(  # type: ignore override
        self,
        key: Union[Address, slice],
        value: Union[AnyItems, ImmutableMemory, None],
    ) -> None:
        r"""Sets data.

        Arguments:
            key (slice or int):
                Selection range or address.

            value (items):
                Items to write at the selection address.
                If `value` is null, the range is cleared.

        Examples:
            >>> from bytesparse import Memory

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

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory[7:10] = None
            >>> memory.to_blocks()
            [(5, b'AB'), (10, b'yz')]
            >>> memory[7] = b'C'
            >>> memory[9] = b'x'
            >>> memory.to_blocks() == [(5, b'ABC'), (9, b'xyz')]
            True
            >>> memory[6:12:3] = None
            >>> memory.to_blocks()
            [(5, b'A'), (7, b'C'), (10, b'yz')]
            >>> memory[6:13:3] = b'123'
            >>> memory.to_blocks()
            [(5, b'A1C'), (9, b'2yz3')]

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

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory[0:4] = b'$'
            >>> memory.to_blocks()
            [(0, b'$'), (2, b'ABC'), (6, b'xyz')]
            >>> memory[4:7] = b'45678'
            >>> memory.to_blocks()
            [(0, b'$'), (2, b'AB45678yz')]
            >>> memory[6:8] = b'<>'
            >>> memory.to_blocks()
            [(0, b'$'), (2, b'AB45<>8yz')]
        """
        ...

    @abc.abstractmethod
    def _prebound_endex(
        self,
        start_min: OptionalAddress,
        size: Address,
    ) -> None:
        r"""Bounds final data.

        Low-level method to manage bounds of data starting from an address.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`bound_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

        See Also:
            :meth:`_prebound_endex_backup`
        """
        ...

    @abc.abstractmethod
    def _prebound_endex_backup(
        self,
        start_min: OptionalAddress,
        size: Address,
    ) -> ImmutableMemory:
        r"""Backups a `_prebound_endex()` operation.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`bound_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`ImmutableMemory`: Backup memory region.

        See Also:
            :meth:`_prebound_endex`
        """
        ...

    @abc.abstractmethod
    def _prebound_start(
        self,
        endex_max: OptionalAddress,
        size: Address,
    ) -> None:
        r"""Bounds initial data.

        Low-level method to manage bounds of data starting from an address.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`bound_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

        See Also:
            :meth:`_prebound_start_backup`
        """
        ...

    @abc.abstractmethod
    def _prebound_start_backup(
        self,
        endex_max: OptionalAddress,
        size: Address,
    ) -> ImmutableMemory:
        r"""Backups a `_prebound_start()` operation.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`bound_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`ImmutableMemory`: Backup memory region.

        See Also:
            :meth:`_prebound_start`
        """
        ...

    @abc.abstractmethod
    def align(
        self,
        modulo: int,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
    ) -> None:
        r"""Floods blocks to align their boundaries.

        Arguments:
            modulo (int):
                Alignment modulo.

            start (int):
                Inclusive start address for flooding.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for flooding.
                If ``None``, :attr:`endex` is considered.

            pattern (items):
                Pattern of items to fill the range.

        See Also:
            :meth:`align_backup`
            :meth:`align_restore`
            :meth:`flood`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+---+
            |[0 | A | B | C | 0 | 1 | x | y | z | 1 | 2 | 3]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.align(4, pattern=b'0123')
            >>> memory.to_blocks()
            [(0, b'0ABC01xyz123')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |   |[0 | 1 | 2 | 3]|   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+---+
            |[x | A | B | C]|   |   |[x | 0 | 1 | 2 | 3 | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (7, b'0123')])
            >>> memory.align(2, pattern=b'xyz')
            >>> memory.to_blocks()
            [(0, b'xABC'), (6, b'x0123z')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.align(2, start=3, endex=7, pattern=b'.@')
            >>> memory.to_blocks()
            [(1, b'ABC'), (6, b'xyz')]
        """
        ...

    @abc.abstractmethod
    def align_backup(
        self,
        modulo: int,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[OpenInterval]:
        r"""Backups an `align()` operation.

        Arguments:
            modulo (int):
                Alignment modulo.

            start (int):
                Inclusive start address for filling.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for filling.
                If ``None``, :attr:`endex` is considered.

        Returns:
            list of open intervals: Backup memory gaps.

        See Also:
            :meth:`align`
            :meth:`align_restore`
        """
        ...

    @abc.abstractmethod
    def align_restore(
        self,
        gaps: list[OpenInterval],
    ) -> None:
        r"""Restores an `align()` operation.

        Arguments:
            gaps (list of open intervals):
                Backup memory gaps to restore.

        See Also:
            :meth:`align`
            :meth:`align_backup`
        """
        ...

    @abc.abstractmethod
    def append(  # type: ignore override
        self,
        item: AnyItems,
    ) -> None:
        r"""Appends a single item.

        Arguments:
            item (int):
                Value to append. Can be a single byte string or integer.

        See Also:
            :meth:`append_backup`
            :meth:`append_restore`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory()
            >>> memory.append(b'$')
            >>> memory.to_blocks()
            [(0, b'$')]

            ~~~

            >>> memory = Memory()
            >>> memory.append(3)
            >>> memory.to_blocks()
            [(0, b'\x03')]
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def append_restore(
        self,
    ) -> None:
        r"""Restores an `append()` operation.

        See Also:
            :meth:`append`
            :meth:`append_backup`
        """
        ...

    @ImmutableMemory.bound_endex.setter
    @abc.abstractmethod
    def bound_endex(
        self,
        bound_endex: OptionalAddress,
    ) -> None:
        ...

    @ImmutableMemory.bound_span.setter
    @abc.abstractmethod
    def bound_span(
        self,
        bound_span: Union[OpenInterval, None],  # `None` translates to `(None, None)`
    ) -> None:
        ...

    @ImmutableMemory.bound_start.setter
    @abc.abstractmethod
    def bound_start(
        self,
        bound_start: OptionalAddress,
    ) -> None:
        ...

    @abc.abstractmethod
    def clear(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:
        r"""Clears an address range.

        Arguments:
            start (int):
                Inclusive start address for clearing.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for clearing.
                If ``None``, :attr:`endex` is considered.

        See Also:
            :meth:`clear_backup`
            :meth:`clear_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory.clear(6, 10)
            >>> memory.to_blocks()
            [(5, b'A'), (10, b'yz')]
        """
        ...

    @abc.abstractmethod
    def clear_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            :obj:`ImmutableMemory`: Backup memory region.

        See Also:
            :meth:`clear`
            :meth:`clear_restore`
        """
        ...

    @abc.abstractmethod
    def clear_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `clear()` operation.

        Arguments:
            backup (:obj:`ImmutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`clear`
            :meth:`clear_backup`
        """
        ...

    @abc.abstractmethod
    def crop(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:
        r"""Keeps data within an address range.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

        See Also:
            :meth:`crop_backup`
            :meth:`crop_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |[B | C]|   |[x]|   |   |   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory.crop(6, 10)
            >>> memory.to_blocks()
            [(6, b'BC'), (9, b'x')]
        """
        ...

    @abc.abstractmethod
    def crop_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> tuple[Union[ImmutableMemory, None], Union[ImmutableMemory, None]]:
        r"""Backups a `crop()` operation.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`ImmutableMemory` pair: Backup memory regions.

        See Also:
            :meth:`crop`
            :meth:`crop_restore`
        """
        ...

    @abc.abstractmethod
    def crop_restore(
        self,
        backup_start: Union[ImmutableMemory, None],
        backup_endex: Union[ImmutableMemory, None],
    ) -> None:
        r"""Restores a `crop()` operation.

        Arguments:
            backup_start (:obj:`ImmutableMemory`):
                Backup memory region to restore at the beginning.

            backup_endex (:obj:`ImmutableMemory`):
                Backup memory region to restore at the end.

        See Also:
            :meth:`crop`
            :meth:`crop_backup`
        """
        ...

    @abc.abstractmethod
    def cut(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        bound: bool = True,
    ) -> ImmutableMemory:
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
                as its bounds range. This retains information about any
                initial and final emptiness of that range, which would be lost
                otherwise.

        Returns:
            :obj:`Memory`: A copy of the memory from the selected range.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+
            |   |   |[B | C]|   |[x]|   |   |   |
            +---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> taken = memory.cut(6, 10)
            >>> taken.to_blocks()
            [(6, b'BC'), (9, b'x')]
            >>> memory.to_blocks()
            [(5, b'A'), (10, b'yz')]
        """
        ...

    @abc.abstractmethod
    def delete(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:
        r"""Deletes an address range.

        Arguments:
            start (int):
                Inclusive start address for deletion.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for deletion.
                If ``None``, :attr:`endex` is considered.

        See Also:
            :meth:`delete_backup`
            :meth:`delete_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+
            | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12| 13|
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | y | z]|   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory.delete(6, 10)
            >>> memory.to_blocks()
            [(5, b'Ayz')]
        """
        ...

    @abc.abstractmethod
    def delete_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            :obj:`ImmutableMemory`: Backup memory region.

        See Also:
            :meth:`delete`
            :meth:`delete_restore`
        """
        ...

    @abc.abstractmethod
    def delete_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `delete()` operation.

        Arguments:
            backup (:obj:`ImmutableMemory`):
                Backup memory region

        See Also:
            :meth:`delete`
            :meth:`delete_backup`
        """
        ...

    @abc.abstractmethod
    def extend(  # type: ignore override
        self,
        items: Union[AnyBytes, ImmutableMemory],
        offset: Address = 0,
    ) -> None:
        r"""Concatenates items.

        Appends `items` after :attr:`content_endex`.
        Equivalent to ``self += items``.

        Arguments:
            items (items):
                Items to append at the end of the current virtual space.

            offset (int):
                Optional offset w.r.t. :attr:`content_endex`.

        See Also:
            :meth:`__iadd__`
            :meth:`extend_backup`
            :meth:`extend_restore`

        Examples:
            >>> from bytesparse import Memory

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.extend(b'123')
            >>> memory.to_blocks()
            [(1, b'ABC'), (5, b'xyz123')]

            ~~~

            >>> memory = Memory.from_blocks([(1, b'ABC'), (5, b'xyz')])
            >>> memory.extend(range(49, 52), offset=4)
            >>> memory.to_blocks()
            [(1, b'ABC'), (5, b'xyz'), (12, b'123')]

            ~~~

            >>> memory1 = Memory.from_blocks([(1, b'ABC')])
            >>> memory2 = Memory.from_blocks([(5, b'xyz')])
            >>> memory1.extend(memory2)
            >>> memory1.to_blocks()
            [(1, b'ABC'), (9, b'xyz')]
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def fill(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
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

        See Also:
            :meth:`fill_backup`
            :meth:`fill_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[1 | 2 | 3 | 1 | 2 | 3 | 1 | 2]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.fill(pattern=b'123')
            >>> memory.to_blocks()
            [(1, b'12312312')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | 1 | 2 | 3 | 1 | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.fill(3, 7, b'123')
            >>> memory.to_blocks()
            [(1, b'AB1231yz')]
        """
        ...

    @abc.abstractmethod
    def fill_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
            :obj:`ImmutableMemory`: Backup memory region.

        See Also:
            :meth:`fill`
            :meth:`fill_restore`
        """
        ...

    @abc.abstractmethod
    def fill_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `fill()` operation.

        Arguments:
            backup (:obj:`ImmutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`fill`
            :meth:`fill_backup`
        """
        ...

    @abc.abstractmethod
    def flood(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
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

        See Also:
            :meth:`flood_backup`
            :meth:`flood_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 1 | 2 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.flood(pattern=b'123')
            >>> memory.to_blocks()
            [(1, b'ABC12xyz')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | 2 | 3 | x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.flood(start=3, endex=7, pattern=b'123')
            >>> memory.to_blocks()
            [(1, b'ABC23xyz')]
        """
        ...

    @abc.abstractmethod
    def flood_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[OpenInterval]:
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
        ...

    @abc.abstractmethod
    def flood_restore(
        self,
        gaps: list[OpenInterval],
    ) -> None:
        r"""Restores a `flood()` operation.

        Arguments:
            gaps (list of open intervals):
                Backup memory gaps to restore.

        See Also:
            :meth:`flood`
            :meth:`flood_backup`
        """
        ...

    @abc.abstractmethod
    def insert(  # type: ignore override
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> None:
        r"""Inserts data.

        Inserts data, moving existing items after the insertion address by the
        size of the inserted data.

        Arguments::
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

        See Also:
            :meth:`insert_backup`
            :meth:`insert_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |   |[x | y | z]|   |[$]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |   |[x | y | 1 | z]|   |[$]|
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.insert(10, b'$')
            >>> memory.to_blocks()
            [(1, b'ABC'), (6, b'xyz'), (10, b'$')]
            >>> memory.insert(8, b'1')
            >>> memory.to_blocks()
            [(1, b'ABC'), (6, b'xy1z'), (11, b'$')]
        """
        ...

    @abc.abstractmethod
    def insert_backup(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> tuple[Address, ImmutableMemory]:
        r"""Backups an `insert()` operation.

        Arguments:
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

        Returns:
            (int, :obj:`ImmutableMemory`): Insertion address, backup memory region.

        See Also:
            :meth:`insert`
            :meth:`insert_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def poke(
        self,
        address: Address,
        item: Union[AnyBytes, Value, None],
    ) -> None:
        r"""Sets the item at an address.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to set, ``None`` to clear the cell.

        See Also:
            :meth:`poke_backup`
            :meth:`poke_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.poke(3, b'@')
            >>> memory.peek(3)  # -> ord('@') = 64
            64
            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.poke(5, b'@')
            >>> memory.peek(5)  # -> ord('@') = 64
            64
        """
        ...

    @abc.abstractmethod
    def poke_backup(
        self,
        address: Address,
    ) -> tuple[Address, OptionalValue]:
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
        ...

    @abc.abstractmethod
    def poke_restore(
        self,
        address: Address,
        item: OptionalValue,
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
        ...

    @abc.abstractmethod
    def pop(  # type: ignore override
        self,
        address: OptionalAddress = None,
        default: OptionalValue = None,
    ) -> OptionalValue:
        r"""Takes a value away.

        Arguments:
            address (int):
                Address of the byte to pop.
                If ``None``, the very last byte is popped.

            default (int):
                Value to return if `address` is within emptiness.

        Return:
            int: Value at `address`; `default` within emptiness.

        See Also:
            :meth:`pop_backup`
            :meth:`pop_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C | D]|   |[$]|   |[x | y]|   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | D]|   |[$]|   |[x | y]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.pop()  # -> ord('z') = 122
            122
            >>> memory.pop(3)  # -> ord('C') = 67
            67
            >>> memory.pop(6, 63)  # -> ord('?') = 67
            63
        """
        ...

    @abc.abstractmethod
    def pop_backup(
        self,
        address: OptionalAddress = None,
    ) -> tuple[Address, OptionalValue]:
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
        ...

    @abc.abstractmethod
    def pop_restore(
        self,
        address: Address,
        item: OptionalValue,
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
        ...

    @abc.abstractmethod
    def popitem(
        self,
    ) -> tuple[Address, Value]:
        r"""Pops the last item.

        Return:
            (int, int): Address and value of the last item.

        See Also:
            :meth:`popitem_backup`
            :meth:`popitem_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A]|   |   |   |   |   |   |   |[y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'A'), (9, b'yz')])
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
        """
        ...

    @abc.abstractmethod
    def popitem_backup(
        self,
    ) -> tuple[Address, Value]:
        r"""Backups a `popitem()` operation.

        Returns:
            (int, int): Address and value of the last item.

        See Also:
            :meth:`popitem`
            :meth:`popitem_restore`
        """
        ...

    @abc.abstractmethod
    def popitem_restore(
        self,
        address: Address,
        item: Value,
    ) -> None:
        r"""Restores a `popitem()` operation.

        Arguments:
            address (int):
                Address of the target item.

            item (int or byte):
                Item to restore.

        See Also:
            :meth:`popitem`
            :meth:`popitem_backup`
        """
        ...

    @abc.abstractmethod
    def remove(  # type: ignore override
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        See Also:
            :meth:`remove_backup`
            :meth:`remove_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | D]|   |[$]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | D]|   |   |[x | y | z]|   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.remove(b'BC')
            >>> memory.to_blocks()
            [(1, b'AD'), (4, b'$'), (6, b'xyz')]
            >>> memory.remove(ord('$'))
            >>> memory.to_blocks()
            [(1, b'AD'), (5, b'xyz')]
            >>> memory.remove(b'?')
            Traceback (most recent call last):
                ...
            ValueError: subsection not found
        """
        ...

    @abc.abstractmethod
    def remove_backup(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        See Also:
            :meth:`remove`
            :meth:`remove_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`reserve_backup`
            :meth:`reserve_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A]|   |   | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(3, b'ABC'), (7, b'xyz')])
            >>> memory.reserve(4, 2)
            >>> memory.to_blocks()
            [(3, b'A'), (6, b'BC'), (9, b'xyz')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   |[A | B]|)))|
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')], endex=12)
            >>> memory.reserve(5, 5)
            >>> memory.to_blocks()
            [(10, b'AB')]
        """
        ...

    @abc.abstractmethod
    def reserve_backup(
        self,
        address: Address,
        size: Address,
    ) -> tuple[Address, ImmutableMemory]:
        r"""Backups a `reserve()` operation.

        Arguments:
            address (int):
                Start address of the emptiness to insert.

            size (int):
                Size of the emptiness to insert.

        Returns:
            (int, :obj:`ImmutableMemory`): Reservation address, backup memory region.

        See Also:
            :meth:`reserve`
            :meth:`reserve_restore`
        """
        ...

    @abc.abstractmethod
    def reserve_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores a `reserve()` operation.

        Arguments:
            address (int):
                Address of the reservation point.

            backup (:obj:`ImmutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`reserve`
            :meth:`reserve_backup`
        """
        ...

    @abc.abstractmethod
    def reverse(
        self,
    ) -> None:
        r"""Reverses the memory in-place.

        Data is reversed within the memory :attr:`span`.

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+
            |   |[z | y | x]|   |[$]|   |[D | C | B | A]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
            >>> memory.reverse()
            >>> memory.to_blocks()
            [(1, b'zyx'), (5, b'$'), (7, b'DCBA')]

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
            [(5, b'CBA')]
        """

    @abc.abstractmethod
    def setdefault(
        self,
        address: Address,
        default: Union[AnyBytes, Value, None] = None,
    ) -> OptionalValue:
        r"""Defaults a value.

        Arguments:
            address (int):
                Address of the byte to set.

            default (int):
                Value to set if `address` is within emptiness.

        Return:
            int: Value at `address`; `default` within emptiness.

        See Also:
            :meth:`setdefault_backup`
            :meth:`setdefault_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11|
            +===+===+===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C | D]|   |[$]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABCD'), (6, b'$'), (8, b'xyz')])
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
        """
        ...

    @abc.abstractmethod
    def setdefault_backup(
        self,
        address: Address,
    ) -> tuple[Address, OptionalValue]:
        r"""Backups a `setdefault()` operation.

        Arguments:
            address (int):
                Address of the byte to set.

        Returns:
            (int, int): `address`, item at `address` (``None`` if empty).

        See Also:
            :meth:`setdefault`
            :meth:`setdefault_restore`
        """
        ...

    @abc.abstractmethod
    def setdefault_restore(
        self,
        address: Address,
        item: OptionalValue,
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
        ...

    @abc.abstractmethod
    def shift(
        self,
        offset: Address,
    ) -> None:
        r"""Shifts the items.

        Arguments:
            offset (int):
                Signed amount of address shifting.

        See Also:
            :meth:`shift_backup`
            :meth:`shift_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |   |   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[x | y | z]|   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')])
            >>> memory.shift(-2)
            >>> memory.to_blocks()
            [(3, b'ABC'), (7, b'xyz')]

            ~~~

            +---+---+---+---+---+---+---+---+---+---+---+
            | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10| 11| 12|
            +===+===+===+===+===+===+===+===+===+===+===+
            |   |[[[|   |[A | B | C]|   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+---+
            |   |[y | z]|   |   |   |   |   |   |   |   |
            +---+---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(5, b'ABC'), (9, b'xyz')], start=3)
            >>> memory.shift(-8)
            >>> memory.to_blocks()
            [(2, b'yz')]
        """
        ...

    @abc.abstractmethod
    def shift_backup(
        self,
        offset: Address,
    ) -> tuple[Address, ImmutableMemory]:
        r"""Backups a `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

        Returns:
            (int, :obj:`ImmutableMemory`): Shifting, backup memory region.

        See Also:
            :meth:`shift`
            :meth:`shift_restore`
        """
        ...

    @abc.abstractmethod
    def shift_restore(
        self,
        offset: Address,
        backup: ImmutableMemory,
    ) -> None:
        r"""Restores an `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

            backup (:obj:`ImmutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`shift`
            :meth:`shift_backup`
        """
        ...

    @abc.abstractmethod
    def update(  # type: ignore override
        self,
        data: object,
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> None:
        r"""Updates data.

        Arguments:
            data (iterable):
                Data to update with.
                Can be either another memory, an (address, value)
                mapping, or an iterable of (address, value) pairs.

            clear (bool):
                Clears the target range before writing data.
                Useful only if `data` is a :obj:`Memory` with empty spaces.

        See Also:
            :meth:`update_backup`
            :meth:`update_restore`

        Examples:
            >>> from bytesparse import Memory

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
            [(5, b'ABC')]
            >>> memory.update({1: b'x', 2: ord('y')})
            >>> memory.to_blocks()
            [(1, b'xy'), (5, b'ABC')]
            >>> memory.update([(6, b'?'), (3, ord('@'))])
            >>> memory.to_blocks()
            [(1, b'xy@'), (5, b'A?C')]
        """
        ...

    @abc.abstractmethod
    def update_backup(
        self,
        data: object,
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> Union[AddressValueMapping, list[ImmutableMemory]]:
        r"""Backups an `update()` operation.

        Arguments:
            data (iterable):
                Data to update with.
                Can be either another memory, an (address, value)
                mapping, or an iterable of (address, value) pairs.

            clear (bool):
                Clears the target range before writing data.
                Useful only if `data` is a :obj:`Memory` with empty spaces.

        Returns:
            list of :obj:`ImmutableMemory`: Backup memory regions.

        See Also:
            :meth:`update`
            :meth:`update_restore`
        """
        ...

    @abc.abstractmethod
    def update_restore(
        self,
        backups: Union[AddressValueMapping, list[ImmutableMemory]],
    ) -> None:
        r"""Restores an `update()` operation.

        Arguments:
            backups (list of :obj:`ImmutableMemory`):
                Backup memory regions to restore.

        See Also:
            :meth:`update`
            :meth:`update_backup`
        """
        ...

    @abc.abstractmethod
    def write(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
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
                Useful only if `data` is a :obj:`ImmutableMemory` with empty spaces.

        See Also:
            :meth:`write_backup`
            :meth:`write_restore`

        Examples:
            >>> from bytesparse import Memory

            +---+---+---+---+---+---+---+---+---+---+
            | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
            +===+===+===+===+===+===+===+===+===+===+
            |   |[A | B | C]|   |   |[x | y | z]|   |
            +---+---+---+---+---+---+---+---+---+---+
            |   |[A | B | C]|   |[1 | 2 | 3 | z]|   |
            +---+---+---+---+---+---+---+---+---+---+

            >>> memory = Memory.from_blocks([(1, b'ABC'), (6, b'xyz')])
            >>> memory.write(5, b'123')
            >>> memory.to_blocks()
            [(1, b'ABC'), (5, b'123z')]
        """
        ...

    @abc.abstractmethod
    def write_backup(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
        clear: bool = False,
    ) -> list[ImmutableMemory]:
        r"""Backups a `write()` operation.

        Arguments:
            address (int):
                Address where to start writing data.

            data (bytes):
                Data to write.

            clear (bool):
                Clears the target range before writing data.
                Useful only if `data` is a :obj:`Memory` with empty spaces.

        Returns:
            list of :obj:`ImmutableMemory`: Backup memory regions.

        See Also:
            :meth:`write`
            :meth:`write_restore`
        """
        ...

    @abc.abstractmethod
    def write_restore(
        self,
        backups: Sequence[ImmutableMemory],
    ) -> None:
        r"""Restores a `write()` operation.

        Arguments:
            backups (list of :obj:`ImmutableMemory`):
                Backup memory regions to restore.

        See Also:
            :meth:`write`
            :meth:`write_backup`
        """
        ...


class MutableBytesparse(MutableMemory, abc.ABC):
    r"""Wrapper for more `bytearray` compatibility.

    This wrapper class can make :class:`Memory` closer to the actual
    :class:`bytearray` API.

    For instantiation, please refer to :meth:`MutableBytesparse.__init__`.

    With respect to :class:`Memory`, negative addresses are not allowed.
    Instead, negative addresses are to consider as referred to :attr:`endex`.

    See Also:
        :obj:`ImmutableMemory`
        :obj:`MutableMemory`

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
            Anything before will be deleted.
            If `source` is provided, its data start at this address
            (0 if `start` is ``None``).

        endex (int):
            Optional memory exclusive end address.
            Anything at or after it will be deleted.

    Examples:
        >>> from bytesparse import bytesparse

        >>> memory = bytesparse()
        >>> memory.to_blocks()
        []

        >>> memory = bytesparse(start=3, endex=10)
        >>> memory.bound_span
        (3, 10)
        >>> memory.write(0, b'Hello, World!')
        >>> memory.to_blocks()
        [(3, b'lo, Wor')]

        >>> memory = bytesparse.from_bytes(b'Hello, World!', offset=5)
        >>> memory.to_blocks()
        [(5, b'Hello, World!')]

        >>> memory = bytesparse(b'Hello, World!')
        >>> memory.to_blocks()
        [(0, b'Hello, World!')]

        >>> memory = bytesparse(3)
        >>> memory.to_blocks()
        [(0, b'\x00\x00\x00')]

        >>> memory = bytesparse([65, 66, 67])
        >>> memory.to_blocks()
        [(0, b'ABC')]

        >>> memory = bytesparse('ASCII string', 'ascii')
        >>> memory.to_blocks()
        [(0, b'ASCII string')]

        >>> memory = bytesparse('Non-ASCII: \u2204', 'ascii', 'backslashreplace')
        >>> memory.to_blocks()
        [(0, b'Non-ASCII: \\u2204')]

        >>> memory = bytesparse('Non-ASCII: \u2204', 'ascii', 'xmlcharrefreplace')
        >>> memory.to_blocks()
        [(0, b'Non-ASCII: &#8708;')]

        >>> memory = bytesparse('Non-ASCII: \u2204', 'ascii', 'replace')
        >>> memory.to_blocks()
        [(0, b'Non-ASCII: ?')]

        >>> memory = bytesparse('Non-ASCII: \u2204', 'ascii', 'ignore')
        >>> memory.to_blocks()
        [(0, b'Non-ASCII: ')]

        >>> memory = bytesparse('Non-ASCII: \u2204', 'ascii', 'strict')
        Traceback (most recent call last):
            ...
        UnicodeEncodeError: 'ascii' codec can't encode character '\u2204' in position 11: ordinal not in range(128)

        >>> memory = bytesparse('Missing encoding')
        Traceback (most recent call last):
            ...
        TypeError: string argument without an encoding

    Method Groups:

        Creation:
            :meth:`__init__`

        Addressing:
            :meth:`_rectify_address`
            :meth:`_rectify_span`
    """

    @abc.abstractmethod
    def __init__(
        self,
        *args: Any,  # see bytearray.__init__()
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ):
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def _rectify_span(
        self,
        start: OptionalAddress,
        endex: OptionalAddress,
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
            pair of int: Rectified address span.
        """
        ...
