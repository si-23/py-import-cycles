#!/usr/bin/env python3

from collections.abc import Iterator, Mapping, Sequence, Set
from typing import TypeVar

from networkx import DiGraph, condensation, find_cycle, topological_sort
from networkx.exception import NetworkXNoCycle

from .digraph import make_digraph
from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def _make_cycle(cyclic_edges: Sequence[tuple[T, T]]) -> tuple[T, ...]:
    return tuple(source for source, _target in cyclic_edges)


def _make_cyclic_rotations(cycle: tuple[T, ...]) -> Sequence[tuple[T, ...]]:
    return [cycle[i:] + cycle[:i] for i in range(1, len(cycle))]


def _is_cyclic(G: DiGraph, members: Set[object]) -> bool:
    return len(members) > 1 or any(G.has_edge(member, member) for member in members)


def _vertices_reaching_a_cycle(G: DiGraph) -> Set[object]:
    condensed = condensation(G)
    reaching: set[int] = set()
    for component in reversed(list(topological_sort(condensed))):
        if _is_cyclic(G, condensed.nodes[component]["members"]) or any(
            successor in reaching for successor in condensed.successors(component)
        ):
            reaching.add(component)
    return {vertex for component in reaching for vertex in condensed.nodes[component]["members"]}


def dfs(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    known_cycles: set[tuple[T, ...]] = set()

    G = make_digraph(graph)
    reaching = _vertices_reaching_a_cycle(G)
    for vertex in sorted(vertex for vertex in graph if vertex in reaching):
        try:
            cyclic_edges = find_cycle(G, source=vertex)
        except NetworkXNoCycle:
            continue

        if (cycle := _make_cycle(cyclic_edges)) not in known_cycles:
            known_cycles.add(cycle)
            for rot in _make_cyclic_rotations(cycle):
                known_cycles.add(rot)
            yield cycle
