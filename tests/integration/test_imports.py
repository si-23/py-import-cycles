#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Sequence

from project.main import (
    _get_python_files,
    _load_python_contents,
    _visit_python_contents,
    _get_module_imports,
    _find_import_cycles,
    CycleAndChains,
)


def _get_import_cycles(path: Path) -> Sequence[CycleAndChains]:
    # TODO encapsulate these steps in project.main
    python_files = _get_python_files(path)
    loaded_python_files = _load_python_contents(set(python_files))
    visitors = _visit_python_contents(loaded_python_files)
    module_imports = _get_module_imports({}, path, visitors)
    return _find_import_cycles(module_imports)


def test_imports_1():
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
