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

# TODO #1
# load all python file not only below FOLDER

# TODO #2
# Handle:
#   import pkg -> execute __init__.py
#   import pkg.mod -> __init__.py already executed
# or
#   import pkg.mod -> execute __init__.py
#   import pkg -> __init__.py already executed

# TODO #3
# Is args.map really needed?

# TODO #4
# use context in graph (nested import stmt)

# TODO #5
# Handle star imports

# TODO #6
# Handle relative imports properly

# Cases:
# import path.to.mod
# import path.to.mod as my_mod

# from path.to.mod import sub_mod
# from path.to.mod import sub_mod as my_sub_mod

# from path.to.mod import func/class
# from path.to.mod import func/class as my_func/class


#   .--files---------------------------------------------------------------.
#   |                           __ _ _                                     |
#   |                          / _(_) | ___  ___                           |
#   |                         | |_| | |/ _ \/ __|                          |
#   |                         |  _| | |  __/\__ \                          |
#   |                         |_| |_|_|\___||___/                          |
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


# .
#   .--node visitor--------------------------------------------------------.
#   |                        _              _     _ _                      |
#   |        _ __   ___   __| | ___  __   _(_)___(_) |_ ___  _ __          |
#   |       | '_ \ / _ \ / _` |/ _ \ \ \ / / / __| | __/ _ \| '__|         |
#   |       | | | | (_) | (_| |  __/  \ V /| \__ \ | || (_) | |            |
#   |       |_| |_|\___/ \__,_|\___|   \_/ |_|___/_|\__\___/|_|            |
#   |                                                                      |
#   '----------------------------------------------------------------------'


