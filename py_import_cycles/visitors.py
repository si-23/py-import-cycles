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
class _AbsImportStmt:
    names: tuple[str, ...]


@dataclass(frozen=True)
class _AbsImportFromStmt:
    module: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        assert self.module


@dataclass(frozen=True)
class _RelImportFromStmt:
    level: int
    module: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        assert self.level >= 1


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self) -> None:
        self._abs_import_stmts: list[_AbsImportStmt] = []
        self._abs_import_from_stmts: list[_AbsImportFromStmt] = []
        self._rel_import_from_stmts: list[_RelImportFromStmt] = []

    @property
    def abs_import_stmts(self) -> Sequence[_AbsImportStmt]:
        return self._abs_import_stmts

    @property
    def abs_import_from_stmts(self) -> Sequence[_AbsImportFromStmt]:
        return self._abs_import_from_stmts

    @property
    def rel_import_from_stmts(self) -> Sequence[_RelImportFromStmt]:
        return self._rel_import_from_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._abs_import_stmts.append(
            _AbsImportStmt(
                tuple(a.name for a in node.names),
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level >= 1:
            self._rel_import_from_stmts.append(
                _RelImportFromStmt(
                    node.level,
                    node.module or "",
                    tuple(a.name for a in node.names),
                )
            )
        else:
            self._abs_import_from_stmts.append(
                _AbsImportFromStmt(
                    node.module or "",
                    tuple(a.name for a in node.names),
                )
            )


def _compute_py_module_from_module_name(
    py_modules_by_name: Mapping[ModuleName, PyModule], module_name: ModuleName
) -> Iterator[PyModule]:
    if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
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


def _compute_py_module_from_abs_import_stmt(
    py_modules_by_name: Mapping[ModuleName, PyModule], abs_import_stmt: _AbsImportStmt
) -> Iterator[PyModule]:
    # https://docs.python.org/3/reference/simple_stmts.html#import
    # import foo                 # foo imported and bound locally
    # import foo.bar.baz         # foo, foo.bar, and foo.bar.baz imported, foo bound locally
    # import foo.bar.baz as fbb  # foo, foo.bar, and foo.bar.baz imported, foo.bar.baz bound as fbb
    for name in abs_import_stmt.names:
        yield from _compute_py_module_from_module_name(py_modules_by_name, ModuleName(name))


def _compute_py_module_from_abs_import_from_stmt(
    py_modules_by_name: Mapping[ModuleName, PyModule],
    abs_import_from_stmt: _AbsImportFromStmt,
) -> Iterator[PyModule]:
    # https://docs.python.org/3/reference/simple_stmts.html#import
    # from foo.bar import baz    # foo, foo.bar, and foo.bar.baz imported, foo.bar.baz bound as baz
    # from foo import attr       # foo imported and foo.attr bound as attr
    anchor = ModuleName(abs_import_from_stmt.module)
    import_py_modules = [
        import_py_module
        for name in abs_import_from_stmt.names
        for import_py_module in _compute_py_module_from_module_name(
            py_modules_by_name, anchor.joinname(name)
        )
    ]
    yield from import_py_modules

    if len(import_py_modules) != len(abs_import_from_stmt.names):
        # from a.b import c, d
        # Check if c and d are modules or objects. If c or d is not a module then we have to
        # collect 'a.b'
        yield from _compute_py_module_from_module_name(py_modules_by_name, anchor)


def _compute_ref_path_from_rel_import_from_stmt(
    base_py_module: PyModule, rel_import_from_stmt: _RelImportFromStmt
) -> Path:
    # Note: PyModuleType.NAMESPACE_PACKAGE are already excluded when calling 'visit_py_module'
    if base_py_module.type is PyModuleType.MODULE:
        return base_py_module.path.parents[rel_import_from_stmt.level - 1]
    # PyModuleType.REGULAR_PACKAGE
    if rel_import_from_stmt.level == 1:
        return base_py_module.path.parent
    return base_py_module.path.parents[rel_import_from_stmt.level - 2]


def _compute_py_module_from_rel_import_from_stmt(base_py_module: PyModule, path: Path) -> PyModule:
    if (module_file_path := path.with_suffix(".py")).exists():
        return PyModule(package=base_py_module.package, path=module_file_path)
    if (init_file_path := path / "__init__.py").exists():
        return PyModule(package=base_py_module.package, path=init_file_path)
    if path.is_dir():
        return PyModule(package=base_py_module.package, path=path)
    raise ValueError(path)


def _compute_py_modules_from_rel_import_from_stmt(
    base_py_module: PyModule, rel_import_from_stmt: _RelImportFromStmt
) -> Iterator[PyModule]:
    ref_path = _compute_ref_path_from_rel_import_from_stmt(base_py_module, rel_import_from_stmt)

    if rel_import_from_stmt.module:
        ref_path = ref_path.joinpath(*ModuleName(rel_import_from_stmt.module).parts)
        try:
            yield _compute_py_module_from_rel_import_from_stmt(base_py_module, ref_path)
        except ValueError as e:
            logger.debug("Cannot make py module from %s: %s", ref_path, e)

    for name in rel_import_from_stmt.names:
        try:
            yield _compute_py_module_from_rel_import_from_stmt(
                base_py_module, ref_path.joinpath(name)
            )
        except ValueError as e:
            logger.debug("Cannot make py module from %s: %s", ref_path, e)


def _is_valid(base_py_module: PyModule, import_py_module: PyModule) -> bool:
    if base_py_module == import_py_module:
        return False
    if (
        base_py_module.type is PyModuleType.MODULE
        and import_py_module.type is PyModuleType.REGULAR_PACKAGE
        and base_py_module.path.parent == import_py_module.path.parent
    ):
        # Do not take 'foo.bar.baz imports foo.bar.__init__' into account
        return False
    return True


def visit_py_module(
    py_modules_by_name: Mapping[ModuleName, PyModule], base_py_module: PyModule
) -> Iterator[PyModule]:
    if base_py_module.type is PyModuleType.NAMESPACE_PACKAGE:
        return

    try:
        with open(base_py_module.path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", base_py_module.path, e)
        return

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", base_py_module.path, e)
        return

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    for abs_import_stmt in visitor.abs_import_stmts:
        for import_py_module in _compute_py_module_from_abs_import_stmt(
            py_modules_by_name, abs_import_stmt
        ):
            if _is_valid(base_py_module, import_py_module):
                yield import_py_module

    for abs_import_from_stmt in visitor.abs_import_from_stmts:
        for import_py_module in _compute_py_module_from_abs_import_from_stmt(
            py_modules_by_name, abs_import_from_stmt
        ):
            if _is_valid(base_py_module, import_py_module):
                yield import_py_module

    for rel_import_from_stmt in visitor.rel_import_from_stmts:
        for import_py_module in _compute_py_modules_from_rel_import_from_stmt(
            base_py_module, rel_import_from_stmt
        ):
            if _is_valid(base_py_module, import_py_module):
                yield import_py_module
