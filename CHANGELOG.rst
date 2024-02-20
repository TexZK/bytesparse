Changelog
=========

0.1.0 (2024-02-22)
------------------

* Improved documentation.
* Version number deserved something more stable.


0.0.8 (2024-01-21)
------------------

* Added ``chop`` method.
* Minor fixes.


0.0.7 (2023-12-10)
------------------

* Added support for Python 3.12.
* Added ``hexdump`` method.
* Added ``bytesparse.io`` package.
* Added ``bytesparse.MemoryIO`` as a stream wrapper for ``bytesparse.Memory``.


0.0.6 (2023-02-18)
------------------

* Added support to Python 3.11, removed 3.6.
* Added some minor features.
* Improved documentation.
* Improved testing.
* Improved repository layout (``pyproject.toml``).
* Minor fixes.


0.0.5 (2022-02-22)
------------------

* Added ``bytesparse`` class, closer to ``bytearray`` than ``Memory``.
* Added missing abstract and ported methods.
* Added cut feature.
* Added more helper methods.
* Fixed values iteration.
* Improved extraction performance.
* Improved testing.


0.0.4 (2022-01-09)
------------------

* Refactored current implementation as the ``inplace`` sub-module.
* Added abstract base classes and base types into the ``base`` sub-module.
* Removed experimental backup feature.
* Added dedicated methods to backup/restore mutated state.
* Fixed some write/insert bugs.
* Fixed some trim/bound bugs.
* Methods sorted by name.
* Removed useless functions.


0.0.3 (2022-01-03)
------------------

* Using explicit factory methods instead of constructor arguments.
* Added block collapsing helper function.
* Minor fixes.
* Improved test suite.


0.0.2 (2021-12-27)
------------------

* Cython implementation moved to its own ``cbytesparse`` Python package.
* Remote testing moved to GitHub Actions.


0.0.1 (2021-04-04)
------------------

* First release on PyPI.
