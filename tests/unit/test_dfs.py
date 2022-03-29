#!/usr/bin/env python3

from typing import Mapping, Sequence, Tuple

import pytest

from project.main import detect_cycles  # pylint: disable=import-error


@pytest.mark.parametrize(
    "graph, cycles",
    [
        ({}, []),
        (
            {
                "a": ["b"],
            },
            [],
        ),
        (
            {
                "a": ["b"],
                "b": ["a"],
            },
            [
                ("b", "a"),
            ],
        ),
        (
            {
                "m1": ["a"],
                "m2": ["a"],
                "a": ["b"],
                "b": ["a"],
            },
            [
                ("b", "a"),
            ],
        ),
        (
            {
                "m1": ["a"],
                "m2": ["b"],
                "a": ["b"],
                "b": ["a"],
            },
            [
                ("b", "a"),
            ],
        ),
        (
            {
                "m": ["c11", "c21"],
                "c11": ["c12"],
                "c12": ["c11"],
                "c21": ["c22"],
                "c22": ["c21"],
            },
            [
                ("c12", "c11"),
                ("c22", "c21"),
            ],
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
                ("c12", "c11"),
                ("c11", "c13", "c14"),
                ("c22", "c21"),
            ],
        ),
    ],
)
def test_cycles_str(
    graph: Mapping[str, Sequence[str]],
    cycles: Sequence[Tuple[str, ...]],
) -> None:
    assert list(detect_cycles("dfs", graph)) == cycles
