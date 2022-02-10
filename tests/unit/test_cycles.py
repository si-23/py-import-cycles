#!/usr/bin/env python3

import pytest
from project.main import DetectImportCycles, ModuleImport, ChainWithCycle


@pytest.mark.parametrize(
    "module_imports, expected_cycles",
    [
        ({}, []),
        ({"a": [ModuleImport("b", tuple())]}, []),
        (
            {"a": [ModuleImport("b", tuple())], "b": [ModuleImport("a", tuple())]},
            [
                ChainWithCycle(cycle=("a", "b", "a"), chain=["a", "b", "a"]),
                ChainWithCycle(cycle=("b", "a", "b"), chain=["b", "a", "b"]),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    assert list(DetectImportCycles(module_imports).detect_cycles()) == expected_cycles
