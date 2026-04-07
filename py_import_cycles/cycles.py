#!/usr/bin/env python3

from collections.abc import Iterator, Mapping, Sequence
from typing import Literal

from .dfs import depth_first_search
from .johnson import johnson
from .modules import PyModule
from .tarjan import strongly_connected_components


def detect_cycles(
    strategy: Literal["dfs", "tarjan"],
    length_bound: int | None,
    graph: Mapping[PyModule, Sequence[PyModule]],
) -> Iterator[tuple[PyModule, ...]]:
    if strategy == "dfs":
        return depth_first_search(graph)
    if strategy == "tarjan":
        return (scc for scc in strongly_connected_components(graph) if len(scc) > 1)
    if strategy == "johnson":
        return johnson(length_bound, graph)
    raise NotImplementedError()
