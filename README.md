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

### What counts as an import

py-import-cycles is a strict linter: it reports every circular import Python raises at import
time, as well as import cycles that only work because of the order of statements.

* Every import statement counts, including imports inside functions and under
  `if TYPE_CHECKING:`.
* `import a.b.c` and `from a.b import c` depend on `a/__init__.py` and `a/b/__init__.py`, which
  Python runs first, and on `a.b.c` if it is a module.
* A module's own parent packages are already imported when it runs. They count only when the
  module reads a name from them (`from . import NAME`, `from pkg import *`) or imports them
  plainly (`import pkg`).
* A relative import counts like its absolute spelling.
* Namespace packages contain no code and never take part in a cycle.

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

A reason may follow the keyword, e.g. `# py-import-cycles: ignore - plugin API`.

### Outputs

* The number of found cycles is printed to stderr, the cycles themselves with `--verbose`.
* A log file is written to `~/.local/py-import-cycles/outputs/` (see `--outputs-folder` and
  `--outputs-filename`).
* `--graph` writes the cycles as Graphviz file to the same folder and opens it.
* `--sarif FILE` writes the cycles as SARIF to `FILE`, or to stdout if `FILE` is `-`.

The exit status is 1 if more cycles than `--threshold` (default: 0) are found, 0 otherwise.
