Changelog
=========

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
