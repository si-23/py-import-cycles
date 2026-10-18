#!/usr/bin/env python3

from collections.abc import Callable

from py_import_cycles.graphs import make_cycle_edges
from py_import_cycles.modules import PyModule


def test_make_cycle_edges(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")

    assert {(e.from_py_module, e.to_py_module) for e in make_cycle_edges([(a, b, a)])} == {
        (a, b),
        (b, a),
    }
