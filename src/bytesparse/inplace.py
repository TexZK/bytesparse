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

r"""In-place implementation.

This implementation in pure Python uses the basic :class:`bytearray` data type
to hold block data, which allows mutable in-place operations.
"""

import io
import sys
from collections.abc import Mapping
from collections.abc import Sequence
from itertools import count as _count
from itertools import islice as _islice
from itertools import repeat as _repeat
from itertools import zip_longest as _zip_longest
from typing import Any
from typing import Union  # NOTE: type | operator unsupported for Python < 3.10
from typing import cast as _cast

from .base import HUMAN_ASCII
from .base import STR_MAX_CONTENT_SIZE
from .base import Address
from .base import AddressValueMapping
from .base import AnyBytes
from .base import AnyItems
from .base import Block
from .base import BlockIndex
from .base import BlockIterable
from .base import BlockList
from .base import BlockSequence
from .base import ByteString
from .base import ClosedInterval
from .base import EllipsisType
from .base import ImmutableMemory
from .base import Iterable
from .base import Iterator
from .base import MutableBytesparse
from .base import MutableMemory
from .base import OpenInterval
from .base import OptionalAddress
from .base import OptionalValue
from .base import Value


def _repeat2(
    pattern: Union[ByteString, None],
    offset: Address,
    size: OptionalAddress,
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
            yield from _repeat(None)  # type: ignore

        elif 0 < size:
            yield from _repeat(None, size)  # type: ignore

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


class Memory(MutableMemory):
    r"""Virtual memory.

    This class is a handy wrapper around `blocks`, so that it can behave mostly
    like a :obj:`bytearray`, but on sparse chunks of data.

    Please look at examples of each method to get a glimpse of the features of
    this class.

    See Also:
        :obj:`ImmutableMemory`
        :obj:`MutableMemory`

    Attributes:
        _blocks (list of blocks):
            A sequence of spaced blocks, sorted by address.

        _bound_start (int):
            Memory bounds start address. Any data before this address is
            automatically discarded; disabled if ``None``.

        _bound_endex (int):
            Memory bounds exclusive end address. Any data at or after this
            address is automatically discarded; disabled if ``None``.

    """
    __doc__ += ImmutableMemory.__doc__[  # type: ignore __doc__
        ImmutableMemory.__doc__.index('Arguments:'):  # type: ignore __doc__
        ImmutableMemory.__doc__.index('Method Groups:')  # type: ignore __doc__
    ]

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
        item: Any,
    ) -> bool:

        return any(item in block_data for _, block_data in self._blocks)

    def __copy__(
        self,
    ) -> 'Memory':

        return self.from_memory(self, start=self._bound_start, endex=self._bound_endex, copy=False)

    def __deepcopy__(
        self,
    ) -> 'Memory':

        return self.from_memory(self, start=self._bound_start, endex=self._bound_endex, copy=True)

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
                    return self.__class__()  # empty
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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ):

        if start is not None:
            start = Address(start)
        if endex is not None:
            endex = Address(endex)
            if start is not None and endex < start:
                endex = start

        self._blocks: BlockList = []
        self._bound_start: OptionalAddress = start
        self._bound_endex: OptionalAddress = endex

    def __ior__(
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'Memory':

        self.write(0, value)
        return self

    def __iter__(
        self,
    ) -> Iterator[OptionalValue]:

        yield from self.values(start=self.start, endex=self.endex)

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

    def __or__(
        self,
        value: Union[AnyBytes, ImmutableMemory],
    ) -> 'Memory':

        memory = self.from_memory(self, validate=False)
        memory.write(0, value)
        return memory

    def __repr__(
        self,
    ) -> str:

        return f'<{self.__class__.__name__}[0x{self.start:X}:0x{self.endex:X}]@0x{id(self):X}>'

    def __reversed__(
        self,
    ) -> Iterator[OptionalValue]:

        yield from self.rvalues(start=self.start, endex=self.endex)

    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Union[AnyBytes, Value, None],
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
            value = _cast(AnyBytes, value)
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
            bound_start = '' if self._bound_start is None else f'{self._bound_start}, '
            bound_endex = '' if self._bound_endex is None else f', {self._bound_endex}'

            inner = ', '.join(f'({block_start}, b{block_data.decode()!r})'
                              for block_start, block_data in self._blocks)

            return f'<{bound_start}[{inner}]{bound_endex}>'
        else:
            return repr(self)

    def _block_index_at(
        self,
        address: Address,
    ) -> Union[BlockIndex, None]:

        blocks = self._blocks
        if blocks:
            block_start, _ = blocks[0]
            if address < block_start:  # before first block
                return None

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:  # after last block
                return None
        else:
            return None

        # Dichotomic search
        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:  # after center block
                left = center + 1
            elif address < block_start:  # before center block
                right = center - 1
            else:  # within center block
                return center

        return None

    def _block_index_endex(
        self,
        address: Address,
    ) -> BlockIndex:

        blocks = self._blocks
        if blocks:
            block_start, _ = blocks[0]
            if address < block_start:  # before first block
                return 0

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:  # after last block
                return len(blocks)
        else:
            return 0

        # Dichotomic search
        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:  # after center block
                left = center + 1
            elif address < block_start:  # before center block
                right = center - 1
            else:  # within center block
                return center + 1

        return right + 1

    def _block_index_start(
        self,
        address: Address,
    ) -> BlockIndex:

        blocks = self._blocks
        if blocks:
            block_start, _ = blocks[0]
            if address <= block_start:  # before first block
                return 0

            block_start, block_data = blocks[-1]
            if block_start + len(block_data) <= address:  # after last block
                return len(blocks)
        else:
            return 0

        # Dichotomic search
        left = 0
        right = len(blocks)

        while left <= right:
            center = (left + right) >> 1
            block_start, block_data = blocks[center]

            if block_start + len(block_data) <= address:  # after center block
                left = center + 1
            elif address < block_start:  # before center block
                right = center - 1
            else:  # within center block
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
                        blocks.insert(block_index, (block_start, block_data))
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
                    block_start += offset  # update address
                    blocks[block_index] = (block_start, block_data)
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
                    block_start, block_data = blocks[block_index]
                    block_start -= size  # update address
                    blocks[block_index] = (block_start, block_data)

            # Delete inner full blocks
            if inner_start < inner_endex:
                del blocks[inner_start:inner_endex]

    def _place(
        self,
        address: Address,
        data: bytearray,
        shift_after: bool,
    ) -> None:
        r"""Places data.

        Low-level method to place data into the underlying data structure.

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
                            block_start, block_data = blocks[block_index]
                            block_start += size
                            blocks[block_index] = (block_start, block_data)
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
                        blocks.insert(block_index, (address, data))
                    else:
                        if address + len(data) == block_start:
                            # Merge with next block
                            blocks[block_index] = (address, block_data)
                            block_data[0:0] = data
                        else:
                            # Insert a standalone block before
                            blocks.insert(block_index, (address, data))
                else:
                    # Insert data into the current block
                    offset = address - block_start
                    block_data[offset:offset] = data

                # Shift blocks after
                if shift_after:
                    for block_index in range(block_index + 1, len(blocks)):
                        block_start, block_data = blocks[block_index]
                        block_start += size
                        blocks[block_index] = (block_start, block_data)

            else:
                # Append a standalone block after
                blocks.append((address, data[:]))

    def _prebound_endex(
        self,
        start_min: OptionalAddress,
        size: Address,
    ) -> None:

        bound_endex = self._bound_endex
        if bound_endex is not None and size > 0:
            start = bound_endex - size

            if start_min is not None and start < start_min:
                start = start_min

            self._erase(start, self.content_endex, False)  # clear

    def _prebound_endex_backup(
        self,
        start_min: OptionalAddress,
        size: Address,
    ) -> ImmutableMemory:

        bound_endex = self._bound_endex
        if bound_endex is not None and size > 0:
            start = bound_endex - size
            if start_min is not None and start < start_min:
                start = start_min
            return self.extract(start=start, endex=None)
        else:
            return self.__class__()

    def _prebound_start(
        self,
        endex_max: OptionalAddress,
        size: Address,
    ) -> None:

        bound_start = self._bound_start
        if bound_start is not None and size > 0:
            endex = bound_start + size

            if endex_max is not None and endex > endex_max:
                endex = endex_max

            self._erase(self.content_start, endex, False)  # clear

    def _prebound_start_backup(
        self,
        endex_max: OptionalAddress,
        size: Address,
    ) -> ImmutableMemory:

        bound_start = self._bound_start
        if bound_start is not None and size > 0:
            endex = bound_start + size

            if endex_max is not None and endex > endex_max:
                endex = endex_max

            return self.extract(start=None, endex=endex)
        else:
            return self.__class__()

    def align(
        self,
        modulo: int,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
    ) -> None:

        modulo = modulo.__index__()
        if modulo < 1:
            raise ValueError('invalid modulo')
        if modulo == 1:
            return

        intervals = list(self.intervals(start=start, endex=endex))

        for start, endex in intervals:
            start_offset = start % modulo
            if start_offset:
                start -= start_offset

            endex_offset = endex % modulo
            if endex_offset:
                endex += modulo - endex_offset

            if start_offset or endex_offset:
                self.flood(start=start, endex=endex, pattern=pattern)

    def align_backup(
        self,
        modulo: int,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[OpenInterval]:

        modulo = modulo.__index__()
        if modulo < 1:
            raise ValueError('invalid modulo')

        start, endex = self.bound(start, endex)

        if modulo != 1:
            start_offset = start % modulo
            if start_offset:
                start -= start_offset

            endex_offset = endex % modulo
            if endex_offset:
                endex += modulo - endex_offset

        return self.flood_backup(start=start, endex=endex)

    def align_restore(
        self,
        gaps: list[OpenInterval],
    ) -> None:

        self.flood_restore(gaps)

    def append(
        self,
        item: AnyItems,
    ) -> None:

        if not isinstance(item, Value):
            item = _cast(AnyBytes, item)
            if len(item) != 1:
                raise ValueError('expecting single item')
            item = item[0]

        blocks = self._blocks
        if blocks:
            blocks[-1][1].append(item)
        else:
            blocks.append((0, bytearray((item,))))

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
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:

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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[tuple[Address, memoryview]]:

        blocks = self._blocks
        if blocks:
            if start is None and endex is None:  # faster
                for block_start, block_data in blocks:
                    block_view = memoryview(block_data)

                    yield (block_start, block_view)

                    block_view.release()
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
                        slice_view2 = slice_view[(slice_start - block_start):(slice_endex - block_start)]

                        yield (slice_start, slice_view2)

                        slice_view2.release()
                        slice_view.release()

    def bound(
        self,
        start: OptionalAddress,
        endex: OptionalAddress,
    ) -> ClosedInterval:

        blocks = self._blocks
        bound_start = self._bound_start
        bound_endex = self._bound_endex

        if start is None:
            if bound_start is None:
                if blocks:
                    start, _ = blocks[0]
                else:
                    start = 0
            else:
                start = bound_start
        else:
            if bound_start is not None:
                if start < bound_start:
                    start = bound_start
            if endex is not None:
                if endex < start:
                    endex = start

        if endex is None:
            if bound_endex is None:
                if blocks:
                    block_start, block_data = blocks[-1]
                    endex = block_start + len(block_data)
                else:
                    endex = start
            else:
                endex = bound_endex
        else:
            if bound_endex is not None:
                if endex > bound_endex:
                    endex = bound_endex
            if start > endex:
                start = endex

        return start, endex

    @ImmutableMemory.bound_endex.getter
    def bound_endex(
        self,
    ) -> OptionalAddress:

        return self._bound_endex

    @bound_endex.setter
    def bound_endex(
        self,
        bound_endex: OptionalAddress,
    ) -> None:

        bound_start = self._bound_start
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            self._bound_start = bound_start = bound_endex

        self._bound_endex = bound_endex
        if bound_endex is not None:
            self.crop(start=bound_start, endex=bound_endex)

    @ImmutableMemory.bound_span.getter
    def bound_span(
        self,
    ) -> OpenInterval:

        return self._bound_start, self._bound_endex

    @bound_span.setter
    def bound_span(  # type: ignore override
        self,
        bound_span: OpenInterval,
    ) -> None:

        if bound_span is None:
            bound_span = (None, None)
        bound_start, bound_endex = bound_span
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            bound_endex = bound_start

        self._bound_start = bound_start
        self._bound_endex = bound_endex
        if bound_start is not None or bound_endex is not None:
            self.crop(start=bound_start, endex=bound_endex)

    @ImmutableMemory.bound_start.getter
    def bound_start(
        self,
    ) -> OptionalAddress:

        return self._bound_start

    @bound_start.setter
    def bound_start(
        self,
        bound_start: OptionalAddress,
    ) -> None:

        bound_endex = self._bound_endex
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            self._bound_endex = bound_endex = bound_start

        self._bound_start = bound_start
        if bound_start is not None:
            self.crop(start=bound_start, endex=bound_endex)

    def chop(
        self,
        width: Address,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        align: bool = False,
    ) -> Iterator[tuple[Address, memoryview]]:

        if width < 1:
            raise ValueError('invalid width')

        for block_start, block_view in self.blocks(start=start, endex=endex):
            block_size = len(block_view)
            chunk_offset = 0

            if align:
                chunk_offset = block_start % width
                if chunk_offset:
                    chunk_offset = width - chunk_offset
                    chunk_view = block_view[:chunk_offset]

                    yield block_start, chunk_view

            while chunk_offset < block_size:
                chunk_after = chunk_offset + width
                chunk_view = block_view[chunk_offset:chunk_after]

                yield block_start + chunk_offset, chunk_view

                chunk_offset = chunk_after

    def clear(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        if start < endex:
            self._erase(start, endex, False)  # clear

    def clear_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        return self.extract(start=start, endex=endex)

    def clear_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.write(0, backup, clear=True)

    @classmethod
    def collapse_blocks(
        cls,
        blocks: BlockIterable,
    ) -> BlockList:

        memory = cls()

        for block_start, block_data in blocks:
            memory.write(block_start, block_data)

        return memory._blocks

    def content_blocks(
        self,
        block_index_start: Union[BlockIndex, None] = None,
        block_index_endex: Union[BlockIndex, None] = None,
        block_index_step: Union[BlockIndex, None] = None,
    ) -> Iterator[Union[tuple[Address, (Union[memoryview, bytearray])], Block]]:

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
        elif self._bound_start is None:  # default to start
            return 0
        else:
            return self._bound_start  # default to start

    @ImmutableMemory.content_endin.getter
    def content_endin(
        self,
    ) -> Address:

        blocks = self._blocks
        if blocks:
            block_start, block_data = blocks[-1]
            return block_start + len(block_data) - 1
        elif self._bound_start is None:  # default to start-1
            return -1
        else:
            return self._bound_start - 1  # default to start-1

    def content_items(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[tuple[Address, Value]]:

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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
        elif self._bound_start is None:
            return 0
        else:
            return self._bound_start

    def content_values(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

    def count(  # type: ignore override
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> int:

        # Faster code for unbounded slice
        item = _cast(Value, item)
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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        blocks = self._blocks  # may change during execution

        # Bound blocks exceeding before memory start
        if start is not None and blocks:
            block_start = blocks[0][0]

            if block_start < start:
                self._erase(block_start, start, False)  # clear

        # Bound blocks exceeding after memory end
        if endex is not None and blocks:
            block_start, block_data = blocks[-1]
            block_endex = block_start + len(block_data)

            if endex < block_endex:
                self._erase(endex, block_endex, False)  # clear

    def crop_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> tuple[Union[ImmutableMemory, None], Union[ImmutableMemory, None]]:

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
        backup_start: Union[ImmutableMemory, None],
        backup_endex: Union[ImmutableMemory, None],
    ) -> None:

        if backup_start is not None:
            self.write(0, backup_start, clear=True)
        if backup_endex is not None:
            self.write(0, backup_endex, clear=True)

    def cut(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
                memory_block_iter = _islice(blocks, block_index_start, block_index_endex)
                memory_blocks = [(block_start, block_data)
                                 for block_start, block_data in memory_block_iter]

                # Bound cloned data before the selection start address
                block_start, block_data = memory_blocks[0]
                if block_start < start:
                    memory_blocks[0] = (start, block_data[(start - block_start):])

                # Bound cloned data after the selection end address
                block_start, block_data = memory_blocks[-1]
                block_endex = block_start + len(block_data)
                if endex < block_endex:
                    if block_start < endex:
                        memory_blocks[-1] = (block_start, block_data[:(endex - block_start)])
                    else:
                        memory_blocks.pop()

                memory._blocks = memory_blocks
                self._erase(start, endex, False)  # clear

        if bound:
            memory._bound_start = start
            memory._bound_endex = endex

        return memory

    def delete(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        if start < endex:
            self._erase(start, endex, True)  # delete

    def delete_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        bound_endex = self._bound_endex
        if bound_endex is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                block_start, block_data = blocks[-1]
                return block_start + len(block_data)
            else:
                return self.start
        else:
            return bound_endex

    @ImmutableMemory.endin.getter
    def endin(
        self,
    ) -> Address:

        bound_endex = self._bound_endex
        if bound_endex is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                block_start, block_data = blocks[-1]
                return block_start + len(block_data) - 1
            else:
                return self.start - 1
        else:
            return bound_endex - 1

    def equal_span(
        self,
        address: Address,
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:

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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: Union[ByteString, Value, None] = None,
        step: OptionalAddress = None,
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
                    memory_block_iter = _islice(blocks, block_index_start, block_index_endex)
                    memory_blocks: BlockList = [(block_start, bytearray(block_data))
                                                for block_start, block_data in memory_block_iter]

                    # Bound cloned data before the selection start address
                    block_start, block_data = memory_blocks[0]
                    if block_start < start:
                        del block_data[:(start - block_start)]
                        memory_blocks[0] = (start, block_data)

                    # Bound cloned data after the selection end address
                    block_start, block_data = memory_blocks[-1]
                    block_endex = block_start + len(block_data)
                    if endex < block_endex:
                        if block_start < endex:
                            del block_data[(endex - block_start):]
                            memory_blocks[-1] = (block_start, block_data)
                        else:
                            memory_blocks.pop()

                    memory._blocks = memory_blocks

                if pattern is not None:
                    memory.flood(start=start, endex=endex, pattern=pattern)
        else:
            step = int(step)
            if step > 1:
                memory_blocks: BlockList = []
                empty = True
                block_start = 0  # dummy
                block_data = bytearray()  # dummy
                offset = start
                values = self.values(start=start, endex=endex, pattern=pattern)

                for value in _islice(values, 0, endex - start, step):
                    if value is None:
                        if not empty:
                            memory_blocks.append((block_start, block_data))
                            empty = True
                    else:
                        if empty:
                            empty = False
                            block_start = offset
                            block_data = bytearray()
                        assert block_data is not None
                        block_data.append(value)
                    offset += 1

                if not empty:
                    memory_blocks.append((block_start, block_data))

                memory._blocks = memory_blocks
                if bound:
                    endex = offset

        if bound:
            memory._bound_start = start
            memory._bound_endex = endex

        return memory

    def fill(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        return self.extract(start=start, endex=endex)

    def fill_restore(
        self,
        backup: ImmutableMemory,
    ) -> None:

        self.write(0, backup, clear=True)

    def find(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        try:
            return self.index(item, start=start, endex=endex)
        except ValueError:
            return -1

    def flood(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
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
            blocks[block_index_start:block_index_endex] = [(start, pattern)]

            for block_start, block_data in blocks_inner:
                block_endex = block_start + len(block_data)
                pattern[(block_start - start):(block_endex - start)] = block_data

    def flood_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[OpenInterval]:

        return list(self.gaps(start=start, endex=endex))

    def flood_restore(
        self,
        gaps: list[OpenInterval],
    ) -> None:

        for gap_start, gap_endex in gaps:
            self.clear(start=gap_start, endex=gap_endex)

    @classmethod
    def from_blocks(
        cls,
        blocks: BlockSequence,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':

        offset = Address(offset)

        if copy:
            blocks2 = [(block_start + offset, bytearray(block_data))
                       for block_start, block_data in blocks]
        elif offset:
            blocks2 = [(block_start + offset, _cast(bytearray, block_data))
                       for block_start, block_data in blocks]
        else:
            blocks2 = _cast(BlockList, blocks)

        memory = cls(start=start, endex=endex)
        memory._blocks = blocks2

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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':

        blocks: BlockList
        if data:
            if copy:
                data = bytearray(data)
            data = _cast(bytearray, data)
            blocks = [(offset, data)]
        else:
            blocks = []

        return cls.from_blocks(blocks, start=start, endex=endex, copy=False, validate=validate)

    @classmethod
    def from_items(
        cls,
        items: object,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        validate: bool = True,
    ) -> 'Memory':

        blocks = []
        items = dict(_cast(AddressValueMapping, items))
        keys = [key for key, value in items.items() if value is not None]

        if keys:
            keys.sort()
            key_seq = keys[0]
            block_start = key_seq
            block_data = bytearray()

            for key in keys:
                if key == key_seq:
                    block_data.append(items[key])  # type: ignore Sequence[Value]
                    key_seq = key_seq + 1
                else:
                    blocks.append([block_start + offset, block_data])
                    block_start = key
                    block_data = bytearray()
                    block_data.append(items[key])  # type: ignore Sequence[Value]
                    key_seq = key + 1

            blocks.append([block_start + offset, block_data])

        return cls.from_blocks(blocks, start=start, endex=endex, copy=False, validate=validate)

    @classmethod
    def from_memory(
        cls,
        memory: 'Union[ImmutableMemory, Memory]',
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        copy: bool = True,
        validate: bool = True,
    ) -> 'Memory':

        offset = Address(offset)
        is_memory = isinstance(memory, Memory)

        if copy or not is_memory:
            memory_blocks = memory._blocks if is_memory else memory.blocks()

            blocks2 = [(block_start + offset, bytearray(block_data))
                       for block_start, block_data in memory_blocks]
        else:
            if offset:
                blocks2 = [(block_start + offset, block_data)
                           for block_start, block_data in memory._blocks]
            else:
                blocks2 = memory._blocks

        return cls.from_blocks(blocks2, start=start, endex=endex, copy=False, validate=validate)

    @classmethod
    def from_values(
        cls,
        values: Iterable[OptionalValue],
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        return cls.from_blocks(blocks, start=start, endex=endex, copy=False, validate=validate)

    @classmethod
    def fromhex(
        cls,
        string: str,
    ) -> 'Memory':

        data = bytearray.fromhex(string)
        obj = cls()
        if data:
            obj._blocks.append((0, data))
        return obj

    def gaps(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[OpenInterval]:

        blocks = self._blocks
        if blocks:
            start_ = start
            endex_ = endex
            start, endex = self.bound(start, endex)

            if start_ is None:
                start, _ = blocks[0]  # override bound start
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
        default: OptionalValue = None,
    ) -> OptionalValue:

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

        _, data = self._blocks[0]
        return data.hex(*args)

    def hexdump(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        columns: int = 16,
        addrfmt: str = '{:08X} ',
        bytefmt: str = ' {:02X}',
        headfmt: Union[str, EllipsisType, None] = None,
        charmap: Union[Mapping[int, str], None] = HUMAN_ASCII,
        emptystr: str = ' --',
        beforestr: str = ' >>',
        afterstr: str = ' <<',
        charsep: str = '  |',
        charend: str = '|',
        stream: Union[io.TextIOBase, EllipsisType, None] = Ellipsis,
    ) -> Union[str, None]:

        if columns < 1:
            raise ValueError('invalid columns')
        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex
        if endex <= start:
            endex = start
        elif endex < start + columns:
            endex = start + columns
        if stream is Ellipsis:
            stream = _cast(io.TextIOBase, sys.stdout)

        addrfmt_format = addrfmt.format
        bytefmt_format = bytefmt.format
        bytemap = [bytefmt_format(i) for i in range(0x100)]
        tokens = []
        append = tokens.append if stream is None else _cast(io.TextIOBase, stream).write
        self_values = self.values(start=start, endex=...)
        bound_start = self._bound_start
        bound_endex = self._bound_endex
        values = [0x100] * columns
        address = int(start)

        if headfmt:
            if headfmt is Ellipsis:
                headfmt = bytefmt
            headfmt = _cast(str, headfmt)
            append(' ' * len(addrfmt_format(address)))
            if ((columns - 1) & columns) == 0:  # power of 2
                for i in range(columns):
                    append(headfmt.format((address + i) % columns))
            else:  # header value offset makes no sense
                for i in range(columns):
                    append(headfmt.format(i))
            append('\n')

        while address < endex:
            append(addrfmt_format(address))

            for i in range(columns):
                byteval = next(self_values)
                if byteval is not None:
                    append(bytemap[byteval])
                elif bound_start is not None and address < bound_start:
                    append(beforestr)
                    byteval = 0x101
                elif bound_endex is not None and address >= bound_endex:
                    append(afterstr)
                    byteval = 0x102
                else:
                    append(emptystr)
                    byteval = 0x100
                values[i] = byteval
                address += 1

            if charmap is not None:
                append(charsep)
                for byteval in values:
                    append(charmap[byteval])
                append(charend)

            append('\n')
        return ''.join(tokens) if stream is None else None

    def index(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        # Faster code for unbounded slice
        if start is None and endex is None:
            for block_start, block_data in self._blocks:
                try:
                    offset = block_data.index(item)  # type: ignore SupportsIndex
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
                offset = block_data.index(item, slice_start, slice_endex)  # type: ignore SupportsIndex
            except ValueError:
                pass
            else:
                return block_start + offset
        else:
            raise ValueError('subsection not found')

    def insert(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> None:

        size = 1 if isinstance(data, Value) else len(data)
        self.reserve(address, size)
        self.write(address, data, clear=True)

    def insert_backup(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> tuple[Address, ImmutableMemory]:

        size = 1 if isinstance(data, Value) else len(data)
        backup = self._prebound_endex_backup(address, size)
        return address, backup

    def insert_restore(
        self,
        address: Address,
        backup: ImmutableMemory,
    ) -> None:

        self.delete(start=address, endex=(address + len(backup)))
        self.write(0, backup, clear=True)

    def intervals(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[tuple[Address, OptionalValue]]:

        if start is None:
            start = self.start
        if endex is None:
            endex = self.endex

        keys = self.keys(start=start, endex=endex)
        values = self.values(start=start, endex=endex, pattern=pattern)
        yield from zip(keys, values)

    def keys(
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
    ) -> Iterator[Address]:

        if start is None:
            start = self.start

        if endex is Ellipsis:
            yield from _count(start)
        else:
            if endex is None:
                endex = self.endex
            endex = _cast(Address, endex)
            yield from range(start, endex)

    def peek(
        self,
        address: Address,
    ) -> OptionalValue:

        block_index = self._block_index_at(address)
        if block_index is None:
            return None
        else:
            block_start, block_data = self._blocks[block_index]
            return block_data[address - block_start]

    def poke(
        self,
        address: Address,
        item: Union[AnyBytes, Value, None],
    ) -> None:

        if self._bound_start is not None and address < self._bound_start:
            return
        if self._bound_endex is not None and address >= self._bound_endex:
            return

        if item is None:
            # Standard clear method
            self._erase(address, address + 1, False)  # clear

        else:
            if not isinstance(item, Value):
                item = _cast(AnyBytes, item)
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
                        block_start, block_data = blocks[block_index]

                        if address + 1 == block_start:
                            # Prepend to the next block
                            block_data.insert(0, item)
                            block_start -= 1  # update address
                            blocks[block_index] = (block_start, block_data)
                            return

            # There is no faster way than the standard block writing method
            self._erase(address, address + 1, False)  # clear
            self._place(address, bytearray((item,)), False)  # write

            self.crop(start=self._bound_start, endex=self._bound_endex)

    def poke_backup(
        self,
        address: Address,
    ) -> tuple[Address, OptionalValue]:

        return address, self.peek(address)

    def poke_restore(
        self,
        address: Address,
        item: OptionalValue,
    ) -> None:

        self.poke(address, item)

    def pop(
        self,
        address: OptionalAddress = None,
        default: OptionalValue = None,
    ) -> OptionalValue:

        if address is None:
            blocks = self._blocks
            if blocks:
                _, block_data = blocks[-1]
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
        address: OptionalAddress = None,
    ) -> tuple[Address, OptionalValue]:

        if address is None:
            address = self.endex - 1
        return address, self.peek(address)

    def pop_restore(
        self,
        address: Address,
        item: OptionalValue,
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
    ) -> tuple[Address, Value]:

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
    ) -> tuple[Address, Value]:

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

    def read(
        self,
        address: Address,
        size: Address,
    ) -> memoryview:

        return self.view(start=address, endex=(address + size))

    def readinto(
        self,
        address: Address,
        buffer: Union[bytearray, memoryview],
    ) -> int:

        size = len(buffer)
        view = self.view(start=address, endex=(address + size))
        buffer[:] = view
        return size

    def remove(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        address = self.index(item, start=start, endex=endex)
        size = 1 if isinstance(item, Value) else len(item)
        self._erase(address, address + size, True)  # delete

    def remove_backup(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        address = self.index(item, start=start, endex=endex)
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
            self._prebound_endex(address, size)
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

                    blocks.insert(block_index, (address + size, data_after))
                    block_index += 1

                for block_index in range(block_index, len(blocks)):
                    block_start, block_data = blocks[block_index]
                    block_start += size
                    blocks[block_index] = (block_start, block_data)

    def reserve_backup(
        self,
        address: Address,
        size: Address,
    ) -> tuple[Address, ImmutableMemory]:

        backup = self._prebound_endex_backup(address, size)
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

            for block_index in range(len(blocks)):
                block_start, block_data = blocks[block_index]
                block_data.reverse()
                block_start = endex - block_start - len(block_data) + start
                blocks[block_index] = block_start, block_data

            blocks.reverse()

    def rfind(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        try:
            return self.rindex(item, start=start, endex=endex)
        except ValueError:
            return -1

    def rindex(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        # Faster code for unbounded slice
        if start is None and endex is None:
            for block_start, block_data in reversed(self._blocks):
                try:
                    offset = block_data.index(item)  # type: ignore SupportsIndex
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
                offset = block_data.rindex(item, slice_start, slice_endex)  # type: ignore SupportsIndex
            except ValueError:
                pass
            else:
                return block_start + offset
        else:
            raise ValueError('subsection not found')

    def rvalues(
        self,
        start: Union[Address, EllipsisType, None] = None,
        endex: OptionalAddress = None,
        pattern: Union[AnyBytes, Value, None] = None,
    ) -> Iterator[OptionalValue]:

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
        start = _cast(Address, start)

        blocks = self._blocks
        if endex is None:
            endex = self.endex
            block_index = len(blocks)
        else:
            block_index = self._block_index_endex(endex)
        endex = _cast(Address, endex)

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
        default: Union[AnyBytes, Value, None] = None,
    ) -> OptionalValue:

        backup = self.peek(address)
        if backup is None:
            if default is not None:
                if not isinstance(default, Value):
                    default = _cast(AnyBytes, default)
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
    ) -> tuple[Address, OptionalValue]:

        backup = self.peek(address)
        return address, backup

    def setdefault_restore(
        self,
        address: Address,
        item: OptionalValue,
    ) -> None:

        self.poke(address, item)

    def shift(
        self,
        offset: Address,
    ) -> None:

        blocks = self._blocks
        if offset and blocks:
            if offset < 0:
                self._prebound_start(None, -offset)
            else:
                self._prebound_endex(None, +offset)

            for block_index in range(len(blocks)):
                block_start, block_data = blocks[block_index]
                block_start += offset
                blocks[block_index] = (block_start, block_data)

    def shift_backup(
        self,
        offset: Address,
    ) -> tuple[Address, ImmutableMemory]:

        if offset < 0:
            backup = self._prebound_start_backup(None, -offset)
        else:
            backup = self._prebound_endex_backup(None, +offset)
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

        bound_start = self._bound_start
        if bound_start is None:
            # Return actual
            blocks = self._blocks
            if blocks:
                return blocks[0][0]
            else:
                return 0
        else:
            return bound_start

    def to_blocks(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[tuple[Address, bytes]]:

        blocks = [(block_start, bytes(block_data))
                  for block_start, block_data in self.blocks(start=start, endex=endex)]
        return blocks

    def to_bytes(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> bytes:

        return bytes(self.view(start=start, endex=endex))

    def update(
        self,
        data: object,
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> None:

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            self.write(0, data, clear=clear)
        else:
            if hasattr(data, 'items') and callable(getattr(data, 'items')):
                data = _cast(Mapping[Address, OptionalValue], data)
                data_iter = data.items()
            else:
                data_iter = _cast(Iterable[tuple[Address, OptionalValue]], data)
            poke = self.poke
            for address, value in data_iter:
                poke(address, value)

    def update_backup(
        self,
        data: object,
        clear: bool = False,
        **kwargs: Any,  # string keys cannot become addresses
    ) -> Union[AddressValueMapping, list[ImmutableMemory]]:

        if kwargs:
            raise KeyError('cannot convert kwargs.keys() into addresses')

        if isinstance(data, ImmutableMemory):
            return self.write_backup(0, data, clear=clear)
        else:
            backups: AddressValueMapping
            peek = self.peek
            if hasattr(data, 'keys') and callable(getattr(data, 'keys')):
                data = _cast(AddressValueMapping, data)
                backups = {address: _cast(Value, peek(address)) for address in data.keys()}
            else:
                data = _cast(Iterable[tuple[Address, Value]], data)
                backups = {address: _cast(Value, peek(address)) for address, _ in data}
            return backups

    def update_restore(
        self,
        backups: Union[AddressValueMapping, list[ImmutableMemory]],
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

            block_start, _ = blocks[0]
            previous_endex = block_start - 1  # before first start

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
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[OptionalValue]:

        if endex is None or endex is Ellipsis:
            if pattern is not None:
                if isinstance(pattern, Value):
                    pattern = bytearray((_cast(Value, pattern),))
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
            endex = _cast(Address, endex)
            if start < endex:
                values = self.values(start=start, endex=Ellipsis, pattern=pattern)
                yield from _islice(values, (endex - start))

    def view(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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

        bound_start = self._bound_start
        if bound_start is not None and endex <= bound_start:
            return

        bound_endex = self._bound_endex
        if bound_endex is not None and bound_endex <= start:
            return

        if data_is_immutable_memory:
            data = _cast(ImmutableMemory, data)
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

                if bound_start is not None and block_endex <= bound_start:
                    continue
                if bound_endex is not None and bound_endex <= block_start:
                    break

                block_data = bytearray(block_data)  # clone

                # Bound before memory
                if bound_start is not None and block_start < bound_start:
                    offset = bound_start - block_start
                    block_start += offset
                    del block_data[:offset]

                # Bound after memory
                if bound_endex is not None and bound_endex < block_endex:
                    offset = block_endex - bound_endex
                    block_endex -= offset
                    del block_data[(block_endex - block_start):]

                self._place(block_start, block_data, False)  # write
        else:
            data = _cast(bytearray, data)

            # Bound before memory
            if bound_start is not None and start < bound_start:
                offset = bound_start - start
                size -= offset
                start += offset
                del data[:offset]

            # Bound after memory
            if bound_endex is not None and bound_endex < endex:
                offset = endex - bound_endex
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
        data: Union[AnyItems, ImmutableMemory],
        clear: bool = False,
    ) -> list[ImmutableMemory]:

        backups: list[ImmutableMemory]
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


# noinspection PyPep8Naming
class bytesparse(Memory, MutableBytesparse):
    __doc__ = MutableBytesparse.__doc__

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
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ):

        super().__init__(start=start, endex=endex)

        data = bytearray(*args)
        if data:
            if start is None:
                start = 0

            if endex is not None:
                if endex <= start:
                    return

                del data[(endex - start):]

            self._blocks.append((start, data))

    def __setitem__(
        self,
        key: Union[Address, slice],
        value: Union[AnyBytes, Value, None],
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

        address = address.__index__()

        if address < 0:
            address = self.endex + address
            if address < 0:
                raise IndexError('index out of range')

        return address

    def _rectify_span(
        self,
        start: OptionalAddress,
        endex: OptionalAddress,
    ) -> OpenInterval:

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
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:

        address = self._rectify_address(address)
        return super().block_span(address)

    def blocks(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[tuple[Address, memoryview]]:

        start, endex = self._rectify_span(start, endex)
        yield from super().blocks(start=start, endex=endex)

    def bound(
        self,
        start: OptionalAddress,
        endex: OptionalAddress,
    ) -> ClosedInterval:

        start, endex = self._rectify_span(start, endex)
        return super().bound(start=start, endex=endex)

    def clear(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().clear(start=start, endex=endex)

    def clear_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().clear_backup(start=start, endex=endex)

    def count(  # type: ignore override
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> int:

        start, endex = self._rectify_span(start, endex)
        return super().count(item, start=start, endex=endex)

    def crop(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().crop(start=start, endex=endex)

    def crop_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> tuple[Union[ImmutableMemory, None], Union[ImmutableMemory, None]]:

        start, endex = self._rectify_span(start, endex)
        return super().crop_backup(start=start, endex=endex)

    def cut(  # type: ignore override
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        bound: bool = True,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().cut(start=start, endex=endex)

    def delete(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().delete(start=start, endex=endex)

    def delete_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().delete_backup(start=start, endex=endex)

    def equal_span(
        self,
        address: Address,
    ) -> tuple[OptionalAddress, OptionalAddress, OptionalValue]:

        address = self._rectify_address(address)
        return super().equal_span(address)

    def extract(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: Union[ByteString, Value, None] = None,
        step: OptionalAddress = None,
        bound: bool = True,
    ) -> Memory:

        start, endex = self._rectify_span(start, endex)
        return super().extract(start=start, endex=endex, pattern=pattern, step=step, bound=bound)

    def fill(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().fill(start=start, endex=endex, pattern=pattern)

    def fill_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> ImmutableMemory:

        start, endex = self._rectify_span(start, endex)
        return super().fill_backup(start=start, endex=endex)

    def find(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().find(item, start=start, endex=endex)

    def flood(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        pattern: AnyItems = 0,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().flood(start=start, endex=endex, pattern=pattern)

    def flood_backup(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> list[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        return super().flood_backup(start=start, endex=endex)

    @classmethod
    def from_blocks(
        cls,
        blocks: BlockSequence,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
        memory2._bound_start = memory1._bound_start
        memory2._bound_endex = memory1._bound_endex
        return memory2

    @classmethod
    def from_bytes(
        cls,
        data: AnyBytes,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
        memory2._bound_start = memory1._bound_start
        memory2._bound_endex = memory1._bound_endex
        return memory2

    @classmethod
    def from_memory(
        cls,
        memory: ImmutableMemory,
        offset: Address = 0,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
        memory2._bound_start = memory1._bound_start
        memory2._bound_endex = memory1._bound_endex
        return memory2

    def gaps(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[OpenInterval]:

        start, endex = self._rectify_span(start, endex)
        yield from super().gaps(start=start, endex=endex)

    def get(
        self,
        address: Address,
        default: OptionalValue = None,
    ) -> OptionalValue:

        address = self._rectify_address(address)
        return super().get(address, default=default)

    def hexdump(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
        columns: int = 16,
        addrfmt: str = '{:08X} ',
        bytefmt: str = ' {:02X}',
        headfmt: Union[str, EllipsisType, None] = None,
        charmap: Union[Mapping[int, str], None] = HUMAN_ASCII,
        emptystr: str = ' --',
        beforestr: str = ' >>',
        afterstr: str = ' <<',
        charsep: str = '  |',
        charend: str = '|',
        stream: Union[io.TextIOBase, EllipsisType, None] = Ellipsis,
    ) -> Union[str, None]:

        start, endex = self._rectify_span(start, endex)
        return super().hexdump(
            start=start,
            endex=endex,
            columns=columns,
            addrfmt=addrfmt,
            bytefmt=bytefmt,
            headfmt=headfmt,
            charmap=charmap,
            emptystr=emptystr,
            beforestr=beforestr,
            afterstr=afterstr,
            charsep=charsep,
            charend=charend,
            stream=stream,
        )

    def index(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().index(item, start=start, endex=endex)

    def insert(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> None:

        address = self._rectify_address(address)
        super().insert(address, data)

    def insert_backup(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
    ) -> tuple[Address, ImmutableMemory]:

        address = self._rectify_address(address)
        return super().insert_backup(address, data)

    def intervals(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Iterator[ClosedInterval]:

        start, endex = self._rectify_span(start, endex)
        yield from super().intervals(start=start, endex=endex)

    def items(
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[tuple[Address, OptionalValue]]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        endex = _cast(OptionalAddress, endex)
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().items(start=start, endex=endex, pattern=pattern)

    def keys(
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
    ) -> Iterator[Address]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        endex = _cast(OptionalAddress, endex)
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().keys(start=start, endex=endex)

    def peek(
        self,
        address: Address,
    ) -> OptionalValue:

        address = self._rectify_address(address)
        return super().peek(address)

    def poke(
        self,
        address: Address,
        item: Union[AnyBytes, Value, None],
    ) -> None:

        address = self._rectify_address(address)
        super().poke(address, item)

    def poke_backup(
        self,
        address: Address,
    ) -> tuple[Address, OptionalValue]:

        address = self._rectify_address(address)
        return super().poke_backup(address)

    def pop(
        self,
        address: OptionalAddress = None,
        default: OptionalValue = None,
    ) -> OptionalValue:

        if address is not None:
            address = self._rectify_address(address)
        return super().pop(address=address, default=default)

    def pop_backup(
        self,
        address: OptionalAddress = None,
    ) -> tuple[Address, OptionalValue]:

        if address is not None:
            address = self._rectify_address(address)
        return super().pop_backup(address=address)

    def read(
        self,
        address: Address,
        size: Address,
    ) -> memoryview:

        address = self._rectify_address(address)
        return super().read(address, size)

    def readinto(
        self,
        address: Address,
        buffer: Union[bytearray, memoryview],
    ) -> int:

        address = self._rectify_address(address)
        return super().readinto(address, buffer)

    def remove(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> None:

        start, endex = self._rectify_span(start, endex)
        super().remove(item, start=start, endex=endex)

    def remove_backup(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
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
    ) -> tuple[Address, ImmutableMemory]:

        address = self._rectify_address(address)
        return super().reserve_backup(address, size)

    def rfind(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().rfind(item, start=start, endex=endex)

    def rindex(
        self,
        item: AnyItems,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> Address:

        start, endex = self._rectify_span(start, endex)
        return super().rindex(item, start=start, endex=endex)

    def rvalues(
        self,
        start: Union[Address, EllipsisType, None] = None,
        endex: OptionalAddress = None,
        pattern: Union[AnyBytes, Value, None] = None,
    ) -> Iterator[OptionalValue]:

        start_ = start  # backup
        if start is Ellipsis:
            start = None
        start = _cast(OptionalAddress, start)
        start, endex = self._rectify_span(start, endex)
        if start_ is Ellipsis:
            start = start_  # restore
        yield from super().rvalues(start=start, endex=endex, pattern=pattern)

    def setdefault(  # type: ignore override
        self,
        address: Address,
        default: OptionalValue = None,
    ) -> OptionalValue:

        address = self._rectify_address(address)
        return super().setdefault(address, default=default)

    def setdefault_backup(
        self,
        address: Address,
    ) -> tuple[Address, OptionalValue]:

        address = self._rectify_address(address)
        return super().setdefault_backup(address)

    def shift(
        self,
        offset: Address,
    ) -> None:

        if self._bound_start is None and offset < 0:
            blocks = self._blocks
            if blocks:
                block_start = blocks[0][0]
                if block_start + offset < 0:
                    raise ValueError('negative offseted start')

        super().shift(offset)

    def shift_backup(
        self,
        offset: Address,
    ) -> tuple[Address, ImmutableMemory]:

        if self._bound_start is None and offset < 0:
            blocks = self._blocks
            if blocks:
                block_start = blocks[0][0]
                if block_start + offset < 0:
                    raise ValueError('negative offseted start')

        return super().shift_backup(offset)

    @ImmutableMemory.bound_endex.getter
    def bound_endex(
        self,
    ) -> OptionalAddress:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._bound_endex

    @bound_endex.setter
    def bound_endex(
        self,
        bound_endex: OptionalAddress,
    ) -> None:

        if bound_endex is not None and bound_endex < 0:
            raise ValueError('negative endex')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        bound_start = self._bound_start
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            self._bound_start = bound_start = bound_endex

        self._bound_endex = bound_endex
        if bound_endex is not None:
            self.crop(start=bound_start, endex=bound_endex)

    @ImmutableMemory.bound_span.getter
    def bound_span(
        self,
    ) -> OpenInterval:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._bound_start, self._bound_endex

    @bound_span.setter
    def bound_span(
        self,
        bound_span: Union[OpenInterval, None],
    ) -> None:

        if bound_span is None:
            bound_span = (None, None)
        bound_start, bound_endex = bound_span
        if bound_start is not None and bound_start < 0:
            raise ValueError('negative start')
        if bound_endex is not None and bound_endex < 0:
            raise ValueError('negative endex')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        bound_start, bound_endex = bound_span
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            bound_endex = bound_start

        self._bound_start = bound_start
        self._bound_endex = bound_endex
        if bound_start is not None or bound_endex is not None:
            self.crop(start=bound_start, endex=bound_endex)

    @ImmutableMemory.bound_start.getter
    def bound_start(
        self,
    ) -> OptionalAddress:

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        return self._bound_start

    @bound_start.setter
    def bound_start(
        self,
        bound_start: OptionalAddress,
    ) -> None:

        if bound_start is not None and bound_start < 0:
            raise ValueError('negative start')

        # Copy-pasted from Memory, because I cannot figure out how to override properties
        bound_endex = self._bound_endex
        if bound_start is not None and bound_endex is not None and bound_endex < bound_start:
            self._bound_endex = bound_endex = bound_start

        self._bound_start = bound_start
        if bound_start is not None:
            self.crop(start=bound_start, endex=bound_endex)

    def validate(
        self,
    ) -> None:

        for block_start, _ in self._blocks:
            if block_start < 0:
                raise ValueError('negative block start')

        super().validate()

    def values(
        self,
        start: OptionalAddress = None,
        endex: Union[Address, EllipsisType, None] = None,
        pattern: Union[ByteString, Value, None] = None,
    ) -> Iterator[OptionalValue]:

        endex_ = endex  # backup
        if endex is Ellipsis:
            endex = None
        endex = _cast(OptionalAddress, endex)
        start, endex = self._rectify_span(start, endex)
        if endex_ is Ellipsis:
            endex = endex_  # restore
        yield from super().values(start=start, endex=endex, pattern=pattern)

    def view(
        self,
        start: OptionalAddress = None,
        endex: OptionalAddress = None,
    ) -> memoryview:

        start, endex = self._rectify_span(start, endex)
        return super().view(start=start, endex=endex)

    def write(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
        clear: bool = False,
    ) -> None:

        address = self._rectify_address(address)
        super().write(address, data, clear=clear)

    def write_backup(
        self,
        address: Address,
        data: Union[AnyItems, ImmutableMemory],
        clear: bool = False,
    ) -> list[ImmutableMemory]:

        address = self._rectify_address(address)
        return super().write_backup(address, data, clear=clear)
