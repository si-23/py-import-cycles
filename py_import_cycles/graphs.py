#!/usr/bin/env python3

import itertools
import random
import sys
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import DefaultDict, Iterable, Literal, NamedTuple, TypeVar

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


def make_graph(
    filepath: Path,
    opt_strategy: Literal["dfs", "tarjan"],
    import_cycles: Sequence[tuple[PyModule, ...]],
) -> None:
    sys.stderr.write(f"Write graph data to {filepath}\n")

    if not (edges := _make_edges(opt_strategy, import_cycles)):
        logger.debug("No such edges for graph")
        return

    d = Digraph("unix", filename=filepath)

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(
                str(edge.from_py_module.name),
                shape=_get_shape(edge.from_py_module),
            )

            ds.node(
                str(edge.to_py_module.name),
                shape=_get_shape(edge.to_py_module),
            )

            ds.attr("edge", color=edge.edge_color)

            if edge.title:
                ds.edge(
                    str(edge.from_py_module.name),
                    str(edge.to_py_module.name),
                    edge.title,
                )
            else:
                ds.edge(str(edge.from_py_module.name), str(edge.to_py_module.name))

    d.unflatten(stagger=50)
    d.view()


def _get_shape(py_module: PyModule) -> str:
    return "" if py_module.type is PyModuleType.MODULE else "box"


def pairwise(iterable: Iterable[T]) -> Iterator[tuple[T, T]]:
    # pairwise('ABCDEFG') --> AB BC CD DE EF FG
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def dedup_edges(cycles: Iterable[tuple[TC, ...]]) -> Sequence[tuple[TC, TC]]:
    edges: set[tuple[TC, TC]] = set()
    for cycle in cycles:
        edges |= frozenset(pairwise(cycle))
    return list(edges)


def count_degree(edges: Sequence[tuple[T, T]]) -> Mapping[T, int]:
    degrees: DefaultDict[T, int] = defaultdict(int)
    for edge in edges:
        degrees[edge[0]] -= 1
        degrees[edge[1]] += 1
    return degrees


def badness(edges: Sequence[tuple[T, T]]) -> Mapping[tuple[T, T], float]:
    # Get some idea of the badness of an edge by computing
    # the average of the degrees of its vertices.
    degree = count_degree(edges)
    return {edge: 0.5 * (degree[edge[0]] + degree[edge[1]]) for edge in edges}


def normalize(value: float, lower: float, higher: float) -> float:
    if not lower <= value < higher:
        raise ValueError(f"{value} is not within bounds")
    if higher < lower:
        raise ValueError("bounds are reverted")
    if higher == lower:
        raise ValueError("must use different bounds")
    return (value - lower) / (higher - lower)


def _make_edges(
    opt_strategy: Literal["dfs", "tarjan"],
    import_cycles: Sequence[tuple[PyModule, ...]],
) -> Sequence[ImportEdge]:
    if opt_strategy == "dfs":
        return _make_dfs_import_edges(import_cycles)
    return _make_only_cycles_edges(import_cycles)


def _make_dfs_import_edges(
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
            color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
                0, 255 - nn, nn
            )
        else:
            color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
                nn, 0, 255 - nn
            )
        out.append(ImportEdge(str(value), edge[0], edge[1], color))
    return out


def _make_only_cycles_edges(
    import_cycles: Sequence[tuple[PyModule, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles, start=1):
        color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
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
