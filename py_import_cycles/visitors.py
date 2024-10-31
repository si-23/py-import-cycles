#!/usr/bin/env python3

import ast
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import NamedTuple

from .log import logger
from .modules import (
    make_module_from_py_file,
    Module,
    ModuleFactory,
    ModuleName,
    NamespacePackage,
    PyFile,
    PyFileType,
    RegularPackage,
)

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
        py_file: PyFile,
        base_module: Module,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._module_factory = module_factory
        self._py_file = py_file
        self._base_module = base_module
        self._import_stmts = import_stmts

    def get_imports(self) -> Iterator[Module]:
        yield from self._module_factory.make_parents_of_module(self._base_module)

        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                for alias in import_stmt.names:
                    if module := self._make_module_from_name(ModuleName(alias.name)):
                        yield module

            elif isinstance(import_stmt, ast.ImportFrom):
                if import_stmt.level == 0:
                    for module_name in self._get_module_names_of_abs_import_from_stmt(import_stmt):
                        if module := self._make_module_from_name(module_name):
                            yield module
                else:
                    yield from self._get_modules_of_rel_import_from_stmt(import_stmt)

    # -----ast.ImportFrom-----

    def _get_module_names_of_abs_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterator[ModuleName]:
        assert import_from_stmt.module

        anchor = ModuleName(import_from_stmt.module)
        yield anchor

        for alias in import_from_stmt.names:
            yield anchor.joinname(alias.name)

    def _get_modules_of_rel_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterator[Module]:
        assert import_from_stmt.level >= 1

        if self._py_file.type is PyFileType.REGULAR_PACKAGE:
            if import_from_stmt.level == 1:
                ref_path = self._py_file.path.parent
            else:
                ref_path = self._py_file.path.parents[import_from_stmt.level - 2]
        else:
            # TODO PyFileType.MODULE, PyFileType.NAMESPACE_PACKAGE are already excluded
            # when calling visit_py_file
            ref_path = self._py_file.path.parents[import_from_stmt.level - 1]

        if import_from_stmt.module:
            ref_path = ref_path.joinpath(*ModuleName(import_from_stmt.module).parts)
            if module := self._get_module_of_rel_import_from_stmt(ref_path):
                yield module

        for alias in import_from_stmt.names:
            if module := self._get_module_of_rel_import_from_stmt(ref_path.joinpath(alias.name)):
                yield module

    def _get_module_of_rel_import_from_stmt(self, path: Path) -> Module | None:
        try:
            if (init_file_path := path / "__init__.py").exists():
                py_file = PyFile(package=self._py_file.package, path=init_file_path)
            elif (module_file_path := path.with_suffix(".py")).exists():
                py_file = PyFile(package=self._py_file.package, path=module_file_path)
            else:  # TODO Namespace?
                py_file = PyFile(package=self._py_file.package, path=path)
        except ValueError as e:
            logger.debug("Cannot make py file from %s: %s", path, e)
            return None

        module = make_module_from_py_file(py_file)

        try:
            self._validate_module(module)
        except ValueError:
            return None

        return module

    # -----helper-----

    def _make_module_from_name(self, module_name: ModuleName) -> Module | None:
        if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
            return None

        try:
            module = self._module_factory.make_module_from_name(module_name)
            self._validate_module(module)
        except ValueError:
            return None

        return module

    def _validate_module(self, module: Module) -> None:
        if isinstance(self._base_module, RegularPackage) and str(module.name).startswith(
            str(self._base_module.name.parent)
        ):
            # Importing submodules within a parent init is allowed
            raise ValueError(module)


class ImportsOfModule(NamedTuple):
    module: Module
    imports: Sequence[Module]


def visit_py_file(module_factory: ModuleFactory, py_file: PyFile) -> None | ImportsOfModule:
    module = make_module_from_py_file(py_file)

    if isinstance(module, NamespacePackage):
        return None

    try:
        with open(module.path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", py_file.path, e)
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", py_file.path, e)
        return None

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    parser = ImportStmtsParser(
        module_factory,
        py_file,
        module,
        visitor.import_stmts,
    )

    return ImportsOfModule(
        module,
        sorted(
            frozenset(parser.get_imports()),
            key=lambda m: tuple(m.name.parts),
            reverse=True,
        ),
    )
