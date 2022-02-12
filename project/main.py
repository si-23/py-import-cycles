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
# use context in graph (nested import stmt)


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


ImportContext = Tuple[Union[ast.If, ast.Try, ast.ClassDef, ast.FunctionDef], ...]


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
    return sorted(visitors, key=lambda v: v.path)


class ImportSTMT(NamedTuple):
    context: ImportContext
    node: ast.Import

    def get_imported_module_names(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module_name: str,
    ) -> Sequence[str]:
        imported_module_names: List[str] = []
        for alias in self.node.names:
            if _is_builtin_or_stdlib(alias.name):
                continue

            if (
                module_path_and_name := ModulePathAndName.make(
                    mapping, project_path, alias.name
                )
            ).py_exists():
                if module_path_and_name.name not in imported_module_names:
                    imported_module_names.append(module_path_and_name.name)
                continue

            if module_path_and_name.init_exists():
                logger.debug(
                    "Unhandled %s: __init__: %s", base_module_name, module_path_and_name
                )
                continue

            logger.debug("Unhandled %s: %s", base_module_name, ast.dump(self.node))

        return imported_module_names


class ImportFromSTMT(NamedTuple):
    context: ImportContext
    node: ast.ImportFrom

    def get_imported_module_names(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module_name: str,
    ) -> Sequence[str]:
        if not self.node.module:
            return []

        if _is_builtin_or_stdlib(self.node.module):
            return []

        if self.node.level == 0:
            module_name = self.node.module
        else:
            module_name = ".".join(
                base_module_name.split(".")[: -self.node.level]
                + self.node.module.split(".")
            )

        if (
            module_path_and_name := ModulePathAndName.make(
                mapping, project_path, module_name
            )
        ).py_exists():
            return [module_path_and_name.name]

        if module_path_and_name.init_exists():
            logger.debug(
                "Unhandled %s: __init__: %s", base_module_name, module_path_and_name
            )
            return []

        if module_path_and_name.path.is_dir():
            imported_module_names: List[str] = []
            for alias in self.node.names:
                sub_module_path_and_name = ModulePathAndName.make(
                    mapping,
                    project_path,
                    ".".join([module_path_and_name.name, alias.name]),
                )

                if sub_module_path_and_name.py_exists():
                    if sub_module_path_and_name.name not in imported_module_names:
                        imported_module_names.append(sub_module_path_and_name.name)
                    continue

                logger.debug("Unhandled %s: %s", base_module_name, ast.dump(self.node))

            return imported_module_names

        logger.debug("Unhandled %s: %s", base_module_name, ast.dump(self.node))
        return []


def _is_builtin_or_stdlib(module_name: str) -> bool:
    if module_name in sys.builtin_module_names or module_name in sys.modules:
        # Avail in 3.10: or name in sys.stdlib_module_names
        return True

    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


class ModulePathAndName(NamedTuple):
    path: Path
    name: str

    def py_exists(self) -> bool:
        return self.path.with_suffix(".py").exists()

    def init_exists(self) -> bool:
        return (
            self.path.is_dir()
            and self.path.joinpath("__init__").with_suffix(".py").exists()
        )

    @classmethod
    def make(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_name: str,
    ) -> ModulePathAndName:
        parts = module_name.split(".")
        for key, value in mapping.items():
            if value in parts:
                parts = [key] + parts
                break

        return cls(
            path=project_path.joinpath(Path(*parts)),
            name=module_name,
        )


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


def _find_import_cycles(module_imports: ModuleImports) -> Sequence[CycleAndChains]:
    detector = DetectImportCycles(module_imports)
    detector.detect_cycles()
    return detector.cycles


