********
Overview
********

WORK IN PROGRESS
================

This repository was just created.
Most (if not all) of the documentation is yet to be done.
Links and other cloud/automated stuff are actually not working right now.

I'm willing to provide at least the minimal support as soon as possible.

Minimal to-do list:

#. Setup and check basic `tox` environments
#. Setup cloud/automated stuff
#. Create some minimal documentation within this readme file
#. Add docstrings at least to the Python implementation
#. Add docstrings to the Cython implementation
#. Implement missing tests
#. Improve existing implementation


.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |appveyor| |requires|
        | |codecov|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|

.. |docs| image:: https://readthedocs.org/projects/bytesparse/badge/?style=flat
    :target: https://readthedocs.org/projects/bytesparse
    :alt: Documentation Status

.. |travis| image:: https://api.travis-ci.org/TexZK/bytesparse.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/TexZK/bytesparse

.. |appveyor| image:: https://ci.appveyor.com/api/projects/status/github/TexZK/bytesparse?branch=master&svg=true
    :alt: AppVeyor Build Status
    :target: https://ci.appveyor.com/project/TexZK/bytesparse

.. |requires| image:: https://requires.io/github/TexZK/bytesparse/requirements.svg?branch=master
    :alt: Requirements Status
    :target: https://requires.io/github/TexZK/bytesparse/requirements/?branch=master

.. |codecov| image:: https://codecov.io/gh/TexZK/bytesparse/branch/master/graphs/badge.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/TexZK/bytesparse

.. |version| image:: https://img.shields.io/pypi/v/bytesparse.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/bytesparse/

.. |commits-since| image:: https://img.shields.io/github/commits-since/TexZK/bytesparse/v0.0.1.svg
    :alt: Commits since latest release
    :target: https://github.com/TexZK/bytesparse/compare/v0.0.1...master

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


Documentation
=============

For the full documentation, please refer to:

https://bytesparse.readthedocs.io/


Installation
============

From PIP (might not be the latest version found on *github*):

.. code-block:: sh

    $ pip install bytesparse

From source:

.. code-block:: sh

    $ python setup.py install


Development
===========

To run the all the tests:

.. code-block:: sh

    $ tox --skip-missing-interpreters


Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - .. code-block:: sh

            $ set PYTEST_ADDOPTS=--cov-append
            $ tox

    - - Other
      - .. code-block:: sh

            $ PYTEST_ADDOPTS=--cov-append tox
