#!/usr/bin/env python3

import ast
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from .log import logger
from .modules import ModuleName, PyModule, PyModuleType

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
        py_modules_by_name: Mapping[ModuleName, PyModule],
        py_module: PyModule,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._py_modules_by_name = py_modules_by_name
        self._py_module = py_module
        self._import_stmts = import_stmts

    def get_imports(self) -> Iterator[PyModule]:
        yield from (p for p in self._py_module.parents if p.type is PyModuleType.REGULAR_PACKAGE)

        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                for alias in import_stmt.names:
                    if py_module := self._make_py_module_from_name(ModuleName(alias.name)):
                        yield py_module

            elif isinstance(import_stmt, ast.ImportFrom):
                if import_stmt.level == 0:
                    for module_name in self._get_module_names_of_abs_import_from_stmt(import_stmt):
                        if py_module := self._make_py_module_from_name(module_name):
                            yield py_module
                else:
                    yield from self._get_py_modules_of_rel_import_from_stmt(import_stmt)

    # -----ast.ImportFrom-----

    def _get_module_names_of_abs_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterator[ModuleName]:
        assert import_from_stmt.module

        anchor = ModuleName(import_from_stmt.module)
        yield anchor

        for alias in import_from_stmt.names:
            yield anchor.joinname(alias.name)

    def _get_py_modules_of_rel_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterator[PyModule]:
        assert import_from_stmt.level >= 1

        if self._py_module.type is PyModuleType.REGULAR_PACKAGE:
            if import_from_stmt.level == 1:
                ref_path = self._py_module.path.parent
            else:
                ref_path = self._py_module.path.parents[import_from_stmt.level - 2]
        else:
            # TODO PyModuleType.MODULE, PyModuleType.NAMESPACE_PACKAGE are already excluded
            # when calling visit_py_module
            ref_path = self._py_module.path.parents[import_from_stmt.level - 1]

        if import_from_stmt.module:
            ref_path = ref_path.joinpath(*ModuleName(import_from_stmt.module).parts)
            if py_module := self._get_py_module_of_rel_import_from_stmt(ref_path):
                yield py_module

        for alias in import_from_stmt.names:
            if py_module := self._get_py_module_of_rel_import_from_stmt(
                ref_path.joinpath(alias.name)
            ):
                yield py_module

    def _get_py_module_of_rel_import_from_stmt(self, path: Path) -> PyModule | None:
        try:
            if (init_file_path := path / "__init__.py").exists():
                py_module = PyModule(package=self._py_module.package, path=init_file_path)
            elif (module_file_path := path.with_suffix(".py")).exists():
                py_module = PyModule(package=self._py_module.package, path=module_file_path)
            else:  # TODO Namespace?
                py_module = PyModule(package=self._py_module.package, path=path)
        except ValueError as e:
            logger.debug("Cannot make py file from %s: %s", path, e)
            return None

        try:
            self._validate_py_module(py_module)
        except ValueError:
            return None

        return py_module

    # -----helper-----

    def _make_py_module_from_name(self, module_name: ModuleName) -> PyModule | None:
        if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
            return None

        if module_name.parts[-1] == "*":
            # Note:
            # from a.b import *
            # - If a.b is a pkg everything from a.b.__init__.py is loaded
            # - If a.b is a mod everything from a.b.py is loaded
            # -> Getting the "right" filepath is already handled below
            module_name = module_name.parent

        if not (py_module := self._lookup_py_module(module_name)):
            return None

        try:
            self._validate_py_module(py_module)
        except ValueError:
            return None

        return py_module

    def _lookup_py_module(self, module_name: ModuleName) -> PyModule | None:
        if py_module := self._py_modules_by_name.get(module_name):
            return py_module
        # TODO hack (missing namespace in self._py_modules_by_name)
        return self._py_modules_by_name.get(ModuleName(*module_name.parts[1:]))

    def _validate_py_module(self, py_module: PyModule) -> None:
        if self._py_module.type is PyModuleType.REGULAR_PACKAGE and str(py_module.name).startswith(
            str(self._py_module.name)
        ):
            # Importing submodules within a parent init is allowed
            raise ValueError(py_module)


def visit_py_module(
    py_modules_by_name: Mapping[ModuleName, PyModule], py_module: PyModule
) -> Iterator[PyModule]:
    try:
        with open(py_module.path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", py_module.path, e)
        yield from ()
        return

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", py_module.path, e)
        yield from ()
        return

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    parser = ImportStmtsParser(
        py_modules_by_name,
        py_module,
        visitor.import_stmts,
    )
    yield from parser.get_imports()
