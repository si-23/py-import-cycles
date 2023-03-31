#!/usr/bin/env python3

from typing import Iterator, Mapping, Sequence, TypeVar

from networkx import DiGraph, simple_cycles

from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def johnson(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    for sc in simple_cycles(DiGraph([(v, w) for v, vertices, in graph.items() for w in vertices])):
        yield tuple(sc)
