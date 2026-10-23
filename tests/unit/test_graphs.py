#!/usr/bin/env python3

from collections.abc import Callable
from pathlib import Path

import pytest

from py_import_cycles.graphs import (
    ImportEdge,
    _badness,
    _make_cycle_digraph,
    _normalize,
    make_cycle_edges,
    make_dfs_edges,
)
from py_import_cycles.modules import ModuleName, PyModule, PyModuleType


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
    assert _badness([("a", "b"), ("b", "c")]) == {("a", "b"): -0.5, ("b", "c"): 0.5}


def test_normalize() -> None:
    assert _normalize(0, -1, 1) == 0.5


@pytest.mark.parametrize("value, lower, higher", [(1, -1, 1), (-2, -1, 1), (0, 1, -1), (0, 0, 0)])
def test_normalize_rejects_value_outside_bounds(value: float, lower: float, higher: float) -> None:
    with pytest.raises(ValueError):
        _normalize(value, lower, higher)


def test_cycle_digraph_edge_carries_title_and_colour(
    make_py_module: Callable[[str], PyModule],
) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    digraph = _make_cycle_digraph(Path("cycles.gv"), [ImportEdge("1 (2)", a, b, "#123456")])
    assert '\t"pkg.a" -> "pkg.b" [label="1 (2)" color="#123456"]' in digraph.source.splitlines()


def test_cycle_digraph_draws_a_package_as_box(make_py_module: Callable[[str], PyModule]) -> None:
    a = make_py_module("a")
    package = PyModule(
        ModuleName("pkg"), a.package, a.package / "__init__.py", PyModuleType.REGULAR_PACKAGE
    )
    digraph = _make_cycle_digraph(Path("cycles.gv"), [ImportEdge("1 (2)", a, package, "#123456")])
    assert "\tpkg [shape=box]" in digraph.source.splitlines()


def test_make_dfs_edges_in_sorted_order(make_py_module: Callable[[str], PyModule]) -> None:
    a, b, c, d = (make_py_module(n) for n in "abcd")
    edges = make_dfs_edges([(a, b, a), (c, d, c), (b, c, b)])
    assert [(e.from_py_module, e.to_py_module) for e in edges] == [
        (a, b),
        (b, a),
        (b, c),
        (c, b),
        (c, d),
        (d, c),
    ]


def test_make_cycle_edges_colours_are_reproducible(
    make_py_module: Callable[[str], PyModule],
) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    assert [e.edge_color for e in make_cycle_edges([(a, b, a)])] == [
        e.edge_color for e in make_cycle_edges([(a, b, a)])
    ]
