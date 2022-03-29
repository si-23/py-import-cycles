#!/usr/bin/env python3

from pathlib import Path
from typing import Mapping, Sequence, Tuple

import pytest

from project.main import detect_cycles, Module, PyModule  # pylint: disable=import-error


@pytest.mark.parametrize(
    "graph, cycles",
    [
        ({}, []),
        ({"a": ["b"]}, []),
        (
            {"a": ["b"], "b": ["a"]},
            [("a", "b", "a")],
        ),
        (
            {"m1": ["a"], "m2": ["a"], "a": ["b"], "b": ["a"]},
            [("a", "b", "a")],
        ),
        (
            {"m1": ["a"], "m2": ["b"], "a": ["b"], "b": ["a"]},
            [("a", "b", "a")],
        ),
        (
            {
                "m": ["c11", "c21"],
                "c11": ["c12"],
                "c12": ["c11"],
                "c21": ["c22"],
                "c22": ["c21"],
            },
            [("c11", "c12", "c11"), ("c21", "c22", "c21")],
        ),
        (
            {
                "m": ["c11", "c21"],
                "c11": ["c12", "c13"],
                "c12": ["c11"],
                "c13": ["c14"],
                "c14": ["c11"],
                "c21": ["c22"],
                "c22": ["c21"],
            },
            [
                ("c11", "c12", "c11"),
                ("c11", "c13", "c14", "c11"),
                ("c21", "c22", "c21"),
            ],
        ),
    ],
)
def test_cycles_str(
    graph: Mapping[str, Sequence[str]],
    cycles: Sequence[Tuple[str, ...]],
) -> None:
    assert list(detect_cycles("dfs", graph)) == cycles


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
def test_cycles_pymodule(
    module_imports: Mapping[Module, Sequence[Module]],
    expected_cycles: Sequence[Tuple[Module, ...]],
) -> None:
    assert list(detect_cycles("dfs", module_imports)) == expected_cycles
