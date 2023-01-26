********
Overview
********

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |gh_actions|
        | |codecov|
    * - package
      - | |version| |wheel|
        | |supported-versions|
        | |supported-implementations|

.. |docs| image:: https://readthedocs.org/projects/bytesparse/badge/?style=flat
    :target: https://readthedocs.org/projects/bytesparse
    :alt: Documentation Status

.. |gh_actions| image:: https://github.com/TexZK/bytesparse/workflows/CI/badge.svg
    :alt: GitHub Actions Status
    :target: https://github.com/TexZK/bytesparse

.. |codecov| image:: https://codecov.io/gh/TexZK/bytesparse/branch/main/graphs/badge.svg?branch=main
    :alt: Coverage Status
    :target: https://codecov.io/github/TexZK/bytesparse

.. |version| image:: https://img.shields.io/pypi/v/bytesparse.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/bytesparse/

.. |wheel| image:: https://img.shields.io/pypi/wheel/bytesparse.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/bytesparse/

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/bytesparse.svg
    :alt: Supported versions
    :target: https://pypi.org/project/bytesparse/

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/bytesparse.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/bytesparse/

.. end-badges


Library to handle sparse bytes within a virtual memory space.

* Free software: BSD 2-Clause License


Objectives
==========

This library aims to provide utilities to work with a `virtual memory`, which
consists of a virtual addressing space where sparse `chunks` of data can be
stored.

In order to be easy to use, its interface should be close to that of a
``bytearray``, which is the closest pythonic way to store dynamic data.
The main downside of a ``bytearray`` is that it requires a contiguous data
allocation starting from address 0. This is not good when sparse data have to
be stored, such as when emulating the addressing space of a generic
microcontroller.

The main idea is to provide a ``bytearray``-like class with the possibility to
internally hold the sparse `blocks` of data.
A `block` is ideally a tuple ``(start, data)`` where `start` is the start
address and `data` is the container of data items (e.g. ``bytearray``).
The length of the block is ``len(data)``.
Those blocks are usually not overlapping nor contiguous, and sorted by start
address.


Python implementation
=====================

This library provides a pure Python implementation, for maximum compatibility.

Its implementation should be correct and robust, whilst trying to be as fast
as common sense suggests. This means that the code should be reasonably
optimized for general use, while still providing features that are less likely
to be used, yet compatible with the existing Python API (e.g. ``bytearray`` or
``dict``).

The Python implementation can also leverage the capabilities of its powerful
``int`` type, so that a virtually infinite addressing space can be used,
even with negative addresses!

Data chunks are stored as common mutable ``bytearray`` objects, whose size is
limited by the Python engine (i.e. that of ``size_t``).

The ``bytesparse`` package provides the following virtual memory types:

* ``bytesparse.Memory``, a generic virtual memory with infinite address range.
* ``bytesparse.bytesparse``, a subclass behaving more like ``bytearray``.

All the implementations inherit the behavior of
``collections.abc.MutableSequence`` and ``collections.abc.MutableMapping``.
Please refer to `the collections.abc reference manual
<https://docs.python.org/3/library/collections.abc.html>`_ for more information
about the interface API methods and capabilities.


Examples
========

Here's a quick usage example of ``bytesparse`` objects:

