#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Final, NamedTuple, Sequence


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


class ModuleFactory:
    def __init__(self, project_path: Path, packages: list[Path]) -> None:
        self._project_path = project_path
        self._pkgs_names = self._find_package_names(project_path, packages)

    @staticmethod
    def _find_package_names(project_path: Path, packages: list[Path]) -> dict[str, Path]:
        pkgs_names: dict[str, Path] = {}
        for pkg in packages:
            if (project_path / pkg / "__init__.py").exists():
                pkgs_names.setdefault(pkg.name, pkg)
                continue

            for parent in pkg.parents[::-1]:
                if (project_path / parent / "__init__.py").exists():
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
