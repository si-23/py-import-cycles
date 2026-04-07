#!/usr/bin/env python3

from collections.abc import Hashable, Iterator, Mapping, Sequence
from typing import Tuple, TypeVar

from networkx import DiGraph, strongly_connected_components

T = TypeVar("T", bound=Hashable)


def tarjan(graph: Mapping[T, Sequence[T]]) -> Iterator[Tuple[T, ...]]:
    for scc in strongly_connected_components(
        DiGraph([(v, w) for v, vertices in graph.items() for w in vertices])
    ):
        if len(scc) > 1:
            yield tuple(scc)
