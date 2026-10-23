#!/usr/bin/env python3

from collections.abc import Callable

from py_import_cycles.cli import _sort_cycles
from py_import_cycles.modules import PyModule


def test_sort_cycles_of_equal_length_and_start_by_all_modules(
    make_py_module: Callable[[str], PyModule],
) -> None:
    a, b, c = (make_py_module(n) for n in "abc")
    assert _sort_cycles([(a, c, b), (a, b), (a, b, c)]) == [(a, b), (a, b, c), (a, c, b)]
