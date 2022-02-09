#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import importlib
import os
import logging
import random
import sys
from dataclasses import dataclass, field
from graphviz import Digraph
from pathlib import Path
from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


#   .--contents------------------------------------------------------------.
#   |                                _             _                       |
#   |                 ___ ___  _ __ | |_ ___ _ __ | |_ ___                 |
#   |                / __/ _ \| '_ \| __/ _ \ '_ \| __/ __|                |
#   |               | (_| (_) | | | | ||  __/ | | | |_\__ \                |
#   |                \___\___/|_| |_|\__\___|_| |_|\__|___/                |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def _get_python_files(path: Path) -> Iterable[Path]:
    if path.is_symlink():
        return

    if path.is_file() and path.suffix == ".py":
        yield path.resolve()
        return

    for f in path.iterdir():
        if f.is_dir():
            yield from _get_python_files(f)
            continue

        if f.suffix == ".py":
            yield f.resolve()


def _load_python_contents(files: Set[Path]) -> Mapping[Path, str]:
    raw_contents: Dict[Path, str] = {}
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                raw_contents.setdefault(path, f.read())
        except UnicodeDecodeError as e:
            logger.debug("Cannot read python file %s: %s", path, e)

    return raw_contents


# .
#   .--node visitor--------------------------------------------------------.
#   |                        _              _     _ _                      |
#   |        _ __   ___   __| | ___  __   _(_)___(_) |_ ___  _ __          |
#   |       | '_ \ / _ \ / _` |/ _ \ \ \ / / / __| | __/ _ \| '__|         |
#   |       | | | | (_) | (_| |  __/  \ V /| \__ \ | || (_) | |            |
#   |       |_| |_|\___/ \__,_|\___|   \_/ |_|___/_|\__\___/|_|            |
#   |                                                                      |
#   '----------------------------------------------------------------------'


ImportContext = Tuple[Union[ast.ClassDef, ast.FunctionDef], ...]


class ImportSTMT(NamedTuple):
    context: ImportContext
    node: ast.Import


