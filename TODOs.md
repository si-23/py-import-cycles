TODOs
=====

1. improve logging:
	* verbose: log every step
	* debug: only log steps which are useful for dev
2. Check shebang

Import edges Python executes but the tool cannot see yet
--------------------------------------------------------

3. `from pkg import *` also imports the submodules listed in `pkg.__all__`; add edges to them
   when `__all__` is a literal.
4. `importlib.import_module("a.b")` and `__import__("a.b")`; resolve literal string arguments.
5. A module-level `__getattr__` (PEP 562) may import modules lazily on
   `from pkg import name`; this needs following the code inside `__getattr__`.
6. Imports run by plugin registries (entry points), `exec`, `runpy`, or `__path__` and
   `sys.path` manipulation; out of reach for static analysis.
7. Cycles through code that is not scanned: C extensions, installed third-party packages,
   folders not given to `--packages`.
8. The same module name in two scanned folders: only one file is kept and the imports of the
   other are lost; Python loads one of them as well, depending on `sys.path`.
