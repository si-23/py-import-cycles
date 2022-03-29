#!/usr/bin/env python3

from __future__ import annotations

import abc
from typing import Protocol, TypeVar


class Comparable(Protocol):
    @abc.abstractmethod
    def __lt__(self: T, other: T) -> bool:
        ...


T = TypeVar("T", bound=Comparable)
