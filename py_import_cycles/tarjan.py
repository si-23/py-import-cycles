#!/usr/bin/env python3

from collections.abc import Hashable, Iterator, Mapping, Sequence
from typing import TypeVar

from networkx import strongly_connected_components

from .digraph import make_digraph

T = TypeVar("T", bound=Hashable)


def tarjan(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    for scc in strongly_connected_components(make_digraph(graph)):
        if len(scc) > 1:
            yield tuple(scc)
