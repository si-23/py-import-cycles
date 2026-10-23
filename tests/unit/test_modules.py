#!/usr/bin/env python3

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from py_import_cycles.modules import (
    ModuleName,
    PyModule,
    PyModuleType,
    make_py_module,
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
        ([ModuleName("a.b")], ModuleName("a", "b")),
    ],
)
def test_module_name_init_or_equal(parts: Sequence[str | ModuleName], expected: ModuleName) -> None:
    assert ModuleName(*parts) == expected


def test_module_name_rejects_empty_part() -> None:
    with pytest.raises(ValueError):
        ModuleName("a..b")


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


def _make_namespace_package(tmp_path: Path) -> PyModule:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True)
    return make_py_module(path, path)


def _make_regular_package(tmp_path: Path) -> PyModule:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True)
    (path / "__init__.py").touch()
    return make_py_module(path, path / "__init__.py")


def _make_module(tmp_path: Path) -> PyModule:
    path = tmp_path / "path/to/package"
    path.mkdir(parents=True)
    (path / "module.py").touch()
    return make_py_module(path, path / "module.py")


@pytest.mark.parametrize(
    "make_py_module, expected",
    [
        (_make_namespace_package, PyModuleType.NAMESPACE_PACKAGE),
        (_make_regular_package, PyModuleType.REGULAR_PACKAGE),
        (_make_module, PyModuleType.MODULE),
    ],
)
def test_py_module_type(
    tmp_path: Path, make_py_module: Callable[[Path], PyModule], expected: PyModuleType
) -> None:
    assert make_py_module(tmp_path).type is expected


@pytest.mark.parametrize(
    "make_py_module, expected",
    [
        (_make_namespace_package, ModuleName("package")),
        (_make_regular_package, ModuleName("package")),
        (_make_module, ModuleName("package.module")),
    ],
)
def test_py_module_name(
    tmp_path: Path, make_py_module: Callable[[Path], PyModule], expected: ModuleName
) -> None:
    assert make_py_module(tmp_path).name == expected


@pytest.mark.parametrize(
    "make_py_module, expected",
    [
        (_make_namespace_package, "package/"),
        (_make_regular_package, "package.__init__"),
        (_make_module, "package.module"),
    ],
)
def test_py_module_str(
    tmp_path: Path, make_py_module: Callable[[Path], PyModule], expected: str
) -> None:
    assert str(make_py_module(tmp_path)) == expected


def test_equal_py_modules_collapse_in_set(tmp_path: Path) -> None:
    roots = [tmp_path / "root1", tmp_path / "root2"]
    for root in roots:
        (root / "package").mkdir(parents=True)
        (root / "package" / "module.py").touch()

    assert len({make_py_module(r / "package", r / "package" / "module.py") for r in roots}) == 1
