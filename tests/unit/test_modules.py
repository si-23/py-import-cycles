#!/usr/bin/env python3

from collections.abc import Sequence
from pathlib import Path

import pytest

from py_import_cycles.modules import (
    ModuleName,
    PyModule,
    PyModuleType,
)


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


def test_namespace_package(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    py_module = PyModule(
        package=tmp_path / "path/to/package",
        path=tmp_path / "path/to/package",
    )
    assert py_module.type is PyModuleType.NAMESPACE_PACKAGE
    assert py_module.name == ModuleName("package")
    assert str(py_module) == "package/"


def test_regular_package(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").touch()
    py_module = PyModule(
        package=tmp_path / "path/to/package",
        path=tmp_path / "path/to/package/__init__.py",
    )
    assert py_module.type is PyModuleType.REGULAR_PACKAGE
    assert py_module.name == ModuleName("package")
    assert str(py_module) == "package.__init__"


def test_py_module(tmp_path: Path) -> None:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True, exist_ok=True)
    (path / "module.py").touch()
    py_module = PyModule(
        package=tmp_path / "path/to/package",
        path=tmp_path / "path/to/package/module.py",
    )
    assert py_module.type is PyModuleType.MODULE
    assert py_module.name == ModuleName("package.module")
    assert str(py_module) == "package.module"


def test_equal_py_modules_collapse_in_set(tmp_path: Path) -> None:
    roots = [tmp_path / "root1", tmp_path / "root2"]
    for root in roots:
        (root / "package").mkdir(parents=True)
        (root / "package" / "module.py").touch()

    assert (
        len({PyModule(package=r / "package", path=r / "package" / "module.py") for r in roots}) == 1
    )
