#!/usr/bin/env python3

from typing import Iterator, Literal, Mapping, Sequence

from .dfs import depth_first_search
from .modules import Module
from .tarjan import strongly_connected_components


def detect_cycles(
    strategy: Literal["dfs", "tarjan"],
    graph: Mapping[Module, Sequence[Module]],
) -> Iterator[tuple[Module, ...]]:
    if strategy == "dfs":
        return depth_first_search(graph)
    if strategy == "tarjan":
        return (scc for scc in strongly_connected_components(graph) if len(scc) > 1)
    raise NotImplementedError()
