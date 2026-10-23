#!/usr/bin/env python3

from collections.abc import Mapping, Sequence
from typing import TypeVar

from networkx import DiGraph

T = TypeVar("T")


def make_digraph(graph: Mapping[T, Sequence[T]]) -> DiGraph:
    return DiGraph([(source, target) for source, targets in graph.items() for target in targets])
