#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Mapping, NamedTuple, Sequence


class ModuleName:
    """This class is inspired by pathlib.Path"""

    def __init__(self, *parts: str | ModuleName) -> None:
        self._parts: Final[tuple[str, ...]] = tuple(
            entry
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

    @property
    def parts(self) -> Sequence[str]:
        return self._parts

    @property
    def parent(self) -> ModuleName:
        return ModuleName(*self._parts[:-1])

    @property
    def parents(self) -> Sequence[ModuleName]:
        return [ModuleName(*self._parts[:idx]) for idx in range(1, len(self._parts))][::-1]

    def joinname(self, *names: str | ModuleName) -> ModuleName:
        return ModuleName(*self._parts, *names)


class RegularPackage(NamedTuple):
    path: Path
    name: ModuleName


class NamespacePackage(NamedTuple):
    path: Path
    name: ModuleName


class PyModule(NamedTuple):
    path: Path
    name: ModuleName


Module = RegularPackage | NamespacePackage | PyModule


@dataclass(frozen=True)
class ModuleFactory:
    _project_path: Path
    _mapping: Mapping[str, str]

    def make_module_from_name(self, module_name: ModuleName) -> Module:
        def _get_sanitized_module_name(module_name: ModuleName) -> ModuleName:
            for key, value in self._mapping.items():
                if value in module_name.parts:
                    return ModuleName(key).joinname(module_name)
            return module_name

        if module_name.parts[-1] == "*":
            # Note:
            # from a.b import *
            # - If a.b is a pkg everything from a.b.__init__.py is loaded
            # - If a.b is a mod everything from a.b.py is loaded
            # -> Getting the "right" filepath is already handled below
            module_name = module_name.parent

        module_path = self._project_path.joinpath(
            Path(*_get_sanitized_module_name(module_name).parts)
        )

        if module_path.is_dir():
            if (init_module_path := module_path / "__init__.py").exists():
                return RegularPackage(
                    path=init_module_path,
                    name=module_name.joinname("__init__"),
                )

            return NamespacePackage(
                path=module_path,
                name=module_name,
            )

        if (py_module_path := module_path.with_suffix(".py")).exists():
            return PyModule(
                path=py_module_path,
                name=module_name,
            )

        raise ValueError(module_name)

    def make_module_from_path(self, module_path: Path) -> Module:
        def _get_sanitized_module_name(module_path: Path) -> ModuleName:
            parts = module_path.relative_to(self._project_path).with_suffix("").parts
            for key, value in self._mapping.items():
                if key == parts[0] and value in parts[1:]:
                    return ModuleName(*parts[1:])
            return ModuleName(*parts)

        module_name = _get_sanitized_module_name(module_path)

        if module_path.is_dir():
            return NamespacePackage(
                path=module_path,
                name=module_name,
            )

        if module_path.is_file() and module_path.suffix == ".py":
            if module_path.stem == "__init__":
                return RegularPackage(
                    path=module_path,
                    name=module_name,
                )

            return PyModule(
                path=module_path,
                name=module_name,
            )

        raise ValueError(module_path)
