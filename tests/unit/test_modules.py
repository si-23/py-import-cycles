#!/usr/bin/env python3

from pathlib import Path
from typing import Sequence

import pytest

from py_import_cycles.modules import ModuleName, PyFile, PyFileType  # pylint: disable=import-error


@pytest.mark.parametrize(
    "parts, expected",
    [
        ([], ModuleName()),
        ([ModuleName()], ModuleName()),
        (["a"], ModuleName("a")),
        ([ModuleName("a")], ModuleName("a")),
        (["a", "b"], ModuleName("a", "b")),
        ([ModuleName("a"), ModuleName("b")], ModuleName("a", "b")),
        ([ModuleName("a.b")], ModuleName("a.b")),
        ([ModuleName("a.b")], ModuleName("a", "b")),
        ([ModuleName("a"), ModuleName("b")], ModuleName("a.b")),
    ],
)
def test_module_name_init_or_equal(parts: Sequence[str | ModuleName], expected: ModuleName) -> None:
    assert ModuleName(*parts) == expected


@pytest.mark.parametrize(
    "module_name, expected",
    [
        (ModuleName(), ""),
        (ModuleName("a"), "a"),
        (ModuleName("a", "b"), "a.b"),
    ],
)
def test_module_name_str(module_name: ModuleName, expected: str) -> None:
    assert str(module_name) == expected


@pytest.mark.parametrize(
    "module_name, expected",
    [
        (ModuleName(), tuple()),
        (ModuleName("a"), ("a",)),
        (ModuleName("a", "b"), ("a", "b")),
    ],
)
def test_module_name_parts(module_name: ModuleName, expected: Sequence[str]) -> None:
    assert module_name.parts == expected


@pytest.mark.parametrize(
    "module_name, expected",
    [
        (ModuleName(), ModuleName()),
        (ModuleName("a"), ModuleName()),
        (ModuleName("a", "b"), ModuleName("a")),
    ],
)
def test_module_name_parent(module_name: ModuleName, expected: Sequence[str]) -> None:
    assert module_name.parent == expected


@pytest.mark.parametrize(
    "module_names, expected",
    [
        ([], ModuleName()),
        ([ModuleName()], ModuleName()),
        ([ModuleName("a")], ModuleName("a")),
        ([ModuleName("a"), ModuleName("b")], ModuleName("a", "b")),
    ],
)
def test_module_name_joinname(module_names: Sequence[ModuleName], expected: ModuleName) -> None:
    assert ModuleName().joinname(*module_names) == expected


def test_py_file_namespace_package(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    py_file = PyFile(
        package=tmp_path / "path/to",
        path=tmp_path / "path/to/package",
    )
    assert py_file.type is PyFileType.NAMESPACE_PACKAGE
    assert py_file.name == ModuleName("package")
    assert str(py_file) == "package/"
    assert list(py_file.parents) == [PyFile(package=tmp_path / "path/to", path=Path())]


def test_py_file_regular_package(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").touch()
    py_file = PyFile(
        package=tmp_path / "path/to",
        path=tmp_path / "path/to/package/__init__.py",
    )
    assert py_file.type is PyFileType.REGULAR_PACKAGE
    assert py_file.name == ModuleName("package")
    assert str(py_file) == "package.__init__"
    assert list(py_file.parents) == [PyFile(package=tmp_path / "path/to", path=Path())]


def test_py_file_module(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    (path / "module.py").touch()
    py_file = PyFile(
        package=tmp_path / "path/to",
        path=tmp_path / "path/to/package/module.py",
    )
    assert py_file.type is PyFileType.MODULE
    assert py_file.name == ModuleName("package.module")
    assert str(py_file) == "package.module"
    assert list(py_file.parents) == [
        PyFile(
            package=tmp_path / "path/to",
            path=tmp_path / "path/to/package",
        ),
        PyFile(
            package=tmp_path / "path/to",
            path=Path(),
        ),
    ]


def test_py_file_module_parents(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "path/to/package/__init__.py").touch()
    (tmp_path / "path/to/__init__.py").touch()
    (path / "module.py").touch()
    py_file = PyFile(
        package=tmp_path,
        path=tmp_path / "path/to/package/module.py",
    )
    assert list(py_file.parents) == [
        PyFile(
            package=tmp_path,
            path=tmp_path / "path/to/package/__init__.py",
        ),
        PyFile(
            package=tmp_path,
            path=tmp_path / "path/to/__init__.py",
        ),
        PyFile(
            package=tmp_path,
            path=tmp_path / "path",
        ),
        PyFile(
            package=tmp_path,
            path=Path(),
        ),
    ]
