py-import-cycles
================

Detect import cycles in Python projects.

It:

* walks over the given packages or files,
* collects (file-based) Python modules,
* extracts import statements via `ast` and
* computes cycles.

It indicates whether Python packages have structural weak points. Python's module finders and
loaders are not taken into account.

Installation
------------

The py-import-cycles package is available on PyPI: `python3 -m pip install --user py-import-cycles`

Usage
-----

* `py_import_cycles --packages /path/to/project/package`
* `py_import_cycles --files /path/to/repo::pkg/module.py`
* `py_import_cycles --help` for all options

`python3 -m py_import_cycles` works as well.

### Strategies

Choose the cycle detection algorithm with `--strategy`:

* `dfs` (default): one cycle per start module, found by depth-first search (fast)
* `tarjan`: the strongly connected components with more than one module
* `johnson`: all simple cycles; this may take very long, limit the cycle length with
  `--length-bound`

### Ignoring imports

Single import statements can be ignored via `# py-import-cycles: ignore`:

```python
import a  # py-import-cycles: ignore

# py-import-cycles: ignore
import b
```

### Outputs

* The number of found cycles is printed to stderr, the cycles themselves with `--verbose`.
* A log file is written to `~/.local/py-import-cycles/outputs/` (see `--outputs-folder` and
  `--outputs-filename`).
* `--graph` writes the cycles as Graphviz file to the same folder and opens it.
* `--sarif FILE` writes the cycles as SARIF to `FILE`, or to stdout if `FILE` is `-`.

The exit status is 1 if more cycles than `--threshold` (default: 0) are found, 0 otherwise.
