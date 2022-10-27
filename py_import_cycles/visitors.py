#!/usr/bin/env python3

import ast
import sys
from pathlib import Path
from typing import Iterator, NamedTuple, Sequence

from .log import logger
from .modules import Module, ModuleFactory, ModuleName, NamespacePackage, RegularPackage

STDLIB_OR_BUILTIN = sys.stdlib_module_names.union(sys.builtin_module_names)
ImportSTMT = ast.Import | ast.ImportFrom


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self) -> None:
        self._import_stmts: list[ImportSTMT] = []

    @property
    def import_stmts(self) -> Sequence[ImportSTMT]:
        return self._import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._import_stmts.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._import_stmts.append(node)


class ImportStmtsParser:
    def __init__(
        self,
        module_factory: ModuleFactory,
        base_module: Module,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._module_factory = module_factory
        self._base_module = base_module
        self._import_stmts = import_stmts

    def get_imports(self) -> Iterator[Module]:
        for module_name in self._get_module_names():
            if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
                continue

            try:
                module = self._module_factory.make_module_from_name(module_name)
                self._validate_module(module)
            except ValueError:
                continue

            yield module

    def _get_module_names(self) -> Iterator[ModuleName]:
        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                yield from self._get_module_names_of_import_stmt(import_stmt)

            elif isinstance(import_stmt, ast.ImportFrom):
                yield from self._get_module_names_of_import_from_stmt(import_stmt)

    # -----ast.Import-----

    def _get_module_names_of_import_stmt(self, import_stmt: ast.Import) -> Iterator[ModuleName]:
        for alias in import_stmt.names:
            yield ModuleName(alias.name)

    # -----ast.ImportFrom-----

    def _get_module_names_of_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterator[ModuleName]:
        try:
            yield (anchor := self._get_anchor(import_from_stmt))
        except ValueError:
            return

        for alias in import_from_stmt.names:
            # Add packages/modules to above prefix:
            # 1 -> ../a/b/c{.py,/}
            # 2 -> ../BASE/c{.py,/}
            # 3 -> ../BASE/a/b/c{.py,/}
            # 4 -> ../BASE_PARENT/a/b/c{.py,/}
            yield anchor.joinname(alias.name)

    def _get_anchor(self, import_from_stmt: ast.ImportFrom) -> ModuleName:
        # Handle the cases:
        # 1 from a.b import c (module == "a.b", level == 0)
        #   -> Python module/package: ../a/b{.py,/}
        # 2 from . import c (module == None, level == 1)
        #   -> Python module/package: ../BASE{.py,/}
        # 3 from .a.b import c (module == "a.b", level == 1)
        #   -> Python module/package: ../BASE/a/b{.py,/}
        # 4 from ..a.b import c (module == "a.b", level == 2)
        #   -> Python module/package: ../BASE_PARENT/a/b{.py,/}
        if import_from_stmt.level == 0:
            if import_from_stmt.module:
                return ModuleName(import_from_stmt.module)
            raise ValueError(import_from_stmt.module)

        try:
            parent = self._base_module.name.parents[import_from_stmt.level - 1]
        except IndexError:
            parent = ModuleName()

        return parent.joinname(import_from_stmt.module) if import_from_stmt.module else parent

    # -----helper-----

    def _validate_module(self, module: Module) -> None:
        if module == self._base_module or (
            isinstance(module, RegularPackage)
            and module.name.parent == self._base_module.name.parent
        ):
            # Last if-part: do not add reg pkg, ie. __init__.py, of base module
            raise ValueError(module)


class ImportsOfModule(NamedTuple):
    module: Module
    imports: Sequence[Module]


def visit_python_file(module_factory: ModuleFactory, path: Path) -> None | ImportsOfModule:
    try:
        module = module_factory.make_module_from_path(path)
    except ValueError:
        return None

    if isinstance(module, NamespacePackage):
        return None

    try:
        with open(module.path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", module.path, e)
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", module.path, e)
        return None

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    parser = ImportStmtsParser(
        module_factory,
        module,
        visitor.import_stmts,
    )

    return ImportsOfModule(
        module,
        sorted(parser.get_imports(), key=lambda m: tuple(m.name.parts), reverse=True),
    )
