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

r"""Common stuff, shared across modules."""

import abc
import collections.abc
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

Block = List[Union[Address, AnyBytes]]  # typed as Tuple[Address, Data]
BlockIndex = int
BlockIterable = Iterable[Block]
BlockSequence = Sequence[Block]
BlockList = List[Block]

OpenInterval = Tuple[Optional[Address], Optional[Address]]
ClosedInterval = Tuple[Address, Address]

EllipsisType = Type['Ellipsis']

STR_MAX_CONTENT_SIZE: Address = 1000
r"""Maximum memory content size for string representation."""


class ImmutableMemory(collections.abc.Sequence,
                      collections.abc.Mapping):

    @abc.abstractmethod
    def __add__(
        self,
        value: Union[AnyBytes, 'ImmutableMemory'],
    ) -> 'ImmutableMemory':
        ...

    @abc.abstractmethod
    def __bool__(
        self,
    ) -> bool:
        r"""Has any items.

        Returns:
            bool: Has any items.
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
    def __iter__(
        self,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values.

        Iterates over values between :attr:`start` and :attr:`endex`.

        Yields:
            int: Value as byte integer, or ``None``.
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def __mul__(
        self,
        times: int,
    ) -> 'ImmutableMemory':
        ...

    @abc.abstractmethod
    def __repr__(
        self,
    ) -> str:
        ...

    @abc.abstractmethod
    def __reversed__(
        self,
    ) -> Iterator[Optional[Value]]:
        r"""Iterates over values, reversed order.

        Iterates over values between :attr:`start` and :attr:`endex`, in
        reversed order.

        Yields:
            int: Value as byte integer, or ``None``.
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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

        If the memory has no data and no trimming, :attr:`start` is returned.

        Trimming is considered only for an empty memory.
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

        If the memory has no data and no trimming, :attr:`start` minus one is
        returned.

        Trimming is considered only for an empty memory.
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

        If the memory has no data and no trimming, 0 is returned.

        Trimming is considered only for an empty memory.
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

        If trimming is defined, there must be no empty space also towards it.
        """
        ...

    @abc.abstractmethod
    def copy(
        self,
    ) -> 'ImmutableMemory':
        r"""Creates a shallow copy.

        Returns:
            :obj:`ImmutableMemory`: Shallow copy.
        """
        ...

    @abc.abstractmethod
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

        If  :attr:`trim_endex` not ``None``, that is returned.

        If the memory has no data and no trimming, :attr:`start` is returned.
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

        If  :attr:`trim_endex` not ``None``, that minus one is returned.

        If the memory has no data and no trimming, :attr:`start` is returned.
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
    def extract(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
        step: Optional[Address] = None,
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
                as its trimming range. This retains information about any
                initial and final emptiness of that range, which would be lost
                otherwise.

        Returns:
            :obj:`ImmutableMemory`: A copy of the memory from the selected range.
        """
        ...

    @abc.abstractmethod
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
        ...

    @classmethod
    @abc.abstractmethod
    def from_blocks(
        cls,
        blocks: BlockList,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
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
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_bytes(
        cls,
        data: AnyBytes,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
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
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`ImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.
        """
        ...

    @classmethod
    @abc.abstractmethod
    def from_memory(
        cls,
        memory: 'ImmutableMemory',
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
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
                Anything before will be trimmed away.

            endex (int):
                Optional memory exclusive end address.
                Anything at or after it will be trimmed away.

            copy (bool):
                Forces copy of provided input data into the underlying data
                structure.

            validate (bool):
                Validates the resulting :obj:`MemorImmutableMemory` object.

        Returns:
            :obj:`ImmutableMemory`: The resulting memory object.

        Raises:
            :obj:`ValueError`: Some requirements are not satisfied.
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
    def get(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, `default` if empty.
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

        Returns:
            str: Hexadecimal string representation.

        Raises:
            :obj:`ValueError`: Data not contiguous (see :attr:`contiguous`).
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def peek(
        self,
        address: Address,
    ) -> Optional[Value]:
        r"""Gets the item at an address.

        Returns:
            int: The item at `address`, ``None`` if empty.
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def rindex(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        """
        ...

    @property
    @abc.abstractmethod
    def span(
        self,
    ) -> ClosedInterval:
        r"""tuple of int: Memory address span.

        A :obj:`tuple` holding both :attr:`start` and :attr:`endex`.
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

        If :attr:`trim_start` not ``None``, that is returned.

        If the memory has no data and no trimming, 0 is returned.
        """
        ...

    @property
    @abc.abstractmethod
    def trim_endex(
        self,
    ) -> Optional[Address]:
        r"""int: Trimming exclusive end address.

        Any data at or after this address is automatically discarded.
        Disabled if ``None``.
        """
        ...

    @property
    @abc.abstractmethod
    def trim_span(
        self,
    ) -> OpenInterval:
        r"""tuple of int: Trimming span addresses.

        A :obj:`tuple` holding :attr:`trim_start` and :attr:`trim_endex`.
        """
        ...

    @property
    @abc.abstractmethod
    def trim_start(
        self,
    ) -> Optional[Address]:
        r"""int: Trimming start address.

        Any data before this address is automatically discarded.
        Disabled if ``None``.
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
        """
        ...

    @abc.abstractmethod
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
        """
        ...


class MutableMemory(ImmutableMemory,
                    collections.abc.MutableSequence,
                    collections.abc.MutableMapping):

    @abc.abstractmethod
    def __delitem__(
        self,
        key: Union[Address, slice],
    ) -> None:
        r"""Deletes data.

        Arguments:
            key (slice or int):
                Deletion range or address.
        """
        ...

    @abc.abstractmethod
    def __iadd__(
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'MutableMemory':
        ...

    @abc.abstractmethod
    def __imul__(
        self,
        times: int,
    ) -> 'MutableMemory':
        ...

    @abc.abstractmethod
    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Optional[Union[AnyBytes, Value, ImmutableMemory]],
    ) -> None:
        r"""Sets data.

        Arguments:
            key (slice or int):
                Selection range or address.

            value (items):
                Items to write at the selection address.
                If `value` is null, the range is cleared.
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def _pretrim_endex_backup(
        self,
        start_min: Optional[Address],
        size: Address,
    ) -> 'MutableMemory':
        r"""Backups a `_pretrim_endex()` operation.

        Arguments:
            start_min (int):
                Starting address of the erasure range.
                If ``None``, :attr:`trim_endex` minus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`MutableMemory`: Backup memory region.

        See Also:
            :meth:`_pretrim_endex`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def _pretrim_start_backup(
        self,
        endex_max: Optional[Address],
        size: Address,
    ) -> 'MutableMemory':
        r"""Backups a `_pretrim_start()` operation.

        Arguments:
            endex_max (int):
                Exclusive end address of the erasure range.
                If ``None``, :attr:`trim_start` plus `size` is considered.

            size (int):
                Size of the erasure range.

        Returns:
            :obj:`MutableMemory`: Backup memory region.

        See Also:
            :meth:`_pretrim_start`
        """
        ...

    @abc.abstractmethod
    def append(
        self,
        item: Union[AnyBytes, Value],
    ) -> None:
        r"""Appends a single item.

        Arguments:
            item (int):
                Value to append. Can be a single byte string or integer.

        See Also:
            :meth:`append_backup`
            :meth:`append_restore`
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

    @abc.abstractmethod
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

        See Also:
            :meth:`clear_backup`
            :meth:`clear_restore`
        """
        ...

    @abc.abstractmethod
    def clear_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> 'MutableMemory':
        r"""Backups a `clear()` operation.

        Arguments:
            start (int):
                Inclusive start address for clearing.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for clearing.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`MutableMemory`: Backup memory region.

        See Also:
            :meth:`clear`
            :meth:`clear_restore`
        """
        ...

    @abc.abstractmethod
    def clear_restore(
        self,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores a `clear()` operation.

        Arguments:
            backup (:obj:`MutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`clear`
            :meth:`clear_backup`
        """
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`crop_backup`
            :meth:`crop_restore`
        """
        ...

    @abc.abstractmethod
    def crop_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Tuple[Optional['MutableMemory'], Optional['MutableMemory']]:
        r"""Backups a `crop()` operation.

        Arguments:
            start (int):
                Inclusive start address for cropping.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for cropping.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`MutableMemory` couple: Backup memory regions.

        See Also:
            :meth:`crop`
            :meth:`crop_restore`
        """
        ...

    @abc.abstractmethod
    def crop_restore(
        self,
        backup_start: Optional['MutableMemory'],
        backup_endex: Optional['MutableMemory'],
    ) -> None:
        r"""Restores a `crop()` operation.

        Arguments:
            backup_start (:obj:`MutableMemory`):
                Backup memory region to restore at the beginning.

            backup_endex (:obj:`MutableMemory`):
                Backup memory region to restore at the end.

        See Also:
            :meth:`crop`
            :meth:`crop_backup`
        """
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`delete_backup`
            :meth:`delete_restore`
        """
        ...

    @abc.abstractmethod
    def delete_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> 'MutableMemory':
        r"""Backups a `delete()` operation.

        Arguments:
            start (int):
                Inclusive start address for deletion.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for deletion.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`MutableMemory`: Backup memory region.

        See Also:
            :meth:`delete`
            :meth:`delete_restore`
        """
        ...

    @abc.abstractmethod
    def delete_restore(
        self,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores a `delete()` operation.

        Arguments:
            backup (:obj:`MutableMemory`):
                Backup memory region

        See Also:
            :meth:`delete`
            :meth:`delete_backup`
        """
        ...

    @abc.abstractmethod
    def extend(
        self,
        items: Union[AnyBytes, 'ImmutableMemory'],
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

        See Also:
            :meth:`fill_backup`
            :meth:`fill_restore`
        """
        ...

    @abc.abstractmethod
    def fill_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> 'MutableMemory':
        r"""Backups a `fill()` operation.

        Arguments:
            start (int):
                Inclusive start address for filling.
                If ``None``, :attr:`start` is considered.

            endex (int):
                Exclusive end address for filling.
                If ``None``, :attr:`endex` is considered.

        Returns:
            :obj:`MutableMemory`: Backup memory region.

        See Also:
            :meth:`fill`
            :meth:`fill_restore`
        """
        ...

    @abc.abstractmethod
    def fill_restore(
        self,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores a `fill()` operation.

        Arguments:
            backup (:obj:`MutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`fill`
            :meth:`fill_backup`
        """
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`flood_backup`
            :meth:`flood_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`insert_backup`
            :meth:`insert_restore`
        """
        ...

    @abc.abstractmethod
    def insert_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> Tuple[Address, 'MutableMemory']:
        r"""Backups an `insert()` operation.

        Arguments:
            address (int):
                Address of the insertion point.

            data (bytes):
                Data to insert.

        Returns:
            (int, :obj:`MutableMemory`): Insertion address, backup memory region.

        See Also:
            :meth:`insert`
            :meth:`insert_restore`
        """
        ...

    @abc.abstractmethod
    def insert_restore(
        self,
        address: Address,
        backup: 'MutableMemory',
    ) -> None:
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`poke_backup`
            :meth:`poke_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`pop_backup`
            :meth:`pop_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
    def popitem(
        self,
    ) -> Tuple[Address, Value]:
        r"""Pops the last item.

        Return:
            (int, int): Address and value of the last item.

        See Also:
            :meth:`popitem_backup`
            :meth:`popitem_restore`
        """
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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
        ...

    @abc.abstractmethod
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

        See Also:
            :meth:`remove_backup`
            :meth:`remove_restore`
        """
        ...

    @abc.abstractmethod
    def remove_backup(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> 'MutableMemory':
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
        backup: 'MutableMemory',
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
        """
        ...

    @abc.abstractmethod
    def reserve_backup(
        self,
        address: Address,
        size: Address,
    ) -> Tuple[Address, 'MutableMemory']:
        r"""Backups a `reserve()` operation.

        Arguments:
            address (int):
                Start address of the emptiness to insert.

            size (int):
                Size of the emptiness to insert.

        Returns:
            (int, :obj:`MutableMemory`): Reservation address, backup memory region.

        See Also:
            :meth:`reserve`
            :meth:`reserve_restore`
        """
        ...

    @abc.abstractmethod
    def reserve_restore(
        self,
        address: Address,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores a `reserve()` operation.

        Arguments:
            address (int):
                Address of the reservation point.

            backup (:obj:`MutableMemory`):
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
        """

    @abc.abstractmethod
    def setdefault(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:
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
        """
        ...

    @abc.abstractmethod
    def setdefault_backup(
        self,
        address: Address,
    ) -> Tuple[Address, Optional[Value]]:
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
        """
        ...

    @abc.abstractmethod
    def shift_backup(
        self,
        offset: Address,
    ) -> Tuple[Address, 'MutableMemory']:
        r"""Backups a `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

        Returns:
            (int, :obj:`MutableMemory`): Shifting, backup memory region.

        See Also:
            :meth:`shift`
            :meth:`shift_restore`
        """
        ...

    @abc.abstractmethod
    def shift_restore(
        self,
        offset: Address,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores an `shift()` operation.

        Arguments:
            offset (int):
                Signed amount of address shifting.

            backup (:obj:`MutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`shift`
            :meth:`shift_backup`
        """
        ...

    @ImmutableMemory.trim_endex.setter
    @abc.abstractmethod
    def trim_endex(
        self,
        trim_endex: Address,
    ) -> None:
        ...

    @ImmutableMemory.trim_span.setter
    @abc.abstractmethod
    def trim_span(
        self,
        trim_span: OpenInterval,
    ) -> None:
        ...

    @ImmutableMemory.trim_start.setter
    @abc.abstractmethod
    def trim_start(
        self,
        trim_start: Address,
    ) -> None:
        ...

    @abc.abstractmethod
    def write(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
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
                Useful only if `data` is a :obj:`MutableMemory` with empty spaces.

        See Also:
            :meth:`write_backup`
            :meth:`write_restore`
        """
        ...

    @abc.abstractmethod
    def write_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> 'MutableMemory':
        r"""Backups a `write()` operation.

        Arguments:
            address (int):
                Address where to start writing data.

            data (bytes):
                Data to write.

        Returns:
            :obj:`MutableMemory` list: Backup memory regions.

        See Also:
            :meth:`write`
            :meth:`write_restore`
        """
        ...

    @abc.abstractmethod
    def write_restore(
        self,
        backup: 'MutableMemory',
    ) -> None:
        r"""Restores a `write()` operation.

        Arguments:
            backup (:obj:`MutableMemory`):
                Backup memory region to restore.

        See Also:
            :meth:`write`
            :meth:`write_backup`
        """
        ...
