#!/usr/bin/env python3

from py_import_cycles.digraph import make_digraph


def test_make_digraph_has_an_edge_per_import() -> None:
    assert sorted(make_digraph({"a": ["b", "c"], "b": ["c"]}).edges) == [
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
    ]
