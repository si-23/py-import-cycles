#!/usr/bin/env python3

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import partial

from .dfs import dfs
from .graphs import ImportEdge, make_cycle_edges, make_dfs_edges
from .johnson import johnson
from .modules import PyModule
from .tarjan import tarjan


@dataclass(frozen=True)
class Strategy:
    detect_cycles: Callable[[Mapping[PyModule, Sequence[PyModule]]], Iterator[tuple[PyModule, ...]]]
    make_edges: Callable[[Sequence[tuple[PyModule, ...]]], Sequence[ImportEdge]]


def make_strategies(length_bound: int | None) -> Mapping[str, Strategy]:
    return {
        "dfs": Strategy(dfs, make_dfs_edges),
        "tarjan": Strategy(tarjan, make_cycle_edges),
        "johnson": Strategy(partial(johnson, length_bound), make_cycle_edges),
    }
