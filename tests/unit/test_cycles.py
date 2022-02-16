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
            [
                ("a", "b", "a"),
            ],
        ),
        (
            {
                Module(Path(), "m1"): [Module(Path(), "a")],
                Module(Path(), "m2"): [Module(Path(), "a")],
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
            },
            [
                ("a", "b", "a"),
            ],
        ),
        (
            {
                Module(Path(), "m1"): [Module(Path(), "a")],
                Module(Path(), "m2"): [Module(Path(), "b")],
                Module(Path(), "a"): [Module(Path(), "b")],
                Module(Path(), "b"): [Module(Path(), "a")],
            },
            [
                ("a", "b", "a"),
            ],
        ),
        (
            {
                Module(Path(), "m"): [Module(Path(), "c11"), Module(Path(), "c21")],
                Module(Path(), "c11"): [Module(Path(), "c12")],
                Module(Path(), "c12"): [Module(Path(), "c11")],
                Module(Path(), "c21"): [Module(Path(), "c22")],
                Module(Path(), "c22"): [Module(Path(), "c21")],
            },
            [
                ("c11", "c12", "c11"),
                ("c21", "c22", "c21"),
            ],
        ),
        (
            {
                Module(Path(), "m"): [Module(Path(), "c11"), Module(Path(), "c21")],
                Module(Path(), "c11"): [Module(Path(), "c12"), Module(Path(), "c13")],
                Module(Path(), "c12"): [Module(Path(), "c11")],
                Module(Path(), "c13"): [Module(Path(), "c14")],
                Module(Path(), "c14"): [Module(Path(), "c11")],
                Module(Path(), "c21"): [Module(Path(), "c22")],
                Module(Path(), "c22"): [Module(Path(), "c21")],
            },
            [
                ("c11", "c12", "c11"),
                ("c11", "c13", "c14", "c11"),
                ("c21", "c22", "c21"),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    detector = DetectImportCycles(module_imports)
    detector.detect_cycles()
    assert detector.cycles == expected_cycles
