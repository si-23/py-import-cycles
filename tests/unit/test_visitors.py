#!/usr/bin/env python3

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from py_import_cycles.files import scan_packages
from py_import_cycles.modules import ModuleName, make_py_modules_by_name
from py_import_cycles.visitors import visit_py_module


def _imports(package: Path, module: str) -> Sequence[str]:
    py_modules_by_name = make_py_modules_by_name(scan_packages([package]))
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


@pytest.mark.parametrize(
    "files, module, expected",
    [
        pytest.param(
            {"b.py": "", "c.py": "", "a.py": "import pkg.b, pkg.c\n"},
            "pkg.a",
            ["pkg.b", "pkg.c"],
            id="import-several-names",
        ),
        pytest.param(
            {"sub/__init__.py": "", "a.py": "from pkg.sub import *\n"},
            "pkg.a",
            ["pkg.sub.__init__"],
            id="star-import",
        ),
        pytest.param(
            {"b.py": "", "a.py": "from .b import f\n"},
            "pkg.a",
            ["pkg.b"],
            id="relative-import-of-object",
        ),
        pytest.param(
            {"sub/__init__.py": "from . import m\n", "sub/m.py": ""},
            "pkg.sub",
            ["pkg.sub.m"],
            id="relative-import-in-package-init",
        ),
        pytest.param(
            {"ns/m.py": "", "a.py": "from . import ns\n"},
            "pkg.a",
            ["pkg.ns/"],
            id="relative-import-of-namespace-package",
        ),
        pytest.param(
            {"a.py": "import os\nimport requests\n"},
            "pkg.a",
            [],
            id="unscanned-modules",
        ),
        pytest.param(
            {"a.py": "import pkg.a\n"},
            "pkg.a",
            [],
            id="self-import",
        ),
        pytest.param(
            {"ns/m.py": "import pkg.b\n", "b.py": ""},
            "pkg.ns",
            [],
            id="namespace-package-has-no-imports",
        ),
        pytest.param(
            {"b.py": "", "a.py": "import pkg.b\ndef (:\n"},
            "pkg.a",
            [],
            id="syntax-error",
        ),
        pytest.param(
            {"b.py": "", "a.py": "# -*- coding: no-such-codec -*-\nimport pkg.b\n"},
            "pkg.a",
            [],
            id="unknown-coding",
        ),
    ],
)
def test_imports(
    tmp_path: Path, files: Mapping[str, str], module: str, expected: Sequence[str]
) -> None:
    assert _visit(tmp_path / "pkg", files, module) == expected


def test_relative_import_from_parent_in_package_init(tmp_path: Path) -> None:
    files = {"sub/__init__.py": "from .. import b\n", "b.py": ""}
    assert _visit(tmp_path / "pkg", files, "pkg.sub") == ["pkg.b"]


def test_relative_import_prefers_package_to_module(tmp_path: Path) -> None:
    files = {"x.py": "", "x/__init__.py": "", "a.py": "from . import x\n"}
    assert _visit(tmp_path / "pkg", files, "pkg.a") == ["pkg.x.__init__"]


def test_import_package_named_like_stdlib_module(tmp_path: Path) -> None:
    files = {"a.py": "import email.b\n", "b.py": ""}
    assert _visit(tmp_path / "email", files, "email.a") == ["email.b"]


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


@pytest.mark.parametrize(
    "comment, expected",
    [
        pytest.param("# py-import-cycles:ignore", [], id="no-space"),
        pytest.param("#  py-import-cycles:   ignore", [], id="extra-spaces"),
        pytest.param("# py-import-cycles: ignore because of the plugin API", [], id="reason"),
        pytest.param("# py-import-cycles: ignored", ["pkg.b"], id="other-word"),
    ],
)
def test_ignore_comment_spelling(tmp_path: Path, comment: str, expected: Sequence[str]) -> None:
    files = {"b.py": "", "a.py": f"import pkg.b  {comment}\n"}
    assert _visit(tmp_path / "pkg", files, "pkg.a") == expected


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
    py_modules_by_name = make_py_modules_by_name(scan_packages([package]))
    (package / "a.py").unlink()

    assert list(visit_py_module(py_modules_by_name, py_modules_by_name[ModuleName("pkg.a")])) == []


def test_honour_coding_declaration(tmp_path: Path) -> None:
    code = "# -*- coding: latin-1 -*-\nimport pkg.b\ns = '\u00e9'\n"
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "b.py").touch()
    (package / "a.py").write_bytes(code.encode("latin-1"))
    assert _imports(package, "pkg.a") == ["pkg.b"]


def test_log_relative_import_beyond_top_level_package(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="py_import_cycles.log")

    _visit(tmp_path / "pkg", {"a.py": "from ... import x\n"}, "pkg.a")

    assert "Cannot resolve relative import of level 3 in pkg.a" in caplog.text
