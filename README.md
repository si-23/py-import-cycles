py-import-cycles
================

Detect import cycles in Python projects.

It:

* walks over given packages,
* collects (file-based) Python modules,
* extracts import statements via `ast` and
* computes cycles.

It is conceived for having an indication whether Python packages may have structural weak points.

`py-import-cycles` does not take any Python module finder or loader mechanisms into account. 

Installation
------------

The py-import-cycles package is available on PyPI: `python3 -m pip install --user py-import-cycles`

Usage
-----

* `python3 -m py_import_cycles --version`
* `python3 -m py_import_cycles --help`
* `python3 -m py_import_cycles --packages /path/to/project/package`
