#!/usr/bin/env python3

import ast
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .log import logger
from .modules import ModuleName, PyModule, PyModuleType

STDLIB_OR_BUILTIN = sys.stdlib_module_names.union(sys.builtin_module_names)
ImportSTMT = ast.Import | ast.ImportFrom


@dataclass(frozen=True)
class _RelImportStmt:
    level: int
    module: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        assert self.level >= 1


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self) -> None:
        self._module_names: list[ModuleName] = []
        self._rel_import_stmts: list[_RelImportStmt] = []

    @property
    def module_names(self) -> Sequence[ModuleName]:
        return self._module_names

    @property
    def rel_import_stmts(self) -> Sequence[_RelImportStmt]:
        return self._rel_import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._module_names.extend(ModuleName(a.name) for a in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level >= 1:
            self._rel_import_stmts.append(
                _RelImportStmt(
                    node.level,
                    node.module or "",
                    tuple(a.name for a in node.names),
                )
            )
        else:
            assert node.module
            anchor = ModuleName(node.module)
            self._module_names.append(anchor)
            self._module_names.extend(anchor.joinname(a.name) for a in node.names)


def _compute_py_module_from_module_name(
    py_modules_by_name: Mapping[ModuleName, PyModule], module_name: ModuleName
) -> Iterator[PyModule]:
    if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
        yield from ()
        return

    if module_name.parts[-1] == "*":
        # Note:
        # from a.b import *
        # - If a.b is a pkg everything from a.b.__init__.py is loaded
        # - If a.b is a mod everything from a.b.py is loaded
        # -> Getting the "right" filepath is already handled below
        module_name = module_name.parent

    if import_py_module := py_modules_by_name.get(module_name):
        yield import_py_module
        return

    # TODO hack (missing namespace in self._py_modules_by_name)
    if import_py_module := py_modules_by_name.get(ModuleName(*module_name.parts[1:])):
        yield import_py_module
        return


def _compute_py_module_from_rel_import_from_stmt(base_py_module: PyModule, path: Path) -> PyModule:
    if (init_file_path := path / "__init__.py").exists():
        return PyModule(package=base_py_module.package, path=init_file_path)
    if (module_file_path := path.with_suffix(".py")).exists():
        return PyModule(package=base_py_module.package, path=module_file_path)
    # TODO Namespace?
    return PyModule(package=base_py_module.package, path=path)


def _compute_py_modules_from_rel_import_from_stmt(
    base_py_module: PyModule, rel_import_stmt: _RelImportStmt
) -> Iterator[PyModule]:
    if base_py_module.type is PyModuleType.REGULAR_PACKAGE:
        if rel_import_stmt.level == 1:
            ref_path = base_py_module.path.parent
        else:
            ref_path = base_py_module.path.parents[rel_import_stmt.level - 2]
    else:
        # TODO PyModuleType.MODULE, PyModuleType.NAMESPACE_PACKAGE are already excluded
        # when calling visit_py_module
        ref_path = base_py_module.path.parents[rel_import_stmt.level - 1]

    if rel_import_stmt.module:
        ref_path = ref_path.joinpath(*ModuleName(rel_import_stmt.module).parts)
        try:
            yield _compute_py_module_from_rel_import_from_stmt(base_py_module, ref_path)
        except ValueError as e:
            logger.debug("Cannot make py file from %s: %s", ref_path, e)

    for name in rel_import_stmt.names:
        try:
            yield _compute_py_module_from_rel_import_from_stmt(
                base_py_module, ref_path.joinpath(name)
            )
        except ValueError as e:
            logger.debug("Cannot make py file from %s: %s", ref_path, e)


def _validate_py_module(base_py_module: PyModule, import_py_module: PyModule) -> None:
    if base_py_module.type is PyModuleType.REGULAR_PACKAGE and str(
        import_py_module.name
    ).startswith(str(base_py_module.name)):
        # Importing submodules within a parent init is allowed
        raise ValueError(import_py_module)


def visit_py_module(
    py_modules_by_name: Mapping[ModuleName, PyModule], base_py_module: PyModule
) -> Iterator[PyModule]:
    try:
        with open(base_py_module.path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", base_py_module.path, e)
        yield from ()
        return

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", base_py_module.path, e)
        yield from ()
        return

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    yield from (p for p in base_py_module.parents if p.type is PyModuleType.REGULAR_PACKAGE)

    for module_name in visitor.module_names:
        for import_py_module in _compute_py_module_from_module_name(
            py_modules_by_name, module_name
        ):
            try:
                _validate_py_module(
                    base_py_module=base_py_module, import_py_module=import_py_module
                )
            except ValueError:
                continue

            yield import_py_module

    for rel_import_stmt in visitor.rel_import_stmts:
        for import_py_module in _compute_py_modules_from_rel_import_from_stmt(
            base_py_module, rel_import_stmt
        ):
            try:
                _validate_py_module(
                    base_py_module=base_py_module, import_py_module=import_py_module
                )
            except ValueError:
                continue

            yield import_py_module
