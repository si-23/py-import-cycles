#!/usr/bin/env python3

from typing import Iterator, List, Mapping, Sequence, Set, TypeVar

from .type_defs import Comparable

T = TypeVar("T", bound=Comparable)


def depth_first_search(graph: Mapping[T, Sequence[T]]) -> Iterator[tuple[T, ...]]:
    visited: Set[T] = set()

    def _dfs_util(vertex_u: T, path: List[T]) -> Iterator[tuple[T, ...]]:
        if vertex_u in visited:
            return

        for vertex_v in graph.get(vertex_u, []):
            if vertex_v in path:
                yield tuple(path[path.index(vertex_v) :])
                continue

            yield from _dfs_util(vertex_v, path + [vertex_v])

        visited.add(vertex_u)

    for vertex in sorted(graph):
        yield from _dfs_util(vertex, [])
