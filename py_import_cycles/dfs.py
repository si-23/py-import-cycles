#!/usr/bin/env python3

from collections.abc import Iterator, Mapping, Sequence
from typing import TypeVar

from networkx import find_cycle
from networkx.exception import NetworkXNoCycle

from .digraph import make_digraph
from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def _make_cycle(cyclic_edges: Sequence[tuple[T, T]]) -> tuple[T, ...]:
    return tuple(source for source, _target in cyclic_edges)


def _make_cyclic_rotations(cycle: tuple[T, ...]) -> Sequence[tuple[T, ...]]:
    return [cycle[i:] + cycle[:i] for i in range(1, len(cycle))]


def dfs(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    known_cycles: set[tuple[T, ...]] = set()

    G = make_digraph(graph)
    for vertex in sorted(graph):
        try:
            cyclic_edges = find_cycle(G, source=vertex)
        except NetworkXNoCycle:
            continue

        if (cycle := _make_cycle(cyclic_edges)) not in known_cycles:
            known_cycles.add(cycle)
            for rot in _make_cyclic_rotations(cycle):
                known_cycles.add(rot)
            yield cycle
