py-import-cycles
================

Detect import cycles in Python projects.

This tool:

* walks over given packages,
* collects (file-based) Python modules,
* extracts import statements and
* computes cycles.

The import statements are collected from the outside via `ast` and this tool does not take any
Python module finder or loader mechanisms into account. It is conceived for having an indication
whether Python packages may have structural weak points.

Installation
------------

The py-import-cycles package is available on PyPI: `python3 -m pip install --user py-import-cycles`

Usage
-----

* `python3 -m py_import_cycles --version`
* `python3 -m py_import_cycles --help`
* `python3 -m py_import_cycles --packages /path/to/project/package`
