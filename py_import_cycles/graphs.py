#!/usr/bin/env python3

import itertools
import random
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, TypeVar

from graphviz import Digraph

from .log import logger
from .modules import PyModule, PyModuleType
from .type_defs import Comparable


class ImportEdge(NamedTuple):
    title: str
    from_py_module: PyModule
    to_py_module: PyModule
    edge_color: str


T = TypeVar("T")
TC = TypeVar("TC", bound=Comparable)


def _get_shape(py_module: PyModule) -> str:
    return "" if py_module.type is PyModuleType.MODULE else "box"


def dedup_edges(cycles: Iterable[tuple[TC, ...]]) -> Sequence[tuple[TC, TC]]:
    edges: set[tuple[TC, TC]] = set()
    for cycle in cycles:
        edges |= frozenset(itertools.pairwise(cycle))
    return list(edges)


def count_degree(edges: Sequence[tuple[T, T]]) -> Mapping[T, int]:
    degrees: defaultdict[T, int] = defaultdict(int)
    for edge in edges:
        degrees[edge[0]] -= 1
        degrees[edge[1]] += 1
    return degrees


def badness(edges: Sequence[tuple[T, T]]) -> Mapping[tuple[T, T], float]:
    degree = count_degree(edges)
    return {edge: 0.5 * (degree[edge[0]] + degree[edge[1]]) for edge in edges}


def normalize(value: float, lower: float, higher: float) -> float:
    if not lower <= value < higher:
        raise ValueError(f"{value} is not within bounds")
    return (value - lower) / (higher - lower)


def _rgb(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def make_dfs_edges(
    cycles: Sequence[tuple[PyModule, ...]],
) -> Sequence[ImportEdge]:
    edges = badness(dedup_edges(cycles))
    if not (edges_values := edges.values()):
        return []

    bound = max(abs(min(edges_values)), abs(max(edges_values)))

    out = []
    for edge, value in edges.items():
        nn = int(255 * normalize(value, -bound, bound + 1))
        assert 0 <= nn < 256
        if value < 0:
            color = _rgb(0, 255 - nn, nn)
        else:
            color = _rgb(nn, 0, 255 - nn)
        out.append(ImportEdge(str(value), edge[0], edge[1], color))
    return out


def make_cycle_edges(
    import_cycles: Sequence[tuple[PyModule, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles, start=1):
        color = _rgb(
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        start_py_module = import_cycle[0]
        for next_py_module in import_cycle[1:]:
            edges.add(
                ImportEdge(
                    f"{str(nr)} ({len(import_cycle) - 1})",
                    start_py_module,
                    next_py_module,
                    color,
                )
            )
            start_py_module = next_py_module
    return sorted(edges)


def _make_cycle_digraph(filepath: Path, edges: Sequence[ImportEdge]) -> Digraph:
    digraph = Digraph("unix", filename=filepath)
    for edge in edges:
        tail, head = str(edge.from_py_module.name), str(edge.to_py_module.name)
        digraph.node(tail, shape=_get_shape(edge.from_py_module))
        digraph.node(head, shape=_get_shape(edge.to_py_module))
        digraph.edge(tail, head, edge.title, color=edge.edge_color)
    return digraph


def make_graph(filepath: Path, edges: Sequence[ImportEdge]) -> None:
    sys.stderr.write(f"Write graph data to {filepath}\n")

    if not edges:
        logger.debug("No such edges for graph")
        return

    digraph = _make_cycle_digraph(filepath, edges)
    digraph.unflatten(stagger=50)
    digraph.view()
