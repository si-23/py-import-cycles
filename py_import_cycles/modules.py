#!/usr/bin/env python3

from __future__ import annotations

from collections.abc import Sequence
from enum import auto, Enum
from pathlib import Path
from string import ascii_letters, digits
from typing import Final


def _parse_part(part: str) -> str:
    # A variable name must start with a letter or the underscore character.
    # A variable name cannot start with a number.
    # A variable name can only contain alpha-numeric characters and underscores (A-z, 0-9, and _ )
    if not part:
        raise ValueError(part)
    # TODO remove "*"; at the moment this is handled later in "make_module_from_name"
    if part[0] not in ascii_letters + "_*":
        raise ValueError(part[0])
    if not set(part[1:]).issubset(ascii_letters + digits + "_*"):
        raise ValueError(part[1:])
    return part


class ModuleName:
    """This class is inspired by pathlib.Path"""

    def __init__(self, *parts: str | ModuleName) -> None:
        self._parts: Final[tuple[str, ...]] = tuple(
            _parse_part(entry)
            for part in parts
            for entry in (part.parts if isinstance(part, ModuleName) else part.split("."))
        )

    def __str__(self) -> str:
        return ".".join(self._parts)

    def __hash__(self) -> int:
        return hash(self._parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts == other._parts

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts < other._parts

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts > other._parts

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def __ge__(self, other: object) -> bool:
        return self > other or self == other

    @property
    def parts(self) -> Sequence[str]:
        return self._parts

    @property
    def parent(self) -> ModuleName:
        return ModuleName(*self._parts[:-1])

    def joinname(self, *names: str | ModuleName) -> ModuleName:
        return ModuleName(*self._parts, *names)


class PyModuleType(Enum):
    NAMESPACE_PACKAGE = auto()
    REGULAR_PACKAGE = auto()
    MODULE = auto()


def _compute_py_module_type(path: Path) -> PyModuleType:
    if path.is_dir():
        return PyModuleType.NAMESPACE_PACKAGE
    if path.is_file():
        if path.name == "__init__.py":
            return PyModuleType.REGULAR_PACKAGE
        if path.suffix == ".py":
            return PyModuleType.MODULE
    raise ValueError(path)


def _compute_py_module_name(package: Path, path: Path, py_module_type: PyModuleType) -> ModuleName:
    module_name = ModuleName(package.name)
    ref_path = path.parent if py_module_type is PyModuleType.REGULAR_PACKAGE else path
    if not ref_path.is_relative_to(package) or (rel_path := ref_path.relative_to(package)) == Path(
        "."
    ):
        return module_name
    return module_name.joinname(*rel_path.with_suffix("").parts)


class PyModule:
    def __init__(self, package: Path, path: Path) -> None:
        self.package: Final[Path] = package
        self.path: Final[Path] = path
        self.type: Final[PyModuleType] = _compute_py_module_type(path)
        self.name: Final[ModuleName] = _compute_py_module_name(package, path, self.type)

    def __str__(self) -> str:
        match self.type:
            case PyModuleType.NAMESPACE_PACKAGE:
                return f"{self.name}/"
            case PyModuleType.REGULAR_PACKAGE:
                return f"{self.name}.__init__"
            case PyModuleType.MODULE:
                return f"{self.name}"

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PyModule):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PyModule):
            return NotImplemented
        return self.name < other.name

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PyModule):
            return NotImplemented
        return self.name > other.name

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def __ge__(self, other: object) -> bool:
        return self > other or self == other