>>> from bytesparse import Memory
>>> from bytesparse import bytesparse
>>> # ----------------------------------------------------------------
>>> m = bytesparse(b'Hello, World!')  # creates from bytes
>>> len(m)  # total length
13
>>> str(m)  # string representation, with bounds and data blocks
"<[[0, b'Hello, World!']]>"
>>> bytes(m)  # export as bytes
b'Hello, World!'
>>> m.to_bytes()  # export the whole range as bytes
b'Hello, World!'
>>> # ----------------------------------------------------------------
>>> m.extend(b'!!')  # more emphasis!!!
>>> bytes(m)
b'Hello, World!!!'
>>> # ----------------------------------------------------------------
>>> i = m.index(b',')  # gets the address of the comma
>>> m[:i] = b'Ciao'  # replaces 'Hello' with 'Ciao'
>>> bytes(m)
b'Ciao, World!!!'
>>> # ----------------------------------------------------------------
>>> i = m.index(b',')  # gets the address of the comma
>>> m.insert(i, b'ne')  # inserts 'ne' to make 'Ciaone' ("big ciao")
>>> bytes(m)
b'Ciaone, World!!!'
>>> # ----------------------------------------------------------------
>>> i = m.index(b',')  # gets the address of the comma
>>> m[(i - 2):i] = b' ciao'  # makes 'Ciaone' --> 'Ciao ciao'
>>> bytes(m)
b'Ciao ciao, World!!!'
>>> # ----------------------------------------------------------------
>>> m.pop()  # less emphasis --> 33 == ord('!')
33
>>> bytes(m)
b'Ciao ciao, World!!'
>>> # ----------------------------------------------------------------
>>> del m[m.index(b'l')]  # makes 'World' --> 'Word'
>>> bytes(m)
b'Ciao ciao, Word!!'
>>> # ----------------------------------------------------------------
>>> m.popitem()  # less emphasis --> pops 33 (== '!') at address 16
(16, 33)
>>> bytes(m)
b'Ciao ciao, Word!'
>>> # ----------------------------------------------------------------
>>> m.remove(b' ciao')  # self-explanatory
>>> bytes(m)
b'Ciao, Word!'
>>> # ----------------------------------------------------------------
>>> i = m.index(b',')  # gets the address of the comma
>>> m.clear(start=i, endex=(i + 2))  # makes empty space between the words
>>> m.to_blocks()  # exports as data block list
[[0, b'Ciao'], [6, b'Word!']]
>>> m.contiguous  # multiple data blocks (emptiness inbetween)
False
>>> m.content_parts  # two data blocks
2
>>> m.content_size  # excluding emptiness
9
>>> len(m)  # including emptiness
11
>>> # ----------------------------------------------------------------
>>> m.flood(pattern=b'.')  # replaces emptiness with dots
>>> bytes(m)
b'Ciao..Word!'
>>> m[-2]  # 100 == ord('d')
100
>>> # ----------------------------------------------------------------
>>> m.peek(-2)  # 100 == ord('d')
100
>>> m.poke(-2, b'k')  # makes 'Word' --> 'Work'
>>> bytes(m)
b'Ciao..Work!'
>>> # ----------------------------------------------------------------
>>> m.crop(start=m.index(b'W'))  # keeps 'Work!'
>>> m.to_blocks()
[[6, b'Work!']]
>>> m.span  # address range of the whole memory
(6, 11)
>>> m.start, m.endex  # same as above
(6, 11)
>>> # ----------------------------------------------------------------
>>> m.bound_span = (2, 10)  # sets memory address bounds
>>> str(m)
"<2, [[6, b'Work']], 10>"
>>> m.to_blocks()
[[6, b'Work']]
>>> # ----------------------------------------------------------------
>>> m.shift(-6)  # shift to the left; NOTE: address bounds will cut 2 bytes!
>>> m.to_blocks()
[[2, b'rk']]
>>> str(m)
"<2, [[2, b'rk']], 10>"
>>> # ----------------------------------------------------------------
>>> a = bytesparse(b'Ma')
>>> a.write(0, m)  # writes [2, b'rk'] --> 'Mark'
>>> a.to_blocks()
[[0, b'Mark']]
>>> # ----------------------------------------------------------------
>>> b = Memory.from_bytes(b'ing', offset=4)
>>> b.to_blocks()
[[4, b'ing']]
>>> # ----------------------------------------------------------------
>>> a.write(0, b)  # writes [4, b'ing'] --> 'Marking'
>>> a.to_blocks()
[[0, b'Marking']]
>>> # ----------------------------------------------------------------
>>> a.reserve(4, 2)  # inserts 2 empty bytes after 'Mark'
>>> a.to_blocks()
[[0, b'Mark'], [6, b'ing']]
>>> # ----------------------------------------------------------------
>>> a.write(4, b'et')  # --> 'Marketing'
>>> a.to_blocks()
[[0, b'Marketing']]
>>> # ----------------------------------------------------------------
>>> a.fill(1, -1, b'*')  # fills asterisks between the first and last letters
>>> a.to_blocks()
[[0, b'M*******g']]
>>> # ----------------------------------------------------------------
>>> v = a.view(1, -1)  # creates a memory view spanning the asterisks
>>> v[::2] = b'1234'  # replaces even asterisks with numbers
>>> a.to_blocks()
[[0, b'M1*2*3*4g']]
>>> a.count(b'*')  # counts all the asterisks
3
>>> del v  # release memory view
>>> # ----------------------------------------------------------------
>>> c = a.copy()  # creates a (deep) copy
>>> c == a
True
>>> c is a
False
>>> # ----------------------------------------------------------------
>>> del a[a.index(b'*')::2]  # deletes every other byte from the first asterisk
>>> a.to_blocks()
[[0, b'M1234']]
>>> # ----------------------------------------------------------------
>>> a.shift(3)  # move away from the trivial 0 index
>>> a.to_blocks()
[[3, b'M1234']]
>>> list(a.keys())
[3, 4, 5, 6, 7]
>>> list(a.values())
[77, 49, 50, 51, 52]
>>> list(a.items())
[(3, 77), (4, 49), (5, 50), (6, 51), (7, 52)]
>>> # ----------------------------------------------------------------
>>> c.to_blocks()  # remind
[[0, b'M1*2*3*4g']]
>>> c[2::2] = None  # clears (empties) every other byte from the first asterisk
>>> c.to_blocks()
[[0, b'M1'], [3, b'2'], [5, b'3'], [7, b'4']]
>>> list(c.intervals())  # list all the block ranges
[(0, 2), (3, 4), (5, 6), (7, 8)]
>>> list(c.gaps())  # list all the empty ranges
[(None, 0), (2, 3), (4, 5), (6, 7), (8, None)]
>>> # ----------------------------------------------------------------
>>> c.flood(pattern=b'xy')  # fill empty spaces
>>> c.to_blocks()
[[0, b'M1x2x3x4']]
>>> # ----------------------------------------------------------------
>>> t = c.cut(c.index(b'1'), c.index(b'3'))  # cut an inner slice
>>> t.to_blocks()
[[1, b'1x2x']]
>>> c.to_blocks()
[[0, b'M'], [5, b'3x4']]
>>> t.bound_span  # address bounds of the slice (automatically activated)
(1, 5)
>>> # ----------------------------------------------------------------
>>> k = bytesparse.from_blocks([[4, b'ABC'], [9, b'xy']], start=2, endex=15)  # bounded
>>> str(k)  # show summary
"<2, [[4, b'ABC'], [9, b'xy']], 15>"
>>> k.bound_span  # defined at creation
(2, 15)
>>> k.span  # superseded by bounds
(2, 15)
>>> k.content_span  # actual content span (min/max addresses)
(4, 11)
>>> len(k)  # superseded by bounds
13
>>> k.content_size  # actual content size
5
>>> # ----------------------------------------------------------------
>>> k.flood(pattern=b'.')  # floods between span
>>> k.to_blocks()
[[2, b'..ABC..xy....']]


