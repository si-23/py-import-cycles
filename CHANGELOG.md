# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

### Changed

- Accept any whitespace after the colon of the ignore comment and a reason after it.
- Model the imports Python executes, so every circular import Python raises at import time is
  reported: an import adds edges to the parent packages it runs, a module's own parent package
  counts when the module reads a name from it or imports it plainly, and relative imports
  resolve like their absolute spelling. Namespace packages are no longer edges.

### Fixed

- Skip `__pycache__` folders instead of reporting them as namespace packages.
- Log at level INFO without `--debug`, so `--stats` reaches the log file.
- Keep an import in the first line when the last line is an ignore comment.
- Honour the ignore comment on multi-line imports of several names.
- Read source files in the encoding their coding declaration names.
- Skip files that cannot be read instead of aborting the run.
- Prefer a regular package to a module of the same name in relative imports.
- Resolve relative imports of level two or more in a package's `__init__.py`.
- Resolve imports of scanned packages named like a standard library module.
- Number the cycles and lay out and colour the graph the same way on every run.

## [0.6.0]

### Added

- Add command line option `--length-bound` for `johnson strategy`.

### Changed

- Use `strongly_connected_components` from `networkx`
- `dfs`: Exclude all cyclic rotations of a cycle
- Modernized repo & tooling

## [0.5.2]

### Fixed

- Add `uriBaseId` field to SARIF output.  It is required for relative `uri`.
- Accept utf8 namespaces to modules and file names.

## [0.5.1]

### Fixed

- Accept utf8 file names

## [0.5.0]

### Added

- Command line option `--sarif`

## [0.4.0]

### Added

- Command line option `--files`

## [0.3.1]

### Fixed

- Do not take `foo.bar.baz imports foo.bar.__init__` into account

## [0.3.0]

### Added

- Command line option `--outputs-folder`
- Command line option `--outputs-filename`

### Changed

- Changed default outputs folder from `$HOME/.local/py_import_cycles/outputs` to
`$HOME/.local/py-import-cycles/outputs`.
- Paths of the command line option `--packages` have to be absolute paths

### Removed

- Removed project path from outputs filename. Use the current timestamp instead.
- Removed command line option `--project-path`

### Fixed
