#!/usr/bin/env python3

from __future__ import annotations

import abc
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Final, Iterable

from .files import PyFile

_INIT_NAME = "__init__"


def _make_init_module_path(path: Path) -> Path:
    return path / f"{_INIT_NAME}.py"


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

    @property
    def parents(self) -> Sequence[ModuleName]:
        return [ModuleName(*self._parts[:idx]) for idx in range(1, len(self._parts))][::-1]

    def joinname(self, *names: str | ModuleName) -> ModuleName:
        return ModuleName(*self._parts, *names)


class Module(abc.ABC):
    def __init__(self, *, package: Path, path: Path, name: ModuleName) -> None:
        self._validate(path, name)
        self.package = package
        self.path = path
        self.name = name

    @abc.abstractmethod
    def _validate(self, path: Path, name: ModuleName) -> None:
        raise NotImplementedError()

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(path={str(self.path)}, name={str(self.name)})"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Module):
            return NotImplemented
        return self.name == other.name

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Module):
            return NotImplemented
        return self.name < other.name

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Module):
            return NotImplemented
        return self.name > other.name

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def __ge__(self, other: object) -> bool:
        return self > other or self == other


class RegularPackage(Module):
    def _validate(self, path: Path, name: ModuleName) -> None:
        if path.with_suffix("").name != _INIT_NAME:
            raise ValueError(path)

        if not name.parts or name.parts[-1] == _INIT_NAME:
            raise ValueError(name)


class NamespacePackage(Module):
    def _validate(self, path: Path, name: ModuleName) -> None:
        if path.with_suffix("").name == _INIT_NAME:
            raise ValueError(path)

        if name.parts and name.parts[-1] == _INIT_NAME:
            raise ValueError(name)


class PyModule(Module):
    def _validate(self, path: Path, name: ModuleName) -> None:
        if path.with_suffix("").name == _INIT_NAME:
            raise ValueError(path)

        if name.parts and name.parts[-1] == _INIT_NAME:
            raise ValueError(name)


def make_modules_from_py_files(
    py_files: Iterable[PyFile],
) -> Iterator[RegularPackage | PyModule]:
    for py_file in py_files:
        if py_file.path.with_suffix("").name == _INIT_NAME:
            parts = py_file.path.with_suffix("").parent.relative_to(py_file.package).parts
            yield RegularPackage(
                package=py_file.package,
                path=py_file.path,
                name=ModuleName(py_file.package.name, *parts),
            )
        else:
            parts = py_file.path.with_suffix("").relative_to(py_file.package).parts
            yield PyModule(
                package=py_file.package,
                path=py_file.path,
                name=ModuleName(py_file.package.name, *parts),
            )


def _find_parent_modules(
    modules: Sequence[RegularPackage | PyModule],
) -> Iterator[RegularPackage | NamespacePackage]:
    for module in modules:
        for parent in module.path.parents:
            if not parent.is_relative_to(module.package):
                continue
            if (parent_init_path := _make_init_module_path(parent)).exists():
                # TODO same as above in make_modules_from_py_files
                parts = parent_init_path.with_suffix("").parent.relative_to(module.package).parts
                yield RegularPackage(
                    package=module.package,
                    path=parent_init_path,
                    name=ModuleName(module.package.name, *parts),
                )
            else:
                parts = parent.relative_to(module.package).parts
                yield NamespacePackage(
                    package=module.package,
                    path=parent,
                    name=ModuleName(module.package.name, *parts),
                )


def _make_packages_by_name(
    modules: Sequence[RegularPackage | NamespacePackage | PyModule],
) -> Mapping[str, RegularPackage | NamespacePackage | PyModule]:
    # TODO we need to distiguish between
    # - package abc
    # - package path/to/abc
    packages: dict[str, RegularPackage | NamespacePackage | PyModule] = {}
    for module in sorted(modules, key=lambda m: m.path.parts):
        packages.setdefault(str(module.name), module)
    return packages


class ModuleFactory:
    def __init__(self, project_path: Path, modules: Sequence[RegularPackage | PyModule]) -> None:
        self._project_path = project_path
        self._packages_by_name = _make_packages_by_name(
            list(_find_parent_modules(modules)) + list(modules)
        )

    def make_module_from_name(self, module_name: ModuleName) -> Module:
        if module_name.parts[-1] == "*":
            # TODO
            # from a.b import *
            # - If a.b is a pkg everything from a.b.__init__.py is loaded
            # - If a.b is a mod everything from a.b.py is loaded
            module_name = module_name.parent
        if module := self._packages_by_name.get(str(module_name)):
            return module
        raise ValueError(module_name)

    def make_parents_of_module(self, module: Module) -> Iterator[RegularPackage]:
        # Return the parents - ie. inits - of a module if they exist:
        # - a.b.c.__init__
        #   -> a.__init__, b.__init__
        # - a.b.c
        #   -> a.__init__, b.__init__, c.__init__
        if isinstance(module, RegularPackage):
            parents = module.name.parents[1:]
        else:
            parents = module.name.parents

        for parent in parents[::-1]:
            try:
                parent_module = self.make_module_from_name(parent)
            except ValueError:
                continue

            if isinstance(parent_module, RegularPackage):
                yield parent_module
