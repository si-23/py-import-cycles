#!/usr/bin/env python3

from pathlib import Path

import pytest

from project.main import DetectorImportCycles, PyModule


@pytest.mark.parametrize(
    "module_imports, expected_cycles",
    [
        ({}, []),
        (
            {PyModule(Path(), "a"): [PyModule(Path(), "b")]},
            [],
        ),
        (
            {
                PyModule(Path(), "a"): [PyModule(Path(), "b")],
                PyModule(Path(), "b"): [PyModule(Path(), "a")],
            },
            [
                (
                    PyModule(path=Path(), name="a"),
                    PyModule(path=Path(), name="b"),
                    PyModule(path=Path(), name="a"),
                ),
            ],
        ),
        (
            {
                PyModule(Path(), "m1"): [PyModule(Path(), "a")],
                PyModule(Path(), "m2"): [PyModule(Path(), "a")],
                PyModule(Path(), "a"): [PyModule(Path(), "b")],
                PyModule(Path(), "b"): [PyModule(Path(), "a")],
            },
            [
                (
                    PyModule(path=Path(), name="a"),
                    PyModule(path=Path(), name="b"),
                    PyModule(path=Path(), name="a"),
                ),
            ],
        ),
        (
            {
                PyModule(Path(), "m1"): [PyModule(Path(), "a")],
                PyModule(Path(), "m2"): [PyModule(Path(), "b")],
                PyModule(Path(), "a"): [PyModule(Path(), "b")],
                PyModule(Path(), "b"): [PyModule(Path(), "a")],
            },
            [
                (
                    PyModule(path=Path(), name="a"),
                    PyModule(path=Path(), name="b"),
                    PyModule(path=Path(), name="a"),
                ),
            ],
        ),
        (
            {
                PyModule(Path(), "m"): [
                    PyModule(Path(), "c11"),
                    PyModule(Path(), "c21"),
                ],
                PyModule(Path(), "c11"): [PyModule(Path(), "c12")],
                PyModule(Path(), "c12"): [PyModule(Path(), "c11")],
                PyModule(Path(), "c21"): [PyModule(Path(), "c22")],
                PyModule(Path(), "c22"): [PyModule(Path(), "c21")],
            },
            [
                (
                    PyModule(path=Path(), name="c11"),
                    PyModule(path=Path(), name="c12"),
                    PyModule(path=Path(), name="c11"),
                ),
                (
                    PyModule(path=Path(), name="c21"),
                    PyModule(path=Path(), name="c22"),
                    PyModule(path=Path(), name="c21"),
                ),
            ],
        ),
        (
            {
                PyModule(Path(), "m"): [
                    PyModule(Path(), "c11"),
                    PyModule(Path(), "c21"),
                ],
                PyModule(Path(), "c11"): [
                    PyModule(Path(), "c12"),
                    PyModule(Path(), "c13"),
                ],
                PyModule(Path(), "c12"): [PyModule(Path(), "c11")],
                PyModule(Path(), "c13"): [PyModule(Path(), "c14")],
                PyModule(Path(), "c14"): [PyModule(Path(), "c11")],
                PyModule(Path(), "c21"): [PyModule(Path(), "c22")],
                PyModule(Path(), "c22"): [PyModule(Path(), "c21")],
            },
            [
                (
                    PyModule(path=Path(), name="c11"),
                    PyModule(path=Path(), name="c12"),
                    PyModule(path=Path(), name="c11"),
                ),
                (
                    PyModule(path=Path(), name="c11"),
                    PyModule(path=Path(), name="c13"),
                    PyModule(path=Path(), name="c14"),
                    PyModule(path=Path(), name="c11"),
                ),
                (
                    PyModule(path=Path(), name="c21"),
                    PyModule(path=Path(), name="c22"),
                    PyModule(path=Path(), name="c21"),
                ),
            ],
        ),
    ],
)
def test_cycles(module_imports, expected_cycles):
    detector = DetectorImportCycles(module_imports)
    detector.detect()
    assert list(detector.detect()) == expected_cycles
