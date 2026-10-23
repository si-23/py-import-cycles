#!/usr/bin/env python3

import ast
import itertools
import tokenize
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .log import logger
from .modules import ModuleName, PyModule, PyModuleType, make_py_module

STATEMENT_CONTAINERS = (ast.stmt, ast.excepthandler, ast.match_case)


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


def _statement_children(node: ast.AST) -> Iterator[ast.AST]:
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list):
            yield from (child for child in value if isinstance(child, STATEMENT_CONTAINERS))


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

    def generic_visit(self, node: ast.AST) -> None:
        for child in _statement_children(node):
            self.visit(child)

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


def _compute_py_module_from_module_name(
    py_modules_by_name: Mapping[ModuleName, PyModule], module_name: ModuleName
) -> Iterator[PyModule]:
    if not module_name.parts:
        return

    if module_name.parts[-1] == "*":
        module_name = module_name.parent

    if import_py_module := py_modules_by_name.get(module_name):
        yield import_py_module


def _compute_py_module_from_abs_import_stmt(
    py_modules_by_name: Mapping[ModuleName, PyModule], abs_import_stmt: _AbsImportStmt
) -> Iterator[PyModule]:
    for name in abs_import_stmt.names:
        yield from _compute_py_module_from_module_name(py_modules_by_name, ModuleName(name))


def _compute_py_module_from_abs_import_from_stmt(
    py_modules_by_name: Mapping[ModuleName, PyModule],
    abs_import_from_stmt: _AbsImportFromStmt,
) -> Iterator[PyModule]:
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
        yield from _compute_py_module_from_module_name(py_modules_by_name, anchor)


def _compute_ref_path_from_rel_import_from_stmt(
    base_py_module: PyModule, rel_import_from_stmt: _RelImportFromStmt
) -> Path:
    return base_py_module.path.parents[rel_import_from_stmt.level - 1]


def _compute_py_module_from_rel_import_from_stmt(base_py_module: PyModule, path: Path) -> PyModule:
    if (init_file_path := path / "__init__.py").exists():
        return make_py_module(base_py_module.package, init_file_path)
    if (module_file_path := path.with_suffix(".py")).exists():
        return make_py_module(base_py_module.package, module_file_path)
    if path.is_dir():
        return make_py_module(base_py_module.package, path)
    raise ValueError(path)


def _compute_py_modules_from_rel_import_from_stmt(
    base_py_module: PyModule, rel_import_from_stmt: _RelImportFromStmt
) -> Iterator[PyModule]:
    ref_path = _compute_ref_path_from_rel_import_from_stmt(base_py_module, rel_import_from_stmt)

    if rel_import_from_stmt.module:
        ref_path = ref_path.joinpath(*ModuleName(rel_import_from_stmt.module).parts)
        try:
            yield _compute_py_module_from_rel_import_from_stmt(base_py_module, ref_path)
        except ValueError:
            logger.debug("Cannot make py module from %s", ref_path)

    for name in rel_import_from_stmt.names:
        name_path = ref_path.joinpath(name)
        try:
            yield _compute_py_module_from_rel_import_from_stmt(base_py_module, name_path)
        except ValueError:
            logger.debug("Cannot make py module from %s", name_path)


def _imports_own_package_init(base_py_module: PyModule, import_py_module: PyModule) -> bool:
    return (
        base_py_module.type is PyModuleType.MODULE
        and import_py_module.type is PyModuleType.REGULAR_PACKAGE
        and base_py_module.path.parent == import_py_module.path.parent
    )


def _is_valid(base_py_module: PyModule, import_py_module: PyModule) -> bool:
    return base_py_module != import_py_module and not _imports_own_package_init(
        base_py_module, import_py_module
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


def _compute_imported_py_modules(
    py_modules_by_name: Mapping[ModuleName, PyModule],
    base_py_module: PyModule,
    visitor: NodeVisitorImports,
) -> Iterator[PyModule]:
    return itertools.chain(
        *(
            _compute_py_module_from_abs_import_stmt(py_modules_by_name, s)
            for s in visitor.abs_import_stmts
        ),
        *(
            _compute_py_module_from_abs_import_from_stmt(py_modules_by_name, s)
            for s in visitor.abs_import_from_stmts
        ),
        *(
            _compute_py_modules_from_rel_import_from_stmt(base_py_module, s)
            for s in visitor.rel_import_from_stmts
        ),
    )


def visit_py_module(
    py_modules_by_name: Mapping[ModuleName, PyModule], base_py_module: PyModule
) -> Iterator[PyModule]:
    if base_py_module.type is PyModuleType.NAMESPACE_PACKAGE:
        return

    if (visitor := _visit_imports(base_py_module.path)) is None:
        return

    yield from (
        import_py_module
        for import_py_module in _compute_imported_py_modules(
            py_modules_by_name, base_py_module, visitor
        )
        if _is_valid(base_py_module, import_py_module)
    )
