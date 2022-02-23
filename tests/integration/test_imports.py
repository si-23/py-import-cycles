#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Sequence

from project.main import (
    CycleAndChains,
    _find_import_cycles,
    _get_module_imports,
    _get_python_files,
    _load_python_contents,
    _visit_python_contents,
)


def _get_import_cycles(path: Path) -> Sequence[CycleAndChains]:
    # TODO encapsulate these steps in project.main
    python_files = _get_python_files(path)
    loaded_python_files = _load_python_contents(set(python_files))
    visitors = _visit_python_contents(loaded_python_files)
    module_imports = _get_module_imports({}, path, visitors)
    return _find_import_cycles(module_imports)


def test_imports_1():
    # ├── main.py::import mod_1
    # ├── mod_1.py::import mod_2
    # ├── mod_2.py::import mod_3
    # └── mod_3.py::import mod_1
    path = Path(os.path.dirname(os.path.realpath(__file__))).joinpath("imports-1")
    assert _get_import_cycles(path) == [
        CycleAndChains(
            cycle=("mod_1", "mod_2", "mod_3", "mod_1"),
            chains=[
                ["main", "mod_1", "mod_2", "mod_3", "mod_1"],
                ["mod_1", "mod_2", "mod_3", "mod_1"],
                ["mod_2", "mod_3", "mod_1", "mod_2"],
                ["mod_3", "mod_1", "mod_2", "mod_3"],
            ],
        )
    ]


def test_imports_2():
    # ├── main.py::import sub_pkg.mod_1
    # └── sub_pkg
    #     ├── __init__.py
    #     ├── mod_1.py::import sub_pkg.mod_2
    #     ├── mod_2.py::import sub_pkg.mod_3
    #     └── mod_3.py::import sub_pkg.mod_1
    path = Path(os.path.dirname(os.path.realpath(__file__))).joinpath("imports-2")
    assert _get_import_cycles(path) == [
        CycleAndChains(
            cycle=("sub_pkg.mod_1", "sub_pkg.mod_2", "sub_pkg.mod_3", "sub_pkg.mod_1"),
            chains=[
                [
                    "main",
                    "sub_pkg.mod_1",
                    "sub_pkg.mod_2",
                    "sub_pkg.mod_3",
                    "sub_pkg.mod_1",
                ],
                ["sub_pkg.mod_1", "sub_pkg.mod_2", "sub_pkg.mod_3", "sub_pkg.mod_1"],
                ["sub_pkg.mod_2", "sub_pkg.mod_3", "sub_pkg.mod_1", "sub_pkg.mod_2"],
                ["sub_pkg.mod_3", "sub_pkg.mod_1", "sub_pkg.mod_2", "sub_pkg.mod_3"],
            ],
        )
    ]


def test_imports_3():
    # ├── main.py::import sub_pkg
    # └── sub_pkg
    #     ├── __init__.py
    #     ├── mod_1.py::import sub_pkg.mod_2
    #     ├── mod_2.py::import sub_pkg.mod_3
    #     └── mod_3.py::import sub_pkg.mod_1
    path = Path(os.path.dirname(os.path.realpath(__file__))).joinpath("imports-3")
    assert _get_import_cycles(path) == [
        # FIXME
    ]


def test_imports_4():
    # ├── main.py::import sub_pkg
    # └── sub_pkg
    #     ├── __init__.py::import import sub_pkg.mod_1
    #     ├── mod_1.py::import sub_pkg.mod_2
    #     ├── mod_2.py::import sub_pkg.mod_3
    #     └── mod_3.py::import sub_pkg.mod_1
    path = Path(os.path.dirname(os.path.realpath(__file__))).joinpath("imports-4")
    assert _get_import_cycles(path) == [
        # FIXME with __init__ handling
    ]