class ImportFromSTMT(NamedTuple):
    context: ImportContext
    node: ast.ImportFrom

    # TODO use context in graph (nested import stmt)


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._imports_stmt: List[ImportSTMT] = []
        self._imports_from_stmt: List[ImportFromSTMT] = []
        self._context: ImportContext = tuple()

    @property
    def imports_stmt(self) -> Sequence[ImportSTMT]:
        return self._imports_stmt

    @property
    def imports_from_stmt(self) -> Sequence[ImportFromSTMT]:
        return self._imports_from_stmt

    def visit_Import(self, node: ast.Import) -> None:
        self._imports_stmt.append(ImportSTMT(self._context, node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._imports_from_stmt.append(ImportFromSTMT(self._context, node))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._context += (node,)
        for child in ast.iter_child_nodes(node):
            ast.NodeVisitor.visit(self, child)
        self._context = self._context[:-1]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._context += (node,)
        for child in ast.iter_child_nodes(node):
            ast.NodeVisitor.visit(self, child)
        self._context = self._context[:-1]


def _visit_python_contents(
    python_contents: Mapping[Path, str]
) -> Sequence[NodeVisitorImports]:
    visitors: List[NodeVisitorImports] = []
    for path, python_content in python_contents.items():
        try:
            tree = ast.parse(python_content)
        except SyntaxError as e:
            logger.debug("Cannot visit python file %s: %s", path, e)
            continue

        visitor = NodeVisitorImports(path)
        visitor.visit(tree)
        visitors.append(visitor)
    return visitors


# .
#   .--cycles--------------------------------------------------------------.
#   |                                     _                                |
#   |                      ___ _   _  ___| | ___  ___                      |
#   |                     / __| | | |/ __| |/ _ \/ __|                     |
#   |                    | (__| |_| | (__| |  __/\__ \                     |
#   |                     \___|\__, |\___|_|\___||___/                     |
#   |                          |___/                                       |
#   '----------------------------------------------------------------------'


ImportChain = Sequence[str]


@dataclass
class ImportCycle:
    cycle: Tuple[str, ...]
    color: str
    chains: List[ImportChain] = field(default_factory=list)


def _find_import_cycles(module_imports: ModuleImports) -> Sequence[ImportCycle]:
    detector = DetectImportCycles(module_imports)

    import_cycles: Dict[Tuple[str, ...], ImportCycle] = {}
    for chain in sorted(detector.detect_cycles()):
        first_idx = chain.index(chain[-1])
        cycle = tuple(chain[first_idx:])

        import_cycles.setdefault(
            tuple(sorted(cycle[:-1])),
            ImportCycle(
                cycle=cycle,
                color="#%02x%02x%02x"
                % (
                    random.randint(50, 200),
                    random.randint(50, 200),
                    random.randint(50, 200),
                ),
            ),
        ).chains.append(chain)

    return list(import_cycles.values())


@dataclass(frozen=True)
class DetectImportCycles:
    _module_imports: Mapping[str, Sequence[str]]

    def detect_cycles(self) -> Iterable[Sequence[str]]:
        for module in self._get_main_modules():
            yield from self._detect_cycles([module], module)

    def _get_main_modules(self) -> Sequence[str]:
        imported_modules = set(
            imported_module
            for imported_modules in self._module_imports.values()
            for imported_module in imported_modules
        )
        if main_modules := set(
            name for name in self._module_imports if name not in imported_modules
        ):
            return sorted(main_modules)
        return sorted(self._module_imports)

    def _detect_cycles(
        self,
        base_chain: List[str],
        module: str,
    ) -> Iterable[Sequence[str]]:
        for imported_module in self._module_imports.get(module, []):
            if imported_module in base_chain:
                yield base_chain + [imported_module]
                break

            yield from self._detect_cycles(
                base_chain + [imported_module], imported_module
            )


# .
#   .--graph---------------------------------------------------------------.
#   |                                           _                          |
#   |                      __ _ _ __ __ _ _ __ | |__                       |
#   |                     / _` | '__/ _` | '_ \| '_ \                      |
#   |                    | (_| | | | (_| | |_) | | | |                     |
#   |                     \__, |_|  \__,_| .__/|_| |_|                     |
#   |                     |___/          |_|                               |
#   '----------------------------------------------------------------------'


def _make_graph(path: Path, edges: Sequence[ImportEdge]) -> Digraph:
    # TODO
    target_dir = (
        Path(os.path.abspath(__file__))
        .parent.parent.joinpath("outputs")
        .joinpath(path.name)
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    d = Digraph("unix", filename=target_dir.joinpath("import-cycles.gv"))

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(edge.module)
            ds.node(edge.imports)
            ds.attr("edge", color=edge.color)
            ds.edge(edge.module, edge.imports)

    return d.unflatten(stagger=50)


class ImportEdge(NamedTuple):
    module: str
    imports: str
    is_in_cycle: bool
    color: str


def _make_edges(
    args: argparse.Namespace,
    module_imports: ModuleImports,
    import_cycles: Sequence[ImportCycle],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(module_imports, import_cycles)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(import_cycles)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    module_imports: ModuleImports,
    import_cycles: Sequence[ImportCycle],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for module, imports in module_imports.items():
        for the_import in imports:
            edges.add(_make_edge(module, the_import, import_cycles))
    return sorted(edges)


def _make_only_cycles_edges(
    import_cycles: Sequence[ImportCycle],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for import_cycle in import_cycles:
        module = import_cycle.cycle[0]
        for the_import in import_cycle.cycle[1:]:
            edges.add(_make_edge(module, the_import, import_cycles))
            module = the_import
    return sorted(edges)


def _make_edge(
    module: str,
    the_import: str,
    import_cycles: Sequence[ImportCycle],
) -> ImportEdge:
    import_cycle = _is_in_cycle(module, the_import, import_cycles)
    return ImportEdge(
        module,
        the_import,
        import_cycle is not None,
        "black" if import_cycle is None else import_cycle.color,
    )


def _is_in_cycle(
    module: str,
    the_import: str,
    import_cycles: Sequence[ImportCycle],
) -> Optional[ImportCycle]:
    for import_cycle in import_cycles:
        try:
            idx = import_cycle.cycle.index(module)
        except ValueError:
            continue

        if import_cycle.cycle[idx + 1] == the_import:
            return import_cycle
    return None


# .
#   .--helper--------------------------------------------------------------.
#   |                    _          _                                      |
#   |                   | |__   ___| |_ __   ___ _ __                      |
#   |                   | '_ \ / _ \ | '_ \ / _ \ '__|                     |
#   |                   | | | |  __/ | |_) |  __/ |                        |
#   |                   |_| |_|\___|_| .__/ \___|_|                        |
#   |                                |_|                                   |
#   '----------------------------------------------------------------------'


ModuleImports = Mapping[str, Sequence[str]]


def _get_module_imports(
    base_path: Path,
    namespace: str,
    visitors: Sequence[NodeVisitorImports],
) -> ModuleImports:
    module_imports: Dict[str, List[str]] = {}
    for visitor in visitors:
        try:
            module_name_from_path = _get_module_name_from_path(
                base_path, namespace, visitor.path
            )
        except ValueError as e:
            logger.debug("Error while getting module name: %s", e)
            continue

        for import_stmt in visitor.imports_stmt:
            for alias in import_stmt.node.names:
                if _is_builtin_or_stdlib(alias.name):
                    continue

                if (
                    module_name_from_import := _get_module_name_from_import(
                        base_path, namespace, alias.name
                    )
                ) is None:
                    continue

                module_imports.setdefault(module_name_from_path, []).append(
                    module_name_from_import
                )

        for import_from_stmt in visitor.imports_from_stmt:
            if not import_from_stmt.node.module:
                continue

            if _is_builtin_or_stdlib(import_from_stmt.node.module):
                continue

            if (
                module_name_from_import := _get_module_name_from_import(
                    base_path, namespace, import_from_stmt.node.module
                )
            ) is None:
                continue

            module_imports.setdefault(module_name_from_path, []).append(
                module_name_from_import
            )

    return module_imports


def _get_module_name_from_path(base_path: Path, namespace: str, path: Path) -> str:
    # TODO use importlib or inspect in order to get the right module name
    idx = base_path.parts.index(namespace)
    base_path = Path(*base_path.parts[:idx])

    path = path.relative_to(base_path).with_suffix("")
    if path.name == "__init__":
        path = path.parent
    return str(path).replace("/", ".")


def _is_builtin_or_stdlib(name: str) -> bool:
    return (
        name in sys.builtin_module_names or name in sys.modules
    )  #  Avail in 3.10: or name in sys.stdlib_module_names


def _get_module_name_from_import(
    base_path: Path,
    namespace: str,
    name: str,
) -> Optional[str]:
    if name.startswith(namespace):
        return name

    try:
        module_spec = importlib.util.find_spec(name)
    except ModuleNotFoundError as e:
        logger.debug("Name: %s, Error: %s", name, e)
        module_spec = None

    if module_spec is not None:
        return None

    idx = base_path.parts.index(namespace)
    return ".".join(list(base_path.parts[idx:]) + [name])


# .


def main(argv: Sequence[str]) -> int:
    args = _parse_arguments(argv)

    _setup_logging(args)

    path = Path(args.path)
    if not path.exists() or not path.is_dir():
        logger.debug("No such directory: %s", path)
        return 1

    if args.namespace not in path.parts:
        logger.debug("Namespace '%s' must be part of %s", args.namespace, path)
        return 1

    python_files = _get_python_files(path)

    loaded_python_files = _load_python_contents(set(python_files))

    visitors = _visit_python_contents(loaded_python_files)

    module_imports = _get_module_imports(path, args.namespace, visitors)

    import_cycles = _find_import_cycles(module_imports)

    _show_import_cycles(args, import_cycles)

    if args.graph == "no":
        return _get_return_code(import_cycles)

    if not (edges := _make_edges(args, module_imports, import_cycles)):
        logger.debug("No edges for graphing")
        return _get_return_code(import_cycles)

    graph = _make_graph(path, edges)
    graph.view()

    return _get_return_code(import_cycles)


def _parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show errors",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show chains",
    )
    parser.add_argument(
        "--graph",
        choices=["all", "only-cycles", "no"],
        default="only-cycles",
        help="Only show cycles",
    )
    parser.add_argument(
        "--namespace",
        help="Part of the path which is the anchor to the namespace",
        required=True,
    )
    parser.add_argument(
        "path",
        help="Path to project folder",
    )
    return parser.parse_args(argv)


def _setup_logging(args: argparse.Namespace) -> None:
    if args.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.NOTSET

    logger.setLevel(log_level)

    handler = logging.StreamHandler()
    handler.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _show_import_cycles(
    args: argparse.Namespace, import_cycles: Sequence[ImportCycle]
) -> None:
    if import_cycles:
        print("===== Found import cycles ====")
        for import_cycle in import_cycles:
            print("Cycle:", import_cycle.cycle)
            if not args.verbose:
                continue

            for chain in import_cycle.chains:
                print("  In chain:", chain)


def _get_return_code(import_cycles: Sequence[ImportCycle]) -> bool:
    return bool(import_cycles)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
