#!/usr/bin/env python3

from typing import Mapping, Sequence, Tuple

import pytest

from py_import_cycles.dfs import depth_first_search  # pylint: disable=import-error


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
                ("a", "b"),
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
                ("a", "b"),
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
                ("c11", "c12"),
                ("c21", "c22"),
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
                ("c11", "c12"),
                ("c21", "c22"),
            ],
        ),
    ],
)
def test_cycles_str(
    graph: Mapping[str, Sequence[str]],
    cycles: Sequence[Tuple[str, ...]],
) -> None:
    assert list(depth_first_search(graph)) == cycles