Cython implementation
=====================

The library also provides an experimental `Cython` implementation. It tries to
mimic the same algorithms of the Python implementation, while leveraging the
speedup of compiled `C` code.

Please refer to the ``cbytesparse`` Python package for more details.


Background
==========

This library started as a spin-off of ``hexrec.blocks.Memory``.
That is based on a simple Python implementation using immutable objects (i.e.
``tuple`` and ``bytes``). While good enough to handle common hexadecimal files,
it is totally unsuited for dynamic/interactive environments, such as emulators,
IDEs, data editors, and so on.
Instead, ``bytesparse`` should be more flexible and faster, hopefully
suitable for generic usage.

While developing the Python implementation, why not also jump on the Cython
bandwagon, which permits even faster algorithms? Moreover, Cython itself is
an interesting intermediate language, which brings to the speed of C, whilst
being close enough to Python for the like.

Too bad, one great downside is that debugging Cython-compiled code is quite an
hassle -- that is why I debugged it in a crude way I cannot even mention, and
the reason why there must be dozens of bugs hidden around there, despite the
test suite :-) Moreover, the Cython implementation is still experimental, with
some features yet to be polished (e.g. reference counting).


Documentation
=============

For the full documentation, please refer to:

https://bytesparse.readthedocs.io/


Installation
============

From PyPI (might not be the latest version found on *github*):

.. code-block:: sh

    $ pip install bytesparse

From the source code root directory:

.. code-block:: sh

    $ pip install .


Development
===========

To run the all the tests:

.. code-block:: sh

    $ pip install tox
    $ tox
