#!/usr/bin/env python3

import ast
import itertools
import tokenize
from collections.abc import Iterator, Mapping, Sequence, Set
from dataclasses import dataclass
from pathlib import Path

from .log import logger
from .modules import ModuleName, PyModule, PyModuleType


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


def _has_ignore_comment(line: str) -> bool:
    return "py-import-cycles: ignore" in [c.strip() for c in line.split("#")[1:]]


def _ignore(code_lines: Sequence[str], lineno: int) -> bool:
    if _has_ignore_comment(code_lines[lineno - 1]):
        return True

    if lineno < 2:
        return False

    comment_line = code_lines[lineno - 2]
    return comment_line.strip().startswith("#") and _has_ignore_comment(comment_line)


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self, code: str) -> None:
        self._code_lines = code.split("\n")
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

    def _is_ignored(self, node: ast.Import | ast.ImportFrom) -> bool:
        if ignored := _ignore(self._code_lines, node.lineno):
            logger.debug("Found ignore comment for %r", ast.unparse(node))
        return ignored

    def visit_Import(self, node: ast.Import) -> None:
        if self._is_ignored(node):
            return
        self._abs_import_stmts.append(
            _AbsImportStmt(
                tuple(a.name for a in node.names),
            )
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._is_ignored(node):
            return
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


def _prefixes(module_name: ModuleName) -> Sequence[ModuleName]:
    return [ModuleName(*module_name.parts[:i]) for i in range(1, len(module_name.parts) + 1)]


def _names_of_import_stmt(
    abs_import_stmt: _AbsImportStmt, ancestors: Set[ModuleName]
) -> Iterator[ModuleName]:
    for name in abs_import_stmt.names:
        *parents, module_name = _prefixes(ModuleName(name))
        yield from (p for p in parents if p not in ancestors)
        yield module_name


def _names_of_import_from_stmt(
    py_modules_by_name: Mapping[ModuleName, PyModule],
    abs_import_from_stmt: _AbsImportFromStmt,
    ancestors: Set[ModuleName],
) -> Iterator[ModuleName]:
    *parents, module_name = _prefixes(ModuleName(abs_import_from_stmt.module))
    submodule_names = [
        submodule_name
        for name in abs_import_from_stmt.names
        if name != "*" and (submodule_name := module_name.joinname(name)) in py_modules_by_name
    ]
    reads_names = len(submodule_names) < len(abs_import_from_stmt.names)

    yield from (p for p in parents if p not in ancestors)
    if reads_names or module_name not in ancestors:
        yield module_name
    yield from submodule_names


def _package_name(py_module: PyModule) -> ModuleName:
    if py_module.type is PyModuleType.REGULAR_PACKAGE:
        return py_module.name
    return py_module.name.parent


def _make_abs_import_from_stmt(
    base_py_module: PyModule, rel_import_from_stmt: _RelImportFromStmt
) -> _AbsImportFromStmt | None:
    package_parts = _package_name(base_py_module).parts
    if rel_import_from_stmt.level > len(package_parts):
        logger.debug(
            "Cannot resolve relative import of level %s in %s",
            rel_import_from_stmt.level,
            base_py_module.name,
        )
        return None

    anchor = ModuleName(*package_parts[: len(package_parts) - rel_import_from_stmt.level + 1])
    module = anchor.joinname(rel_import_from_stmt.module) if rel_import_from_stmt.module else anchor
    return _AbsImportFromStmt(str(module), rel_import_from_stmt.names)


def _is_valid(base_py_module: PyModule, import_py_module: PyModule) -> bool:
    return (
        base_py_module != import_py_module
        and import_py_module.type is not PyModuleType.NAMESPACE_PACKAGE
    )


def _visit_imports(path: Path) -> NodeVisitorImports | None:
    try:
        with tokenize.open(path) as f:
            code = f.read()
    except (OSError, SyntaxError, UnicodeDecodeError) as e:
        logger.debug("Cannot read python file %s: %s", path, e)
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", path, e)
        return None

    visitor = NodeVisitorImports(code)
    visitor.visit(tree)
    return visitor


def _compute_imported_names(
    py_modules_by_name: Mapping[ModuleName, PyModule],
    base_py_module: PyModule,
    visitor: NodeVisitorImports,
) -> Iterator[ModuleName]:
    ancestors = frozenset(_prefixes(base_py_module.name)[:-1])
    return itertools.chain(
        *(_names_of_import_stmt(s, ancestors) for s in visitor.abs_import_stmts),
        *(
            _names_of_import_from_stmt(py_modules_by_name, s, ancestors)
            for s in visitor.abs_import_from_stmts
        ),
        *(
            _names_of_import_from_stmt(py_modules_by_name, abs_stmt, ancestors)
            for s in visitor.rel_import_from_stmts
            if (abs_stmt := _make_abs_import_from_stmt(base_py_module, s))
        ),
    )


def visit_py_module(
    py_modules_by_name: Mapping[ModuleName, PyModule], base_py_module: PyModule
) -> Iterator[PyModule]:
    if base_py_module.type is PyModuleType.NAMESPACE_PACKAGE:
        return

    if (visitor := _visit_imports(base_py_module.path)) is None:
        return

    for name in _compute_imported_names(py_modules_by_name, base_py_module, visitor):
        import_py_module = py_modules_by_name.get(name)
        if import_py_module and _is_valid(base_py_module, import_py_module):
            yield import_py_module
