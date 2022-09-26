#!/usr/bin/env python3

import itertools
import random
from collections import defaultdict
from typing import DefaultDict, Iterable, Iterator, Literal, Mapping, NamedTuple, Sequence, TypeVar

from graphviz import Digraph

from .files import OutputsFilepaths
from .modules import Module, PyModule
from .type_defs import Comparable


class ImportEdge(NamedTuple):
    title: str
    from_module: Module
    to_module: Module
    edge_color: str


T = TypeVar("T")
TC = TypeVar("TC", bound=Comparable)


def make_graph(
    edges: Sequence[ImportEdge],
    outputs_filepaths: OutputsFilepaths,
) -> Digraph:
    d = Digraph("unix", filename=outputs_filepaths.graph)

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(
                str(edge.from_module.name),
                shape=_get_shape(edge.from_module),
            )

            ds.node(
                str(edge.to_module.name),
                shape=_get_shape(edge.to_module),
            )

            ds.attr("edge", color=edge.edge_color)

            if edge.title:
                ds.edge(str(edge.from_module.name), str(edge.to_module.name), edge.title)
            else:
                ds.edge(str(edge.from_module.name), str(edge.to_module.name))

    return d.unflatten(stagger=50)


def _get_shape(module: Module) -> str:
    return "" if isinstance(module, PyModule) else "box"


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


def make_edges(
    opt_graph: Literal["all", "only-cycles"],
    opt_strategy: Literal["dfs", "tarjan"],
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    if opt_graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if opt_graph == "only-cycles":
        if opt_strategy == "dfs":
            return _make_dfs_import_edges(import_cycles)
        return _make_only_cycles_edges(import_cycles)

    raise NotImplementedError(f"Unknown graph option: {opt_graph}")


def _make_all_edges(
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
    for module, imported_modules in imports_by_module.items():
        for imported_module in imported_modules:
            edges.add(
                ImportEdge(
                    "",
                    module,
                    imported_module,
                    (
                        "red"
                        if _has_cycle(module, imported_module, import_cycles) is None
                        else "black"
                    ),
                )
            )
    return sorted(edges)


def _has_cycle(
    module: Module,
    imported_module: Module,
    import_cycles: Sequence[tuple[Module, ...]],
) -> bool:
    for import_cycle in import_cycles:
        try:
            idx = import_cycle.index(module)
        except ValueError:
            continue

        if import_cycle[idx + 1] == imported_module:
            return True
    return False


def _make_dfs_import_edges(
    cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges = badness(dedup_edges(cycles))
    edges_values = edges.values()
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
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles, start=1):
        color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        start_module = import_cycle[0]
        for next_module in import_cycle[1:]:
            edges.add(
                ImportEdge(
                    f"{str(nr)} ({len(import_cycle) - 1})",
                    start_module,
                    next_module,
                    color,
                )
            )
            start_module = next_module
    return sorted(edges)
