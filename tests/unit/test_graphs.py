#!/usr/bin/env python3

from collections.abc import Callable

import pytest

from py_import_cycles.graphs import badness, make_cycle_edges, make_dfs_edges, normalize
from py_import_cycles.modules import PyModule


def test_make_cycle_edges(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")

    assert {(e.from_py_module, e.to_py_module) for e in make_cycle_edges([(a, b, a)])} == {
        (a, b),
        (b, a),
    }


def test_make_dfs_edges(make_py_module: Callable[[str], PyModule]) -> None:
    a, b, c = (make_py_module(n) for n in "abc")

    assert {(e.from_py_module, e.to_py_module) for e in make_dfs_edges([(a, b, a), (b, c, b)])} == {
        (a, b),
        (b, a),
        (b, c),
        (c, b),
    }


def test_make_dfs_edges_colours_balanced_edges_blue(
    make_py_module: Callable[[str], PyModule],
) -> None:
    a, b = make_py_module("a"), make_py_module("b")

    assert {e.edge_color for e in make_dfs_edges([(a, b, a)])} == {"#0000ff"}


def test_make_dfs_edges_without_cycles() -> None:
    assert not make_dfs_edges([])


def test_badness_is_mean_degree_of_edge_vertices() -> None:
    assert badness([("a", "b"), ("b", "c")]) == {("a", "b"): -0.5, ("b", "c"): 0.5}


def test_normalize() -> None:
    assert normalize(0, -1, 1) == 0.5


@pytest.mark.parametrize("value, lower, higher", [(1, -1, 1), (-2, -1, 1), (0, 1, -1), (0, 0, 0)])
def test_normalize_rejects_value_outside_bounds(value: float, lower: float, higher: float) -> None:
    with pytest.raises(ValueError):
        normalize(value, lower, higher)