ImportContext = Tuple[Union[ast.If, ast.Try, ast.ClassDef, ast.FunctionDef], ...]


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._import_stmts: List[Union[ImportSTMT, ImportFromSTMT]] = []
        self._context: ImportContext = tuple()

    @property
    def import_stmts(self) -> Sequence[Union[ImportSTMT, ImportFromSTMT]]:
        return self._import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._import_stmts.append(ImportSTMT(self._context, node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._import_stmts.append(ImportFromSTMT(self._context, node))

    def visit_If(self, node: ast.If) -> None:
        self._context += (node,)
        for child in ast.iter_child_nodes(node):
            ast.NodeVisitor.visit(self, child)
        self._context = self._context[:-1]

    def visit_Try(self, node: ast.Try) -> None:
        self._context += (node,)
        for child in ast.iter_child_nodes(node):
            ast.NodeVisitor.visit(self, child)
        self._context = self._context[:-1]

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


def _visit_python_files(files: Iterable[Path]) -> Iterable[NodeVisitorImports]:
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            logger.debug("Cannot read python file %s: %s", path, e)
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.debug("Cannot visit python file %s: %s", path, e)
            continue

        visitor = NodeVisitorImports(path)
        visitor.visit(tree)
        yield visitor


class ImportSTMT(NamedTuple):
    context: ImportContext
    node: ast.Import

    def get_imported_modules(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: Module,
    ) -> Iterable[Module]:
        for alias in self.node.names:
            if _is_builtin_or_stdlib(alias.name):
                continue

            module = Module.from_name(
                mapping,
                project_path,
                alias.name,
                self.context,
            )

            if module.py_exists():
                yield module
                continue

            if module.init_exists():
                logger.debug(
                    "Import: Unhandled %s: %s",
                    base_module.name,
                    ".".join([module.name, "__init__"]),
                )
                continue

            logger.debug(
                "Import: Unhandled %s: %s",
                base_module.name,
                ast.dump(self.node),
            )


class ImportFromSTMT(NamedTuple):
    context: ImportContext
    node: ast.ImportFrom

    def get_imported_modules(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: Module,
    ) -> Iterable[Module]:
        if not self.node.module:
            return

        if _is_builtin_or_stdlib(self.node.module):
            return

        if self.node.level == 0:
            module_name = self.node.module
        else:
            module_name = ".".join(
                base_module.name.split(".")[: -self.node.level]
                + self.node.module.split(".")
            )

        module = Module.from_name(
            mapping,
            project_path,
            module_name,
            self.context,
        )

        if module.py_exists():
            yield module
            return

        if module.init_exists():
            logger.debug(
                "ImportFrom: Unhandled %s: %s",
                base_module.name,
                ".".join([module.name, "__init__"]),
            )
            return

        if module.path.is_dir():
            for alias in self.node.names:
                sub_module = Module.from_name(
                    mapping,
                    project_path,
                    ".".join([module.name, alias.name]),
                    self.context,
                )

                if sub_module.py_exists():
                    yield sub_module
                    continue

                if module.init_exists():
                    logger.debug(
                        "ImportFrom: Unhandled %s: %s",
                        base_module.name,
                        ".".join([sub_module.name, "__init__"]),
                    )
                    continue

                logger.debug(
                    "ImportFrom: Unhandled %s: %s",
                    base_module.name,
                    ast.dump(self.node),
                )
            return

        logger.debug(
            "ImportFrom: Unhandled %s: %s",
            base_module.name,
            ast.dump(self.node),
        )


def _is_builtin_or_stdlib(module_name: str) -> bool:
    if module_name in sys.builtin_module_names or module_name in sys.modules:
        # Avail in 3.10: or name in sys.stdlib_module_names
        return True

    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


# .
#   .--cycles--------------------------------------------------------------.
#   |                                     _                                |
#   |                      ___ _   _  ___| | ___  ___                      |
#   |                     / __| | | |/ __| |/ _ \/ __|                     |
#   |                    | (__| |_| | (__| |  __/\__ \                     |
#   |                     \___|\__, |\___|_|\___||___/                     |
#   |                          |___/                                       |
#   '----------------------------------------------------------------------'


ImportCycle = Tuple[str, ...]
ImportChain = Sequence[str]


@dataclass
class CycleAndChains:
    cycle: ImportCycle
    chains: List[ImportChain] = field(default_factory=list)


def _find_import_cycles(imports_by_module: ImportsByModule) -> Sequence[CycleAndChains]:
    detector = DetectImportCycles(imports_by_module)
    detector.detect_cycles()
    return detector.cycles


@dataclass(frozen=True)
class DetectImportCycles:
    _imports_by_module: ImportsByModule
    _cycles: Dict[ImportChain, CycleAndChains] = field(default_factory=dict)

    @property
    def cycles(self) -> Sequence[CycleAndChains]:
        return sorted(self._cycles.values(), key=lambda icwc: icwc.cycle)

    def detect_cycles(self) -> None:
        for module, imported_modules in self._imports_by_module.items():
            self._detect_cycles([module.name], imported_modules)

    def _detect_cycles(
        self,
        base_chain: List[str],
        imported_modules: Sequence[Module],
    ) -> None:
        for module in imported_modules:
            chain = base_chain + [module.name]

            if module.name in base_chain:
                self._add_cycle(chain)
                return

            self._detect_cycles(
                chain,
                self._imports_by_module.get(module, []),
            )

    def _add_cycle(self, chain: ImportChain) -> None:
        first_idx = chain.index(chain[-1])
        cycle = tuple(chain[first_idx:])
        self._cycles.setdefault(
            tuple(sorted(cycle[:-1])), CycleAndChains(cycle)
        ).chains.append(chain)


# .
#   .--graph---------------------------------------------------------------.
#   |                                           _                          |
#   |                      __ _ _ __ __ _ _ __ | |__                       |
#   |                     / _` | '__/ _` | '_ \| '_ \                      |
#   |                    | (_| | | | (_| | |_) | | | |                     |
#   |                     \__, |_|  \__,_| .__/|_| |_|                     |
#   |                     |___/          |_|                               |
#   '----------------------------------------------------------------------'


def _make_graph(
    project_path: Path, args: argparse.Namespace, edges: Sequence[ImportEdge]
) -> Digraph:
    target_dir = Path(os.path.abspath(__file__)).parent.parent.joinpath("outputs")
    target_dir.mkdir(parents=True, exist_ok=True)

    d = Digraph(
        "unix",
        filename=target_dir.joinpath(
            "%s-import-cycles.gv" % args.folder.replace("/", "-")
        ),
    )

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(edge.module)
            ds.node(edge.imports)
            ds.attr("edge", color=edge.color)

            if edge.title:
                ds.edge(edge.module, edge.imports, edge.title)
            else:
                ds.edge(edge.module, edge.imports)

    return d.unflatten(stagger=50)


class ImportEdge(NamedTuple):
    title: str
    module: str
    imports: str
    color: str
    context: ImportContext


def _make_edges(
    args: argparse.Namespace,
    imports_by_module: ImportsByModule,
    import_cycles: Sequence[CycleAndChains],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(imports_by_module, import_cycles)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    imports_by_module: ImportsByModule,
    import_cycles: Sequence[CycleAndChains],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for module, these_imports_by_module in imports_by_module.items():
        for imported_module in these_imports_by_module:
            import_cycle = _is_in_cycle(module, imported_module.name, import_cycles)
            edges.add(
                ImportEdge(
                    "",
                    module.name,
                    imported_module.name,
                    "black" if import_cycle is None else "red",
                    tuple(),
                )
            )
    return sorted(edges)


def _is_in_cycle(
    module: Module,
    the_import: str,
    import_cycles: Sequence[CycleAndChains],
) -> Optional[CycleAndChains]:
    for import_cycle in import_cycles:
        try:
            idx = import_cycle.cycle.index(module)
        except ValueError:
            continue

        if import_cycle.cycle[idx + 1] == the_import:
            return import_cycle
    return None


def _make_only_cycles_edges(
    imports_by_module: ImportsByModule,
    import_cycles: Sequence[CycleAndChains],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles):
        color = "#%02x%02x%02x" % (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )
        module = import_cycle.cycle[0]
        for module_name in import_cycle.cycle[1:]:
            edges.add(
                ImportEdge(
                    str(nr + 1),
                    module,
                    module_name,
                    color,
                    tuple(),
                )
            )
            module = module_name
    return sorted(edges)


# .
#   .--helper--------------------------------------------------------------.
#   |                    _          _                                      |
#   |                   | |__   ___| |_ __   ___ _ __                      |
#   |                   | '_ \ / _ \ | '_ \ / _ \ '__|                     |
#   |                   | | | |  __/ | |_) |  __/ |                        |
#   |                   |_| |_|\___|_| .__/ \___|_|                        |
#   |                                |_|                                   |
#   '----------------------------------------------------------------------'


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
        "--map",
        nargs="+",
        help=(
            "Hack with symlinks: Sanitize module paths or import statments,"
            " ie. PREFIX:SHORT, eg.:"
            " from path.to.SHORT.module -> PREFIX/path/to/SHORT/module.py"
            " PREFIX/path/to/SHORT/module.py -> path.to.SHORT.module"
        ),
    )
    parser.add_argument(
        "--project-path",
        help="Path to project",
        required=True,
    )
    parser.add_argument(
        "folder",
        help="Folder for cycle analysis which is appended to project path.",
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


def _get_imports_by_module(
    mapping: Mapping[str, str],
    project_path: Path,
    visitors: Iterable[NodeVisitorImports],
) -> ImportsByModule:
    return {
        module: [
            imported_module
            for import_stmt in visitor.import_stmts
            for imported_module in import_stmt.get_imported_modules(
                mapping, project_path, module
            )
        ]
        for visitor in visitors
        for module in (
            Module.from_path(
                mapping,
                project_path,
                visitor.path,
                tuple(),
            ),
        )
    }


class Module(NamedTuple):
    path: Path
    name: str
    # context: ImportContext

    @classmethod
    def from_name(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_name: str,
        context: ImportContext,
    ) -> Module:
        parts = module_name.split(".")
        for key, value in mapping.items():
            if value in parts:
                parts = [key] + parts
                break

        return cls(
            path=project_path.joinpath(Path(*parts)),
            name=module_name,
            # context=context,
        )

    @classmethod
    def from_path(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_path: Path,
        context: ImportContext,
    ) -> Module:
        parts = module_path.relative_to(project_path).with_suffix("").parts
        for key, value in mapping.items():
            if key == parts[0] and value in parts[1:]:
                parts = parts[1:]
                break

        return cls(
            path=module_path.with_suffix(""),
            name=".".join(parts),
            # context=context,
        )

    def py_exists(self) -> bool:
        return self.path.with_suffix(".py").exists()

    def init_exists(self) -> bool:
        return self.path.is_dir() and self.path.joinpath("__init__.py").exists()


ImportsByModule = Mapping[Module, Sequence[Module]]


def _show_import_cycles(
    args: argparse.Namespace, import_cycles: Sequence[CycleAndChains]
) -> None:
    if import_cycles:
        print("===== Found import cycles ====")
        for import_cycle in import_cycles:
            print("Cycle:", import_cycle.cycle)
            if not args.verbose:
                continue

            for chain in import_cycle.chains:
                print("  In chain:", chain)

        print("Amount of cycles: %s" % len(import_cycles))


def _get_return_code(import_cycles: Sequence[CycleAndChains]) -> bool:
    return bool(import_cycles)


# .


def main(argv: Sequence[str]) -> int:
    args = _parse_arguments(argv)

    _setup_logging(args)

    project_path = Path(args.project_path)
    if not project_path.exists() or not project_path.is_dir():
        logger.debug("No such directory: %s", project_path)
        return 1

    folder_path = project_path.joinpath(args.folder)
    if not folder_path.exists():
        logger.debug("No such directory: %s", folder_path)
        return 1

    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    logger.info("Get Python files")
    python_files = _get_python_files(folder_path)

    logger.info("Visit Python files")
    visitors = _visit_python_files(python_files)

    logger.info("Get imports of modules")
    imports_by_module = _get_imports_by_module(mapping, project_path, visitors)
    logger.info("Found %d modules", len(imports_by_module))
    logger.info("Found %d imported modules", sum(map(len, imports_by_module.values())))

    logger.info("Detect import cycles")
    import_cycles = _find_import_cycles(imports_by_module)

    _show_import_cycles(args, import_cycles)

    if args.graph == "no":
        return _get_return_code(import_cycles)

    if not (edges := _make_edges(args, imports_by_module, import_cycles)):
        logger.debug("No edges for graphing")
        return _get_return_code(import_cycles)

    logger.info("Make graph")
    graph = _make_graph(project_path, args, edges)
    graph.view()

    return _get_return_code(import_cycles)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
