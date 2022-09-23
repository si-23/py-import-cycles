#!/usr/bin/env python3

from pathlib import Path

import pytest

from py_import_cycles.main import (  # pylint: disable=import-error
    ModuleFactory,
    ModuleName,
    NamespacePackage,
    PyModule,
    RegularPackage,
)


@pytest.mark.parametrize(
    "raw_package_path, raw_module_name, expected_raw_module_name",
    [
        ("a/b/c", "a.b.c", "a.b.c.__init__"),
        ("a/b", "a.b.*", "a.b.__init__"),
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

    module = ModuleFactory({}, project_folder).make_module_from_name(ModuleName(raw_module_name))

    assert isinstance(module, RegularPackage)
    assert module.path == init_filepath
    assert module.name.parts == ModuleName(expected_raw_module_name).parts


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

    module = ModuleFactory({}, project_folder).make_module_from_name(ModuleName(raw_module_name))

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

    module = ModuleFactory({}, project_folder).make_module_from_name(ModuleName(raw_module_name))

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
        ModuleFactory({}, Path("/path/to/project")).make_module_from_name(
            ModuleName(raw_module_name)
        )
