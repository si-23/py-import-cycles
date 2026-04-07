#!/usr/bin/env python3

from py_import_cycles.tarjan import tarjan


def test_empty() -> None:
    assert not list(tarjan({}))


def test_tree() -> None:
    graph = {
        1: [11, 12, 13],
        11: [111, 112, 113],
        111: [1111, 1112, 1113],
        12: [121, 122, 123],
        13: [131, 132, 133],
        2: [21, 22, 23],
        3: [31, 32, 33],
    }
    assert sorted(tarjan(graph)) == []


def test_dag() -> None:
    graph = {
        1: [11, 12, 2],
        11: [111, 112, 121, 122],
        12: [121, 122],
        121: [111, 112],
        2: [21, 22],
    }
    assert sorted(tarjan(graph)) == []


def test_graph_with_one_cycles() -> None:
    graph = {
        1: [11, 12, 13, 1],
        11: [111, 112, 1],
        111: [1111, 1112, 1],
        12: [121, 122, 111],
    }
    assert sorted(tarjan(graph)) == [
        (1, 11, 12, 111),
    ]


def test_graph_with_more_cycles() -> None:
    graph = {
        1: [11, 12],
        11: [111, 112],
        111: [11],
        112: [1],
        2: [21, 22],
        22: [221, 222, 223],
        222: [2, 22],
        223: [2, 22],
        3: [31, 32, 33],
        33: [333],
        333: [31],
        31: [3],
    }
    assert sorted(tarjan(graph)) == [
        (2, 222, 22, 223),
        (33, 3, 333, 31),
        (112, 1, 11, 111),
    ]
