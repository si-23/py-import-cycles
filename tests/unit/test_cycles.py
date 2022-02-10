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
        (
            {
                "a": [ModuleImport("b", tuple())],
                "b": [ModuleImport("a", tuple()), ModuleImport("c", tuple())],
                "c": [ModuleImport("d", tuple())],
            },
            [
                ChainWithCycle(cycle=("a", "b", "a"), chain=["a", "b", "a"]),
                ChainWithCycle(cycle=("b", "a", "b"), chain=["b", "a", "b"]),
            ],
        ),
        (
            {
                "a": [ModuleImport("b", tuple())],
                "b": [ModuleImport("c", tuple())],
                "c": [ModuleImport("a", tuple()), ModuleImport("d", tuple())],
            },
            [
                ChainWithCycle(cycle=("a", "b", "c", "a"), chain=["a", "b", "c", "a"]),
                ChainWithCycle(cycle=("b", "c", "a", "b"), chain=["b", "c", "a", "b"]),
                ChainWithCycle(cycle=("c", "a", "b", "c"), chain=["c", "a", "b", "c"]),
            ],
        ),
        (
            {
                "a": [ModuleImport("b", tuple())],
                "b": [ModuleImport("c", tuple())],
                "c": [ModuleImport("a", tuple()), ModuleImport("d", tuple())],
                "d": [ModuleImport("b", tuple())],
            },
            [
                ChainWithCycle(cycle=("a", "b", "c", "a"), chain=["a", "b", "c", "a"]),
                ChainWithCycle(cycle=("b", "c", "a", "b"), chain=["b", "c", "a", "b"]),
                ChainWithCycle(cycle=("b", "c", "d", "b"), chain=["b", "c", "d", "b"]),
                ChainWithCycle(cycle=("c", "a", "b", "c"), chain=["c", "a", "b", "c"]),
                ChainWithCycle(cycle=("c", "d", "b", "c"), chain=["c", "d", "b", "c"]),
                ChainWithCycle(
                    cycle=("b", "c", "a", "b"), chain=["d", "b", "c", "a", "b"]
                ),
                ChainWithCycle(cycle=("d", "b", "c", "d"), chain=["d", "b", "c", "d"]),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    assert list(DetectImportCycles(module_imports).detect_cycles()) == expected_cycles
