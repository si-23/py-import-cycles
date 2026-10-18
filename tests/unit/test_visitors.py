#!/usr/bin/env python3

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from py_import_cycles.files import scan_packages
from py_import_cycles.modules import ModuleName, PyModule
from py_import_cycles.visitors import visit_py_module


def _imports(package: Path, module: str) -> Sequence[str]:
    py_modules_by_name = {m.name: m for m in scan_packages([package])}
    return [
        str(m) for m in visit_py_module(py_modules_by_name, py_modules_by_name[ModuleName(module)])
    ]


def _visit(package: Path, files: Mapping[str, str], module: str) -> Sequence[str]:
    for name, code in files.items():
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text(code)
    return _imports(package, module)


def test_import_from_modules(tmp_path: Path) -> None:
    files = {
        "a/b/__init__.py": "",
        "a/b/c.py": "",
        "a/b/d.py": "",
        "mod.py": "from package.a.b import c, d\n",
    }
    assert _visit(tmp_path / "package", files, "package.mod") == [
        "package.a.b.c",
        "package.a.b.d",
    ]


def test_import_from_module_and_object(tmp_path: Path) -> None:
    files = {
        "a/b/__init__.py": "",
        "a/b/c.py": "",
        "mod.py": "from package.a.b import c, d\n",
    }
    assert _visit(tmp_path / "package", files, "package.mod") == [
        "package.a.b.c",
        "package.a.b.__init__",
    ]


def test_relative_import_prefers_package_to_module(tmp_path: Path) -> None:
    files = {"x.py": "", "x/__init__.py": "", "a.py": "from . import x\n"}
    assert _visit(tmp_path / "pkg", files, "pkg.a") == ["pkg.x.__init__"]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
import pkg.foo
import pkg.a.b  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
from . import bar
""",
            id="same-line",
        ),
        pytest.param(
            """
import pkg.foo
# linter-1: ... # py-import-cycles: ignore # linter-2: ...
import pkg.a.b
from . import bar
""",
            id="line-above",
        ),
        pytest.param(
            """
import pkg.foo
from pkg.a import (  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    b
)
from . import bar
""",
            id="multiline",
        ),
        pytest.param(
            """
def func():
    import pkg.foo
    import pkg.a.b  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    from . import bar
""",
            id="nested-same-line",
        ),
        pytest.param(
            """
def func():
    import pkg.foo
    # linter-1: ... # py-import-cycles: ignore # linter-2: ...
    import pkg.a.b
    from . import bar
""",
            id="nested-line-above",
        ),
        pytest.param(
            """
def func():
    import pkg.foo
    from pkg.a import (  # linter-1: ... # py-import-cycles: ignore # linter-2: ...
        b
    )
    from . import bar
""",
            id="nested-multiline",
        ),
    ],
)
def test_ignore_comment(tmp_path: Path, code: str) -> None:
    files = {
        "foo.py": "",
        "bar.py": "",
        "a/__init__.py": "",
        "a/b.py": "",
        "mod.py": code,
    }
    assert _visit(tmp_path / "pkg", files, "pkg.mod") == ["pkg.foo", "pkg.bar"]


def test_ignore_comment_on_multiline_import_of_several_names(tmp_path: Path) -> None:
    code = "from pkg import (  # py-import-cycles: ignore\n    b,\n    c,\n)\n"
    files = {"b.py": "", "c.py": "", "a.py": code}
    assert _visit(tmp_path / "pkg", files, "pkg.a") == []


def test_ignore_comment_in_last_line_keeps_import_in_first_line(tmp_path: Path) -> None:
    files = {"b.py": "", "a.py": "import pkg.b\nx = 1\n# py-import-cycles: ignore"}
    assert _visit(tmp_path / "pkg", files, "pkg.a") == ["pkg.b"]


def test_skip_file_that_cannot_be_read(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "a.py").write_text("import pkg.b\n")
    (package / "b.py").touch()
    py_modules_by_name = {m.name: m for m in scan_packages([package])}
    (package / "a.py").unlink()

    assert list(visit_py_module(py_modules_by_name, py_modules_by_name[ModuleName("pkg.a")])) == []


def test_honour_coding_declaration(tmp_path: Path) -> None:
    code = "# -*- coding: latin-1 -*-\nimport pkg.b\ns = '\u00e9'\n"
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "b.py").touch()
    (package / "a.py").write_bytes(code.encode("latin-1"))
    assert _imports(package, "pkg.a") == ["pkg.b"]


def test_log_unresolvable_relative_import(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "module.py").write_text("from . import missing\n")
    caplog.set_level(logging.DEBUG, logger="py_import_cycles.log")

    list(visit_py_module({}, PyModule(package, package / "module.py")))

    assert str(package / "missing") in caplog.text
