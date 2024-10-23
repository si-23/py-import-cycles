#!/usr/bin/env python3

from pathlib import Path
from typing import Sequence

import pytest

from py_import_cycles.files import iter_python_files  # pylint: disable=import-error
from py_import_cycles.modules import (  # pylint: disable=import-error
    make_modules_from_py_files,
    ModuleFactory,
    ModuleName,
    NamespacePackage,
    PyModule,
    RegularPackage,
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
    "module_name, expected",
    [
        (ModuleName(), []),
        (ModuleName("a"), []),
        (ModuleName("a", "b"), [ModuleName("a")]),
        (ModuleName("a", "b", "c"), [ModuleName("a", "b"), ModuleName("a")]),
    ],
)
def test_module_name_parents(module_name: ModuleName, expected: Sequence[ModuleName]) -> None:
    assert module_name.parents == expected


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


@pytest.mark.parametrize(
    "raw_package_path, raw_module_name, expected_raw_module_name",
    [
        ("a/b/c", "a.b.c", "a.b.c"),
        ("a/b", "a.b.*", "a.b"),
    ],
)
def test_make_module_from_name_regular_package(
    tmp_path: Path,
    raw_package_path: str,
    raw_module_name: str,
    expected_raw_module_name: str,
) -> None:
    project_folder = tmp_path / "path/to/project"
    package_folder = project_folder / raw_package_path
    package_folder.mkdir(parents=True, exist_ok=True)
    init_filepath = package_folder / "__init__.py"
    init_filepath.write_text("")

    modules = list(make_modules_from_py_files(iter_python_files(project_folder, [Path("a")])))
    module = ModuleFactory(project_folder, modules).make_module_from_name(
        ModuleName(raw_module_name)
    )

    assert isinstance(module, RegularPackage)
    assert module.path == init_filepath
    assert module.name.parts == ModuleName(expected_raw_module_name).parts


@pytest.mark.skip(reason="Not sure if we need this test")
@pytest.mark.parametrize(
    "raw_package_path, raw_module_name, expected_raw_module_name",
    [
        ("a/b/c", "a.b.c", "a.b.c"),
        ("a/b", "a.b.*", "a.b"),
    ],
)
def test_make_module_from_name_namespace_package(
    tmp_path: Path,
    raw_package_path: str,
    raw_module_name: str,
    expected_raw_module_name: str,
) -> None:
    project_folder = tmp_path / "path/to/project"
    package_folder = project_folder / raw_package_path
    package_folder.mkdir(parents=True, exist_ok=True)

    modules = list(make_modules_from_py_files(iter_python_files(project_folder, [Path("a")])))
    module = ModuleFactory(project_folder, modules).make_module_from_name(
        ModuleName(raw_module_name)
    )

    assert isinstance(module, NamespacePackage)
    assert module.path == package_folder
    assert module.name.parts == ModuleName(expected_raw_module_name).parts


@pytest.mark.parametrize(
    "raw_package_path, raw_filename, raw_module_name, expected_raw_module_name",
    [
        ("a/b", "c.py", "a.b.c", "a.b.c"),
        ("a", "b.py", "a.b.*", "a.b"),
    ],
)
def test_make_module_from_name_python_module(
    tmp_path: Path,
    raw_package_path: str,
    raw_filename: str,
    raw_module_name: str,
    expected_raw_module_name: str,
) -> None:
    project_folder = tmp_path / "path/to/project"
    package_folder = project_folder / raw_package_path
    package_folder.mkdir(parents=True, exist_ok=True)
    module_filepath = package_folder / raw_filename
    module_filepath.write_text("")

    modules = list(make_modules_from_py_files(iter_python_files(project_folder, [Path("a")])))
    module = ModuleFactory(project_folder, modules).make_module_from_name(
        ModuleName(raw_module_name)
    )

    assert isinstance(module, PyModule)
    assert module.path == module_filepath
    assert module.name.parts == ModuleName(expected_raw_module_name).parts


@pytest.mark.parametrize(
    "raw_module_name",
    [
        "a.b.c",
        "a.b.*",
    ],
)
def test_make_module_from_name_error(raw_module_name: str) -> None:
    with pytest.raises(ValueError):
        ModuleFactory(Path("/path/to/project"), []).make_module_from_name(
            ModuleName(raw_module_name)
        )


@pytest.mark.parametrize(
    "raw_package_path, expected_raw_module_name",
    [
        ("a/b/c", "a.b.c"),
    ],
)
def test_make_module_from_path_regular_package(
    tmp_path: Path,
    raw_package_path: str,
    expected_raw_module_name: str,
) -> None:
    project_folder = tmp_path / "path/to/project"
    package_folder = project_folder / raw_package_path
    package_folder.mkdir(parents=True, exist_ok=True)
    init_filepath = package_folder / "__init__.py"
    init_filepath.write_text("")

    modules = list(make_modules_from_py_files(iter_python_files(project_folder, [Path("a")])))

    assert modules
    module = modules[0]
    assert isinstance(module, RegularPackage)
    assert module.path == init_filepath
    assert module.name.parts == ModuleName(expected_raw_module_name).parts


@pytest.mark.parametrize(
    "raw_package_path, raw_filename, expected_raw_module_name",
    [
        ("a/b", "c.py", "a.b.c"),
    ],
)
def test_make_module_from_path_python_module(
    tmp_path: Path,
    raw_package_path: str,
    raw_filename: str,
    expected_raw_module_name: str,
) -> None:
    project_folder = tmp_path / "path/to/project"
    package_folder = project_folder / raw_package_path
    package_folder.mkdir(parents=True, exist_ok=True)
    module_filepath = package_folder / raw_filename
    module_filepath.write_text("")

    modules = list(make_modules_from_py_files(iter_python_files(project_folder, [Path("a")])))

    assert modules
    module = modules[0]
    assert isinstance(module, PyModule)
    assert module.path == module_filepath
    assert module.name.parts == ModuleName(expected_raw_module_name).parts
