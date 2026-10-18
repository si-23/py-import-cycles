#!/usr/bin/env python3

import ast
import logging
from collections.abc import Mapping
from pathlib import Path

import pytest

from py_import_cycles.modules import ModuleName, PyModule
from py_import_cycles.visitors import (
    NodeVisitorImports,
    _AbsImportFromStmt,
    _AbsImportStmt,
    _compute_py_module_from_abs_import_from_stmt,
    _RelImportFromStmt,
    visit_py_module,
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
        PyModule(tmp_path / "path/to/package", path / "c.py"),
        PyModule(tmp_path / "path/to/package", path / "__init__.py"),
    ]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
import foo
import a.b  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
from . import bar
""",
            id="same-line",
        ),
        pytest.param(
            """
import foo
# linter-1: ... # py-import-cycles: ignore # linter-2: ...
import a.b
from . import bar
""",
            id="line-above",
        ),
        pytest.param(
            """
import foo
from a import (  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    b
)
from . import bar
""",
            id="multiline",
        ),
        pytest.param(
            """
def func():
    import foo
    import a.b  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    from . import bar
""",
            id="nested-same-line",
        ),
        pytest.param(
            """
def func():
    import foo
    # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    import a.b
    from . import bar
""",
            id="nested-line-above",
        ),
        pytest.param(
            """
def func():
    import foo
    from a import (  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
        b
    )
    from . import bar
""",
            id="nested-multiline",
        ),
    ],
)
def test_linter_statement(code: str) -> None:
    visitor = NodeVisitorImports(code)
    visitor.visit(ast.parse(code))
    assert visitor.abs_import_stmts == [_AbsImportStmt(names=("foo",))]
    assert not visitor.abs_import_from_stmts
    assert visitor.rel_import_from_stmts == [_RelImportFromStmt(level=1, module="", names=("bar",))]


def test_log_unresolvable_relative_import(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "module.py").write_text("from . import missing\n")
    caplog.set_level(logging.DEBUG, logger="py_import_cycles.log")

    list(visit_py_module({}, PyModule(package, package / "module.py")))

    assert str(package / "missing") in caplog.text
