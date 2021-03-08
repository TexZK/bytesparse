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

Block = List[Any]  # [Address, Data]
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


class Memory:

    def __init__(
        self: 'Memory',
        memory: Optional['Memory'] = None,
        data: Optional[AnyBytes] = None,
        offset: Optional[Address] = None,
        blocks: Optional[BlockList] = None,
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        copy: bool = True,
        validate: bool = True,
    ):
        if start is not None:
            start = Address(start)
        if endex is not None:
            endex = Address(endex)
        if start is not None and endex is not None and endex < start:
            endex = start
        offset = 0 if offset is None else Address(offset)

        if (memory is not None) + (data is not None) + (blocks is not None) > 1:
            raise ValueError('only one of [memory, data, blocks] is allowed')

        if memory is not None:
            if copy:
                blocks = [[block_start + offset, bytearray(block_data)]
                          for block_start, block_data in memory._blocks]
            else:
                if offset:
                    blocks = [[block_start + offset, block_data]
                              for block_start, block_data in memory._blocks]
                else:
                    blocks = memory._blocks

        elif data is not None:
            if copy:
                data = bytearray(data)

            if data:
                blocks = [[offset, data]]
            else:
                blocks = []

        elif blocks:
            if copy:
                blocks = [[block_start + offset, bytearray(block_data)]
                          for block_start, block_data in blocks]
            elif offset:
                blocks = [[block_start + offset, block_data]
                          for block_start, block_data in blocks]
        else:
            blocks = []

        self._blocks: BlockList = blocks
        self._trim_start: Optional[Address] = start
        self._trim_endex: Optional[Address] = endex

        self._crop(start, endex, None)

        if validate:
            self.validate()

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

        if self.content_size < STR_MAX_CONTENT_SIZE:
            return repr(self._blocks)
        else:
            return repr(self)

    def __bool__(
        self: 'Memory',
    ) -> bool:

        return any(block_data for _, block_data in self._blocks)

    def __eq__(
        self: 'Memory',
        other: Any,
    ) -> bool:

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

        yield from self.values(self.start, self.endex)

    def __reversed__(
        self: 'Memory',
    ) -> Iterator[Optional[Value]]:

        yield from self.rvalues()

    def __add__(
        self: 'Memory',
        value: Union[AnyBytes, 'Memory'],
    ) -> 'Memory':

        memory = type(self)(memory=self, validate=False)
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
            memory = type(self)(memory=self, validate=False)

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
            memory = type(self)(memory=self, validate=False)

            for time in range(times - 1):
                self.write(offset, memory)
                offset += size
        else:
            blocks.clear()
        return self

    def __len__(
        self: 'Memory',
    ) -> Address:

        return self.endex - self.start

    def ofind(
        self: 'Memory',
        item: Union[AnyBytes, Value],
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
    ) -> Optional[Address]:

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

        return any(item in block_data for _, block_data in self._blocks)

    def count(
        self: 'Memory',
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

    def __getitem__(
        self: 'Memory',
        key: Union[Address, slice],
    ) -> Any:

        if isinstance(key, slice):
            start = key.start
            endex = key.stop
            start = self.start if start is None else start
            endex = self.endex if endex is None else endex
            step = key.step

            if isinstance(step, Value):
                if step is None or step >= 1:
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
    ) -> None:

        if offset < 0:
            raise ValueError('negative extension offset')
        self.write(self.content_endex + offset, items)

    def pop(
        self: 'Memory',
        address: Optional[Address] = None,
    ) -> Optional[Value]:

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

        message = 'non-contiguous data within range'
        blocks = self._blocks

        if not blocks:
            start = self._trim_start
            endex = self._trim_endex
            if start is not None and endex is not None and start < endex - 1:
                raise ValueError(message)
            return bytearray()

        elif len(blocks) == 1:
            start = self._trim_start
            if start is not None:
                if start != blocks[0][0]:
                    raise ValueError(message)

            endex = self._trim_endex
            if endex is not None:
                block_start, block_data = blocks[-1]
                if endex != block_start + len(block_data):
                    raise ValueError(message)

            return blocks[0][1]

        else:
            raise ValueError(message)

    def __bytes__(
        self: 'Memory',
    ) -> bytes:

        return bytes(self._bytearray())

    def to_bytes(
        self: 'Memory',
    ) -> bytes:

        return bytes(self._bytearray())

    def to_bytearray(
        self: 'Memory',
        copy: bool = True,
    ) -> bytearray:

        block_data = self._bytearray()
        return bytearray(block_data) if copy else block_data

    def to_memoryview(
        self: 'Memory',
    ) -> memoryview:

        return memoryview(self._bytearray())

    def __copy__(
        self: 'Memory',
    ) -> 'Memory':

        return type(self)(memory=self, start=self.trim_start, endex=self.trim_endex, copy=False)

    def __deepcopy__(
        self: 'Memory',
    ) -> 'Memory':

        return type(self)(memory=self, start=self.trim_start, endex=self.trim_endex, copy=True)

    @property
    def contiguous(
        self: 'Memory',
    ) -> bool:

        try:
            self._bytearray()
            return True
        except ValueError:
            return False

    @property
    def trim_start(
        self: 'Memory',
    ) -> Optional[Address]:

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

        return self.start, self.endex

    @property
    def endin(
        self: 'Memory',
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

    @property
    def content_start(
        self: 'Memory',
    ) -> Address:

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

        return self.content_start, self.content_endex

    @property
    def content_endin(
        self: 'Memory',
    ) -> Address:

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

        return sum(len(block_data) for _, block_data in self._blocks)

    @property
    def content_parts(
        self: 'Memory',
    ) -> int:

        return len(self._blocks)

    def validate(
        self: 'Memory',
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

    def bound(
        self: 'Memory',
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
            if start is not None:
                if start > endex:
                    start = endex

        return start, endex

    def _block_index_at(
        self: 'Memory',
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
        else:
            return None

    def _block_index_start(
        self: 'Memory',
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
        else:
            return left

    def _block_index_endex(
        self: 'Memory',
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
        else:
            return right + 1

    def peek(
        self: 'Memory',
        address: Address,
    ) -> Optional[Value]:

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

        size = endex - start
        if size > 0:
            blocks = self._blocks
            block_index = self._block_index_start(start)

            # Delete final/inner part of deletion start block
            for block_index in range(block_index, len(blocks)):
                block_start, block_data = blocks[block_index]
                if start <= block_start:
                    break  # inner starts here

                block_endex = block_start + len(block_data)
                if start < block_endex:
                    if shift_after:
                        del block_data[(start - block_start):(endex - block_start)]
                    else:
                        block_data = block_data[:(start - block_start)]
                        blocks.insert(block_index, [block_start, block_data])
                    block_index += 1  # skip this from inner part
                    break
            else:
                block_index = len(blocks)

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

            self._insert(address, data, True)

            if data:
                self._crop(self._trim_start, self._trim_endex, None)

    def delete(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        backups: Optional[MemoryList] = None,
    ) -> None:

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

        self._crop(start, endex, backups)

    def write(
        self: 'Memory',
        address: Address,
        data: Union[AnyBytes, Value, 'Memory'],
        clear: bool = False,
        backups: Optional[MemoryList] = None,
    ) -> None:

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

                    self._erase(data_start, data_endex, False, True)  # insert

                else:
                    # Clear only overwritten ranges
                    for block_start, block_data in data._blocks:
                        block_start += address
                        block_endex = block_start + len(block_data)

                        if backups is not None:
                            backups.append(self.extract(block_start, block_endex))

                        self._erase(block_start, block_endex, False, True)  # insert

                for block_start, block_data in data._blocks:
                    self._insert(block_start + address, bytearray(block_data), False)

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
                    backups.append(cls(start=gap_start, endex=gap_endex, validate=False))

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
    ) -> Iterator[Address]:

        del self
        yield from _count(start)

    def values(
        self: 'Memory',
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

    def rvalues(
        self: 'Memory',
        start: Optional[Union[Address, EllipsisType]] = None,
        endex: Optional[Address] = None,
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Optional[Value]]:

        if start is None or start is Ellipsis:
            if isinstance(pattern, Value):
                pattern = (pattern,)
                pattern = bytearray(pattern)

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
        pattern: Optional[Union[AnyBytes, Value]] = None,
    ) -> Iterator[Tuple[Address, Value]]:

        yield from zip(self.keys(start), self.values(start, Ellipsis, pattern))

    def intervals(
        self: 'Memory',
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

    def gaps(
        self: 'Memory',
        start: Optional[Address] = None,
        endex: Optional[Address] = None,
        bound: bool = False,
    ) -> Iterator[OpenInterval]:

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
