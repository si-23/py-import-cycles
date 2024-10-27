#!/usr/bin/env python3

from __future__ import annotations

import abc
from collections.abc import Iterator, Sequence
from pathlib import Path
from string import ascii_letters, digits
from typing import Final

from .log import logger

_INIT_NAME = "__init__"


def _make_init_module_path(path: Path) -> Path:
    return path / f"{_INIT_NAME}.py"


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

    @property
    def parents(self) -> Sequence[ModuleName]:
        return [ModuleName(*self._parts[:idx]) for idx in range(1, len(self._parts))][::-1]

    def joinname(self, *names: str | ModuleName) -> ModuleName:
        return ModuleName(*self._parts, *names)


class Module(abc.ABC):
    def __init__(self, *, path: Path, name: ModuleName) -> None:
        self._validate(path, name)
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


class ModuleFactory:
    def __init__(self, project_path: Path, packages: Sequence[Path]) -> None:
        self._project_path = project_path
        self._pkgs_names = self._find_package_names(project_path, packages)

    @staticmethod
    def _find_package_names(project_path: Path, packages: Sequence[Path]) -> dict[str, Path]:
        pkgs_names: dict[str, Path] = {}
        for pkg in packages:
            if _make_init_module_path(project_path / pkg).exists():
                pkgs_names.setdefault(pkg.name, pkg)
                continue

            for parent in pkg.parents[::-1]:
                if _make_init_module_path(project_path / parent).exists():
                    pkgs_names.setdefault(parent.name, pkg)
                    break

        return pkgs_names

    def make_module_from_name(self, module_name: ModuleName) -> Module:
        def _get_sanitized_rel_module_path(module_name: ModuleName) -> Path:
            if module_name and module_name.parts[0] in self._pkgs_names:
                return Path(*self._pkgs_names[module_name.parts[0]].parts) / Path(
                    *module_name.parts[1:]
                )
            return Path(*module_name.parts)

        if module_name.parts[-1] == "*":
            # Note:
            # from a.b import *
            # - If a.b is a pkg everything from a.b.__init__.py is loaded
            # - If a.b is a mod everything from a.b.py is loaded
            # -> Getting the "right" filepath is already handled below
            module_name = module_name.parent

        module_path = self._project_path.joinpath(_get_sanitized_rel_module_path(module_name))

        if module_path.is_dir():
            if (init_module_path := _make_init_module_path(module_path)).exists():
                return RegularPackage(
                    path=init_module_path,
                    name=module_name,
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
            module_path = module_path.with_suffix("")
            for name, path in self._pkgs_names.items():
                abs_module_path = self._project_path.joinpath(path)
                if module_path.is_relative_to(abs_module_path):
                    return ModuleName(name, *module_path.relative_to(abs_module_path).parts)
            return ModuleName(*module_path.relative_to(self._project_path).parts)

        module_name = _get_sanitized_module_name(module_path)

        if module_path.is_dir():
            return NamespacePackage(
                path=module_path,
                name=module_name,
            )

        if module_path.is_file() and module_path.suffix == ".py":
            if module_path.stem == _INIT_NAME:
                return RegularPackage(
                    path=module_path,
                    name=ModuleName(*module_name.parts[:-1]),
                )

            return PyModule(
                path=module_path,
                name=module_name,
            )

        raise ValueError(module_path)

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
            except ValueError as e:
                logger.debug("Cannot make module from module name: %s: %s", parent, e)
                continue

            if isinstance(parent_module, RegularPackage):
                yield parent_module
