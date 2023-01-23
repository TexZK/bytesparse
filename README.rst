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
constsis in a virtual addressing space where sparse `chunks` of data can be
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

The Python implementation can also exploit the capabilities of its powerful
``int`` type, so that a virtually infinite addressing space can be used,
even with negative addresses!

Data chunks are stored as common mutable ``bytearray`` objects, whose size is
limited by the Python engine (e.g. that of ``size_t``).

More details can be found within ``bytesparse.inplace``.


Cython implementation
=====================

The library also provides an experimental `Cython` implementation. It tries to
mimic the same algorithms of the Python implementation, while exploiting the
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
