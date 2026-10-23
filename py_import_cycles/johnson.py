#!/usr/bin/env python3

from collections.abc import Iterator, Mapping, Sequence
from typing import TypeVar

from networkx import simple_cycles

from .digraph import make_digraph
from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def johnson(length_bound: int | None, graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    for sc in simple_cycles(
        make_digraph(graph),
        length_bound=length_bound,
    ):
        yield tuple(sc)
