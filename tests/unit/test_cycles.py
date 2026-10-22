#!/usr/bin/env python3

from collections.abc import Callable

from py_import_cycles.cycles import make_strategies
from py_import_cycles.modules import PyModule


def test_johnson_respects_length_bound(make_py_module: Callable[[str], PyModule]) -> None:
    a, b, c = (make_py_module(n) for n in "abc")
    graph = {a: [b], b: [a, c], c: [a]}

    assert list(make_strategies(2)["johnson"].detect_cycles(graph)) == [(a, b)]
