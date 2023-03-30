#!/usr/bin/env python3

from typing import Iterator, Mapping, Sequence, Set, TypeVar

from networkx import DiGraph, find_cycle
from networkx.exception import NetworkXNoCycle

from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def depth_first_search(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    known_cycles: Set[tuple[T, ...]] = set()

    def _make_cycle(cyclic_edges: Sequence[tuple[T, T, str]]) -> tuple[T, ...]:
        # find_cycle returns:
        # [
        #     (e0, e1, ORIENTATION),
        #     (e1, e2, ORIENTATION),
        #     ...
        #     (eX-1, eX, ORIENTATION),
        #     (eX, e0, ORIENTATION),
        # ]
        return tuple(cyclic_edges[0][:-1] + tuple(ce[1] for ce in cyclic_edges[1:-1]))

    G = DiGraph([(v, w) for v, vertices, in graph.items() for w in vertices])
    for vertex in sorted(graph):
        try:
            cyclic_edges = find_cycle(G, source=vertex, orientation="original")
        except NetworkXNoCycle:
            continue

        if (cycle := _make_cycle(cyclic_edges)) not in known_cycles:
            known_cycles.add(cycle)
            known_cycles.add(cycle[::-1])
            yield cycle
