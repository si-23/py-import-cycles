# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

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
