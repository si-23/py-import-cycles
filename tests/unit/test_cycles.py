#!/usr/bin/env python3

from pathlib import Path

import pytest
from project.main import DetectImportCycles, Module


@pytest.mark.parametrize(
    "module_imports, expected_cycles",
    [
        ({}, []),
        (
            {Module(Path(), "a"): [Module(Path(), "b")]},
            [],
        ),
        (
            {
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
            },
            [("a", "b", "a")],
        ),
        (
            {
                Module(Path(), "m1"): [Module(Path(), "a")],
                Module(Path(), "m2"): [Module(Path(), "a")],
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
            },
            [("a", "b", "a")],
        ),
        (
            {
                Module(Path(), "m1"): [Module(Path(), "a")],
                Module(Path(), "m2"): [Module(Path(), "b")],
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
            },
            [("a", "b", "a")],
        ),
        (
            {
                Module(Path(), "m"): [Module(Path(), "a"), Module(Path(), "y")],
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
                Module(Path(), "y"): [Module(Path(), "z")],
                Module(Path(), "z"): [Module(Path(), "y")],
            },
            [
                ("a", "b", "a"),
                ("y", "z", "y"),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    detector = DetectImportCycles(module_imports)
    detector.detect_cycles()
    assert detector.cycles == expected_cycles
