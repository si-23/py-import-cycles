#!/usr/bin/env python3

from collections.abc import Mapping
from pathlib import Path

from py_import_cycles.modules import ModuleName, PyModule  # pylint: disable=import-error
from py_import_cycles.visitors import (  # pylint: disable=import-error
    _AbsImportFromStmt,
    _compute_py_module_from_abs_import_from_stmt,
)


def test__compute_py_module_from_abs_import_from_stmt_all_modules(
    tmp_path: Path,
) -> None:
    path = tmp_path / "path/to/package/a/b"
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").touch()
    (path / "c.py").touch()
    (path / "d.py").touch()

    py_modules_by_name: Mapping[ModuleName, PyModule] = {
        m.name: m
        for m in [
            PyModule(tmp_path / "path/to/package", path / "__init__.py"),
            PyModule(tmp_path / "path/to/package", path / "c.py"),
            PyModule(tmp_path / "path/to/package", path / "d.py"),
        ]
    }
    assert list(
        _compute_py_module_from_abs_import_from_stmt(
            py_modules_by_name, _AbsImportFromStmt("package.a.b", ("c", "d"))
        )
    ) == [
        PyModule(tmp_path / "path/to/package", path / "__init__.py"),
        PyModule(tmp_path / "path/to/package", path / "c.py"),
        PyModule(tmp_path / "path/to/package", path / "d.py"),
    ]


def test__compute_py_module_from_abs_import_from_stmt_not_all_modules(
    tmp_path: Path,
) -> None:
    path = tmp_path / "path/to/package/a/b"
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").touch()
    (path / "c.py").touch()

    py_modules_by_name: Mapping[ModuleName, PyModule] = {
        m.name: m
        for m in [
            PyModule(tmp_path / "path/to/package", path / "__init__.py"),
            PyModule(tmp_path / "path/to/package", path / "c.py"),
        ]
    }
    assert list(
        _compute_py_module_from_abs_import_from_stmt(
            py_modules_by_name, _AbsImportFromStmt("package.a.b", ("c", "d"))
        )
    ) == [
        PyModule(tmp_path / "path/to/package", path / "__init__.py"),
        PyModule(tmp_path / "path/to/package", path / "c.py"),
    ]
