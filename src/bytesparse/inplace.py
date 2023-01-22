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
from typing import Sequence
from typing import Tuple
from typing import Union

from .base import STR_MAX_CONTENT_SIZE
from .base import Address
from .base import AddressValueMapping
from .base import AnyBytes
from .base import Block
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

        return bool(self._blocks)

    def __bytes__(
        self,
    ) -> bytes:

        return bytes(self.view())

    def __contains__(
        self,
        item: Union[AnyBytes, Value],
    ) -> bool:

        return any(item in block_data for _, block_data in self._blocks)

    def __copy__(
        self,
    ) -> 'Memory':

        return self.from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=False)

    def __deepcopy__(
        self,
    ) -> 'Memory':

        return self.from_memory(self, start=self._trim_start, endex=self._trim_endex, copy=True)

    def __delitem__(
        self,
        key: Union[Address, slice],
    ) -> None:

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
                    return self.extract(start=start, endex=endex, step=step)
                else:
                    return Memory()  # empty
            else:
                return self.extract(start=start, endex=endex, pattern=step)
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
                self.write(offset, memory, clear=True)
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

        yield from self.values(self.start, self.endex)

    def __len__(
        self,
    ) -> Address:

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

        yield from self.rvalues(self.start, self.endex)

    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Optional[Union[AnyBytes, Value]],
    ) -> None:

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

        return None

    def _block_index_endex(
        self,
        address: Address,
    ) -> BlockIndex:

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

        return right + 1

    def _block_index_start(
        self,
        address: Address,
    ) -> BlockIndex:

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

        trim_endex = self._trim_endex
        if trim_endex is not None and size > 0:
            start = trim_endex - size
            if start_min is not None and start < start_min:
                start = start_min
            return self.extract(start=start, endex=None)
        else:
            return self.__class__()

    def _pretrim_start(
        self,
        endex_max: Optional[Address],
        size: Address,
    ) -> None:

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

        trim_start = self._trim_start
        if trim_start is not None and size > 0:
            endex = trim_start + size

            if endex_max is not None and endex > endex_max:
                endex = endex_max

            return self.extract(start=None, endex=endex)
        else:
            return self.__class__()

    def append(
        self,
        item: Union[AnyBytes, Value],
    ) -> None:

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

        return None

    def append_restore(
        self,
    ) -> None:

        self.pop()

    def block_span(
        self,
        address: Address,
    ) -> Tuple[Optional[Address], Optional[Address], Optional[Value]]:

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

        return self.extract(start=start, endex=endex)

    def clear_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.write(0, backup, clear=True)

    def content_blocks(
        self,
        block_index_start: Optional[BlockIndex] = None,
        block_index_endex: Optional[BlockIndex] = None,
        block_index_step: Optional[BlockIndex] = None,
    ) -> Iterator[Union[Tuple[Address, Union[memoryview, bytearray]], Block]]:

        blocks = self._blocks

        if block_index_start is not None and block_index_start < 0:
            block_index_start = len(blocks) + block_index_start

        if block_index_endex is not None and block_index_endex < 0:
            block_index_endex = len(blocks) + block_index_endex

        yield from _islice(blocks, block_index_start, block_index_endex, block_index_step)

    @ImmutableMemory.content_endex.getter
    def content_endex(
        self,
    ) -> Address:

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

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            return block_start + len(block_data) - 1
        elif self._trim_start is None:  # default to start-1
            return -1
        else:
            return self._trim_start - 1  # default to start-1

    def content_items(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[Tuple[Address, Value]]:

        blocks = self._blocks
        if blocks:
            if start is None and endex is None:  # faster
                for block_start, block_data in blocks:
                    address = block_start + 0
                    for value in block_data:
                        yield address, value
                        address += 1
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
                        address = slice_start + 0
                        for value in slice_view[(slice_start - block_start):(slice_endex - block_start)]:
                            yield address, value
                            address += 1

    def content_keys(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[Address]:

        blocks = self._blocks
        if blocks:
            if start is None and endex is None:  # faster
                for block_start, block_data in blocks:
                    block_endex = block_start + len(block_data)
                    yield from range(block_start, block_endex)
            else:
                block_index_start = 0 if start is None else self._block_index_start(start)
                block_index_endex = len(blocks) if endex is None else self._block_index_endex(endex)
                start, endex = self.bound(start, endex)
                block_iterator = _islice(blocks, block_index_start, block_index_endex)

                for block_start, block_data in block_iterator:
                    block_endex = block_start + len(block_data)
                    slice_start = block_start if start < block_start else start
                    slice_endex = endex if endex < block_endex else block_endex
                    yield from range(slice_start, slice_endex)

    @ImmutableMemory.content_parts.getter
    def content_parts(
        self,
    ) -> int:

        return len(self._blocks)

    @ImmutableMemory.content_size.getter
    def content_size(
        self,
    ) -> Address:

        return sum(len(block_data) for _, block_data in self._blocks)

    @ImmutableMemory.content_span.getter
    def content_span(
        self,
    ) -> ClosedInterval:

        return self.content_start, self.content_endex

    @ImmutableMemory.content_start.getter
    def content_start(
        self,
    ) -> Address:

        blocks = self._blocks
        if blocks:
            return blocks[0][0]
        elif self._trim_start is None:
            return 0
        else:
            return self._trim_start

    def content_values(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[Value]:

        blocks = self._blocks
        if blocks:
            if start is None and endex is None:  # faster
                for block in blocks:
                    yield from block[1]
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
                        yield from slice_view[(slice_start - block_start):(slice_endex - block_start)]

    @ImmutableMemory.contiguous.getter
    def contiguous(
        self,
    ) -> bool:

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

        return self.__deepcopy__()

    def crop(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

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

        backup_start = None
        backup_endex = None

        blocks = self._blocks  # may change
        if blocks:
            if start is not None:
                block_start = blocks[0][0]
                if block_start < start:
                    backup_start = self.extract(start=block_start, endex=start)

            if endex is not None:
                block_start, block_data = blocks[-1]
                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    backup_endex = self.extract(start=endex, endex=block_endex)

        return backup_start, backup_endex

    def crop_restore(
        self,
        backup_start: Optional[ImmutableMemory],
        backup_endex: Optional[ImmutableMemory],
    ) -> None:

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

        return self.extract(start=start, endex=endex)

    def delete_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.reserve(backup.start, len(backup))
        self.write(0, backup, clear=True)

    @ImmutableMemory.endex.getter
    def endex(
        self,
    ) -> Address:

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

        if offset < 0:
            raise ValueError('negative extension offset')
        self.write(self.content_endex + offset, items, clear=True)

    def extend_backup(
        self,
        offset: Address = 0,
    ) -> Address:

        if offset < 0:
            raise ValueError('negative extension offset')
        return self.content_endex + offset

    def extend_restore(
        self,
        content_endex: Address,
    ) -> None:

        self.clear(content_endex)

    def extract(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
        step: Optional[Address] = None,
        bound: bool = True,
    ) -> 'Memory':

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

        return self.extract(start=start, endex=endex)

    def fill_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.write(0, backup, clear=True)

    def find(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

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

        return list(self.gaps(start, endex))

    def flood_restore(
        self,
        gaps: List[OpenInterval],
    ) -> None:

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

        offset = Address(offset)

        if copy:
            blocks = [[block_start + offset, bytearray(block_data)]
                      for block_start, block_data in blocks]
        elif offset:
            blocks = [[block_start + offset, block_data]
                      for block_start, block_data in blocks]

        memory = cls(start=start, endex=endex)
        memory._blocks = blocks

        if start is not None or endex is not None:
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
    def from_items(
        cls,
        items: Union[AddressValueMapping,
                     Iterable[Tuple[Address, Optional[Value]]],
                     Mapping[Address, Optional[Union[Value, AnyBytes]]],
                     ImmutableMemory],
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        validate: bool = True,
    ) -> 'Memory':

        blocks = []
        items = dict(items)
        keys = [key for key, value in items.items() if value is not None]

        if keys:
            keys.sort()
            key_seq = keys[0]
            block_start = key_seq
            block_data = bytearray()

            for key in keys:
                if key == key_seq:
                    block_data.append(items[key])
                    key_seq = key_seq + 1
                else:
                    blocks.append([block_start + offset, block_data])
                    block_start = key
                    block_data = bytearray()
                    block_data.append(items[key])
                    key_seq = key + 1

            blocks.append([block_start + offset, block_data])

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
    def from_values(
        cls,
        values: Iterable[Optional[Value]],
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        validate: bool = True,
    ) -> 'Memory':

        blocks = []
        block_start = offset
        block_data = bytearray()

        for value in values:
            offset += 1

            if start is not None and offset <= start:
                block_start = offset
                continue

            if endex is not None and offset > endex:
                break

            if value is None:
                if block_data:
                    blocks.append([block_start, block_data])
                    block_data = bytearray()
                block_start = offset
            else:
                block_data.append(value)

        if block_data:
            blocks.append([block_start, block_data])

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

        size = 1 if isinstance(data, Value) else len(data)
        self.reserve(address, size)
        self.write(address, data, clear=True)

    def insert_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
    ) -> Tuple[Address, ImmutableMemory]:

        size = 1 if isinstance(data, Value) else len(data)
        backup = self._pretrim_endex_backup(address, size)
        return address, backup

    def insert_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:

        self.delete(address, address + len(backup))
        self.write(0, backup, clear=True)

    def intervals(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[ClosedInterval]:

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
    ) -> Iterator[Tuple[Address, Optional[Value]]]:

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

        try:
            return self.index(item, start, endex)
        except ValueError:
            return None

    def peek(
        self,
        address: Address,
    ) -> Optional[Value]:

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

        return address, self.peek(address)

    def poke_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:

        self.poke(address, item)

    def pop(
        self,
        address: Optional[Address] = None,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

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

        if address is None:
            address = self.endex - 1
        return address, self.peek(address)

    def pop_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:

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

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            value = block_data[-1]
            address = block_start + len(block_data) - 1
            return address, value
        raise KeyError('empty')

    def popitem_restore(
        self,
        address: Address,
        item: Value,
    ) -> None:

        if address == self.content_endex:
            self.append(item)
        else:
            self.insert(address, item)

    def remove(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        address = self.index(item, start, endex)
        size = 1 if isinstance(item, Value) else len(item)
        self._erase(address, address + size, True)  # delete

    def remove_backup(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        address = self.index(item, start, endex)
        size = 1 if isinstance(item, Value) else len(item)
        return self.extract(start=address, endex=(address + size))

    def remove_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.reserve(backup.start, len(backup))
        self.write(0, backup, clear=True)

    def reserve(
        self,
        address: Address,
        size: Address,
    ) -> None:

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

        backup = self._pretrim_endex_backup(address, size)
        return address, backup

    def reserve_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:

        self.delete(address, address + len(backup))
        self.write(0, backup, clear=True)

    def reverse(
        self,
    ) -> None:

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
    ) -> Tuple[Address, Optional[Value]]:

        backup = self.peek(address)
        return address, backup

    def setdefault_restore(
        self,
        address: Address,
        item: Optional[Value],
    ) -> None:

        self.poke(address, item)

    def shift(
        self,
        offset: Address,
    ) -> None:

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

        self.shift(-offset)
        self.write(0, backup, clear=True)

    @ImmutableMemory.span.getter
    def span(
        self,
    ) -> ClosedInterval:

        return self.start, self.endex

    @ImmutableMemory.start.getter
    def start(
        self,
    ) -> Address:

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

        blocks = [[block_start, bytes(block_data)]
                  for block_start, block_data in self.blocks(start, endex)]
        return blocks

    def to_bytes(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> bytes:

        return bytes(self.view(start, endex))

    @ImmutableMemory.trim_endex.getter
    def trim_endex(
        self,
    ) -> Optional[Address]:

        return self._trim_endex

    @trim_endex.setter
    def trim_endex(
        self,
        trim_endex: Optional[Address],
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

        return self._trim_start

    @trim_start.setter
    def trim_start(
        self,
        trim_start: Optional[Address],
    ) -> None:

        trim_endex = self._trim_endex
        if trim_start is not None and trim_endex is not None and trim_endex < trim_start:
            self._trim_endex = trim_endex = trim_start

        self._trim_start = trim_start
        if trim_start is not None:
            self.crop(trim_start, trim_endex)

    def update(
        self,
        data: Union[AddressValueMapping,
                    Iterable[Tuple[Address, Optional[Value]]],
                    Mapping[Address, Optional[Union[Value, AnyBytes]]],
                    ImmutableMemory],
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> None:

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            self.write(0, data, clear=clear)
        else:
            if isinstance(data, Mapping):
                data = data.items()
            poke = self.poke
            for address, value in data:
                poke(address, value)

    def update_backup(
        self,
        data: Union[AddressValueMapping,
                    Iterable[Tuple[Address, Optional[Value]]],
                    Mapping[Address, Optional[Union[Value, AnyBytes]]],
                    ImmutableMemory],
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> Union[AddressValueMapping, List[ImmutableMemory]]:

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            return self.write_backup(0, data, clear=clear)
        else:
            peek = self.peek
            if isinstance(data, Mapping):
                backups = {address: peek(address) for address in data.keys()}
            else:
                backups = {address: peek(address) for address, _ in data}
            return backups

    def update_restore(
        self,
        backups: Union[AddressValueMapping, List[ImmutableMemory]],
    ) -> None:

        if isinstance(backups, list):
            for backup in backups:
                self.write(0, backup, clear=True)
        else:
            self.update(backups)

    def validate(
        self,
    ) -> None:

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
        clear: bool = False,
    ) -> List[ImmutableMemory]:

        if isinstance(data, ImmutableMemory):
            start = data.start + address
            endex = data.endex + address
            if endex <= start:
                backups = []
            elif clear:
                backups = [self.extract(start=start, endex=endex)]
            else:
                intervals = data.intervals(start=start, endex=endex)
                backups = [self.extract(start=block_start, endex=block_endex)
                           for block_start, block_endex in intervals]
        else:
            if isinstance(data, Value):
                data = (data,)
            start = address
            endex = start + len(data)
            if start < endex:
                backups = [self.extract(start=start, endex=endex)]
            else:
                backups = []
        return backups

    def write_restore(
        self,
        backups: Sequence[ImmutableMemory],
    ) -> None:

        for backup in backups:
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
                if endex <= start:
                    return

                del data[(endex - start):]

            self._blocks.append([start, data])

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
            address = self.endex + address
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
            pair of int: Rectified address span.
        """

        endex_ = None

        if start is not None and start < 0:
            endex_ = self.endex
            start = endex_ + start
            if start < 0:
                start = 0

        if endex is not None and endex < 0:
            if endex_ is None:
                endex_ = self.endex
            endex = endex_ + endex
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
        yield from super().blocks(start=start, endex=endex)

    def bound(
        self,
        start: Optional[Address],
        endex: Optional[Address],
    ) -> ClosedInterval:

        start, endex = self._rectify_span(start, endex)
        return super().bound(start=start, endex=endex)

    def clear(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().clear(start=start, endex=endex)

    def clear_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().clear_backup(start=start, endex=endex)

    def count(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> int:

        start, endex = self._rectify_span(start, endex)
        return super().count(item, start=start, endex=endex)

    def crop(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().crop(start=start, endex=endex)

    def crop_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Tuple[Optional[ImmutableMemory], Optional[ImmutableMemory]]:

        start, endex = self._rectify_span(start, endex)
        return super().crop_backup(start=start, endex=endex)

    def cut(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        bound: bool = True,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().cut(start=start, endex=endex)

    def delete(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().delete(start=start, endex=endex)

    def delete_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().delete_backup(start=start, endex=endex)

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
        return super().extract(start=start, endex=endex, pattern=pattern, step=step, bound=bound)

    def fill(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().fill(start=start, endex=endex, pattern=pattern)

    def fill_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().fill_backup(start=start, endex=endex)

    def find(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().find(item, start=start, endex=endex)

    def flood(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        pattern: Union[AnyBytes, Value] = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().flood(start=start, endex=endex, pattern=pattern)

    def flood_backup(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> List[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        return super().flood_backup(start=start, endex=endex)

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

        memory1 = super().from_blocks(blocks, offset=offset, start=start, endex=endex, copy=copy, validate=validate)
        memory2 = cls()
        memory2._blocks = memory1._blocks
        memory2._trim_start = memory1._trim_start
        memory2._trim_endex = memory1._trim_endex
        return memory2

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

        memory1 = super().from_bytes(data, offset=offset, start=start, endex=endex, copy=copy, validate=validate)
        memory2 = cls()
        memory2._blocks = memory1._blocks
        memory2._trim_start = memory1._trim_start
        memory2._trim_endex = memory1._trim_endex
        return memory2

    @classmethod
    def from_memory(
        cls,
        memory: ImmutableMemory,
        offset: Address = 0,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'bytesparse':

        if isinstance(memory, Memory):
            blocks = memory._blocks
            if blocks:
                block_start = blocks[0][0]
                if block_start + offset < 0:
                    raise ValueError('negative offseted start')
        else:
            if memory:
                if memory.start + offset < 0:
                    raise ValueError('negative offseted start')

        if start is not None and start < 0:
            raise ValueError('negative start')
        if endex is not None and endex < 0:
            raise ValueError('negative endex')

        memory1 = super().from_memory(memory, offset=offset, start=start, endex=endex, copy=copy, validate=validate)
        memory2 = cls()
        memory2._blocks = memory1._blocks
        memory2._trim_start = memory1._trim_start
        memory2._trim_endex = memory1._trim_endex
        return memory2

    def gaps(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Iterator[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        yield from super().gaps(start=start, endex=endex)

    def get(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

        address = self._rectify_address(address)
        return super().get(address, default=default)

    def index(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().index(item, start=start, endex=endex)

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
        yield from super().intervals(start=start, endex=endex)

    def items(
        self,
        start: Optional[Address] = None,
        endex: Optional[Union[Address, EllipsisType]] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Tuple[Address, Optional[Value]]]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().items(start=start, endex=endex, pattern=pattern)

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
        yield from super().keys(start=start, endex=endex)

    def ofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:

        start, endex = self._rectify_span(start, endex)
        return super().ofind(item, start=start, endex=endex)

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
        return super().pop(address=address, default=default)

    def pop_backup(
        self,
        address: Optional[Address] = None,
    ) -> Tuple[Address, Optional[Value]]:

        if address is not None:
            address = self._rectify_address(address)
        return super().pop_backup(address=address)

    def remove(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().remove(item, start=start, endex=endex)

    def remove_backup(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().remove_backup(item, start=start, endex=endex)

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
        return super().rfind(item, start=start, endex=endex)

    def rindex(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().rindex(item, start=start, endex=endex)

    def rofind(
        self,
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:

        start, endex = self._rectify_span(start, endex)
        return super().rofind(item, start=start, endex=endex)

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
        yield from super().rvalues(start=start, endex=endex, pattern=pattern)

    def setdefault(
        self,
        address: Address,
        default: Optional[Value] = None,
    ) -> Optional[Value]:

        address = self._rectify_address(address)
        return super().setdefault(address, default=default)

    def setdefault_backup(
        self,
        address: Address,
    ) -> Tuple[Address, Optional[Value]]:

        address = self._rectify_address(address)
        return super().setdefault_backup(address)

    def shift(
        self,
        offset: Address,
    ) -> None:

        if self._trim_start is None and offset < 0:
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

        if self._trim_start is None and offset < 0:
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
        trim_endex: Optional[Address],
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
        trim_start: Optional[Address],
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
        yield from super().values(start=start, endex=endex, pattern=pattern)

    def view(
        self,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> memoryview:

        start, endex = self._rectify_span(start, endex)
        return super().view(start=start, endex=endex)

    def write(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
        clear: bool = False,
    ) -> None:

        address = self._rectify_address(address)
        super().write(address, data, clear=clear)

    def write_backup(
        self,
        address: Address,
        data: Union[AnyBytes, Value, ImmutableMemory],
        clear: bool = False,
    ) -> List[ImmutableMemory]:

        address = self._rectify_address(address)
        return super().write_backup(address, data, clear=clear)