@dataclass(frozen=True)
class DetectImportCycles:
    _module_imports: ModuleImports
    _cycles: Dict[ImportChain, CycleAndChains] = field(default_factory=dict)

    @property
    def cycles(self) -> Sequence[CycleAndChains]:
        return sorted(self._cycles.values(), key=lambda icwc: icwc.cycle)

    def detect_cycles(self) -> None:
        for module_name, module_imports in self._module_imports.items():
            self._detect_cycles([module_name], module_imports)

    def _detect_cycles(
        self,
        base_chain: List[str],
        module_imports: Sequence[ModuleImport],
    ) -> None:
        for module_import in module_imports:
            chain = base_chain + [module_import.module_name]

            if module_import.module_name in base_chain:
                self._add_cycle(chain)
                return

            self._detect_cycles(
                chain,
                self._module_imports.get(module_import.module_name, []),
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

            prefix = ">" if edge.context else ""

            if edge.title:
                ds.edge(edge.module, prefix + edge.imports, edge.title)
            else:
                ds.edge(edge.module, prefix + edge.imports)

    return d.unflatten(stagger=50)


class ImportEdge(NamedTuple):
    title: str
    module: str
    imports: str
    color: str
    context: ImportContext


def _make_edges(
    args: argparse.Namespace,
    module_imports: ModuleImports,
    import_cycles: Sequence[CycleAndChains],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(module_imports, import_cycles)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(module_imports, import_cycles)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    module_imports: ModuleImports,
    import_cycles: Sequence[CycleAndChains],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for module, these_module_imports in module_imports.items():
        for module_import in these_module_imports:
            import_cycle = _is_in_cycle(
                module, module_import.module_name, import_cycles
            )
            edges.add(
                ImportEdge(
                    "",
                    module,
                    module_import.module_name,
                    "black" if import_cycle is None else "red",
                    tuple(),
                )
            )
    return sorted(edges)


def _is_in_cycle(
    module: str,
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
    module_imports: ModuleImports,
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
            # if (module_import := module_imports.get(module_name)) is None:
            #     context = tuple()
            # else:
            #     context = module_import.context

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


@dataclass
class ModuleImport:
    module_name: str
    context: ImportContext


ModuleImports = Mapping[str, Sequence[ModuleImport]]


def _get_module_imports(
    mapping: Mapping[str, str],
    project_path: Path,
    visitors: Sequence[NodeVisitorImports],
) -> ModuleImports:
    module_imports: Dict[str, List[ModuleImport]] = {}
    for visitor in visitors:
        if (
            module_name_from_path := _get_module_name_from_path(
                mapping, project_path, visitor.path
            )
        ) is None:
            continue

        for import_stmt in visitor.imports_stmt:
            for imported_module_name in import_stmt.get_imported_module_names(
                mapping,
                project_path,
                module_name_from_path,
            ):
                module_imports.setdefault(module_name_from_path, []).append(
                    ModuleImport(imported_module_name, import_stmt.context)
                )

        for import_from_stmt in visitor.imports_from_stmt:
            for imported_module_name in import_from_stmt.get_imported_module_names(
                mapping,
                project_path,
                module_name_from_path,
            ):
                module_imports.setdefault(module_name_from_path, []).append(
                    ModuleImport(imported_module_name, import_from_stmt.context)
                )

    return module_imports


def _get_module_name_from_path(
    mapping: Mapping[str, str], project_path: Path, module_path: Path
) -> Optional[str]:
    rel_path = module_path.relative_to(project_path).with_suffix("")
    if rel_path.name == "__init__":
        logger.debug("Ignore %s", module_path)
        return None

    parts = rel_path.parts
    for key in mapping:
        if key == parts[0]:
            parts = parts[1:]
            break

    return ".".join(parts)


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

    mapping = (
        dict([entry.split(":") for entry in args.map]) if args.map is not None else {}
    )

    logger.info("Get Python files")
    python_files = _get_python_files(folder_path)

    logger.info("Load Python files")
    loaded_python_files = _load_python_contents(set(python_files))

    logger.info("Visit Python contents")
    visitors = _visit_python_contents(loaded_python_files)

    logger.info("Parse Python contents into module relationships")
    module_imports = _get_module_imports(mapping, project_path, visitors)
    logger.info("Found %d relationships", len(module_imports))

    logger.info("Detect import cycles")
    import_cycles = _find_import_cycles(module_imports)

    _show_import_cycles(args, import_cycles)

    if args.graph == "no":
        return _get_return_code(import_cycles)

    if not (edges := _make_edges(args, module_imports, import_cycles)):
        logger.debug("No edges for graphing")
        return _get_return_code(import_cycles)

    logger.info("Make graph")
    graph = _make_graph(project_path, args, edges)
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
