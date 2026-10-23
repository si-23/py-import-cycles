#!/usr/bin/env python3

from collections.abc import Callable
from pathlib import Path

import pytest

from py_import_cycles.modules import PyModule, make_py_module


@pytest.fixture(name="make_py_module")
def fixture_make_py_module(tmp_path: Path) -> Callable[[str], PyModule]:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").touch()

    def make_named_py_module(name: str) -> PyModule:
        path = package / f"{name}.py"
        path.touch()
        return make_py_module(package, path)

    return make_named_py_module
