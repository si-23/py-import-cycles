#!/usr/bin/env python3

import pytest
from project.main import DetectImportCycles, ModuleImport, CycleAndChains


@pytest.mark.parametrize(
    "module_imports, expected_cycles",
    [
        ({}, []),
        ({"a": [ModuleImport("b", tuple())]}, []),
        (
            {"a": [ModuleImport("b", tuple())], "b": [ModuleImport("a", tuple())]},
            [
                CycleAndChains(
                    cycle=("a", "b", "a"), chains=[["a", "b", "a"], ["b", "a", "b"]]
                ),
            ],
        ),
        (
            {
                "a": [ModuleImport("b", tuple())],
                "b": [ModuleImport("a", tuple()), ModuleImport("c", tuple())],
                "c": [ModuleImport("d", tuple())],
            },
            [
                CycleAndChains(
                    cycle=("a", "b", "a"), chains=[["a", "b", "a"], ["b", "a", "b"]]
                ),
            ],
        ),
        (
            {
                "a": [ModuleImport("b", tuple())],
                "b": [ModuleImport("c", tuple())],
                "c": [ModuleImport("a", tuple()), ModuleImport("d", tuple())],
            },
            [
                CycleAndChains(
                    cycle=("a", "b", "c", "a"),
                    chains=[
                        ["a", "b", "c", "a"],
                        ["b", "c", "a", "b"],
                        ["c", "a", "b", "c"],
                    ],
                ),
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
                CycleAndChains(
                    cycle=("a", "b", "c", "a"),
                    chains=[
                        ["a", "b", "c", "a"],
                        ["b", "c", "a", "b"],
                        ["c", "a", "b", "c"],
                        ["d", "b", "c", "a", "b"],
                    ],
                ),
                CycleAndChains(
                    cycle=("b", "c", "d", "b"),
                    chains=[
                        ["b", "c", "d", "b"],
                        ["c", "d", "b", "c"],
                        ["d", "b", "c", "d"],
                    ],
                ),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    detector = DetectImportCycles(module_imports)
    detector.detect_cycles()
    assert detector.cycles == expected_cycles
