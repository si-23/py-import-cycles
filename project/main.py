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
# handle __init__.py?

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
# what to do with Packages in _visit_python_file?

# TODO #5
# Handle star imports

# TODO #6
# Handle relative imports properly

# TODO #7
# Exclude specific folders like tests...

# TODO #8
# more log levels: verbose: log nrealy every step
#                  debug: only log steps which are useful for dev


# Cases:
# import path.to.mod
# import path.to.mod as my_mod

# from path.to.mod import sub_mod
# from path.to.mod import sub_mod as my_sub_mod

# from path.to.mod import func/class
# from path.to.mod import func/class as my_func/class


#   .--modules-------------------------------------------------------------.
#   |                                   _       _                          |
#   |               _ __ ___   ___   __| |_   _| | ___  ___                |
#   |              | '_ ` _ \ / _ \ / _` | | | | |/ _ \/ __|               |
#   |              | | | | | | (_) | (_| | |_| | |  __/\__ \               |
#   |              |_| |_| |_|\___/ \__,_|\__,_|_|\___||___/               |
#   |                                                                      |
#   '----------------------------------------------------------------------'


class Package(NamedTuple):
    path: Path
    name: str


class PyModule(NamedTuple):
    path: Path
    name: str


TModule = Union[Package, PyModule]
ImportsByModule = Mapping[TModule, Sequence[TModule]]


class Module:
    @classmethod
    def from_name(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_name: str,
    ) -> Optional[TModule]:
        parts = module_name.split(".")
        for key, value in mapping.items():
            if value in parts:
                parts = [key] + parts
                break

        module_path = project_path.joinpath(Path(*parts))

        if module_path.is_dir():
            return Package(
                path=module_path,
                name=module_name,
            )

        if (py_module_path := module_path.with_suffix(".py")).exists():
            return PyModule(
                path=py_module_path,
                name=module_name,
            )

        return None

    @classmethod
    def from_path(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_path: Path,
    ) -> Optional[TModule]:
        parts = module_path.relative_to(project_path).with_suffix("").parts
        for key, value in mapping.items():
            if key == parts[0] and value in parts[1:]:
                parts = parts[1:]
                break

        module_name = ".".join(parts)

        if module_path.is_dir():
            return Package(
                path=module_path,
                name=module_name,
            )

        if module_path.is_file() and module_path.suffix == ".py":
            return PyModule(
                path=module_path,
                name=module_name,
            )

        return None


# .
#   .--files---------------------------------------------------------------.
#   |                           __ _ _                                     |
#   |                          / _(_) | ___  ___                           |
#   |                         | |_| | |/ _ \/ __|                          |
#   |                         |  _| | |  __/\__ \                          |
#   |                         |_| |_|_|\___||___/                          |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def _get_python_files(
    project_path: Path, folders: Sequence[str], namespaces: Sequence[str]
) -> Iterable[Path]:
    for fp in project_path.iterdir():
        if not fp.is_dir():
            continue

        if fp.name not in folders:
            continue

        yield from _get_python_files_recursively(project_path, fp, namespaces)


def _get_python_files_recursively(
    project_path: Path, path: Path, namespaces: Sequence[str]
) -> Iterable[Path]:
    if path.is_dir():
        for fp in path.iterdir():
            yield from _get_python_files_recursively(project_path, fp, namespaces)

    if path.suffix != ".py" or path.stem == "__init__":
        return

    if all(ns in path.parts for ns in namespaces):
        yield path.resolve()
        return

    logger.debug("Ignore path %r", path.relative_to(project_path))


# .
#   .--node visitor--------------------------------------------------------.
#   |                        _              _     _ _                      |
#   |        _ __   ___   __| | ___  __   _(_)___(_) |_ ___  _ __          |
#   |       | '_ \ / _ \ / _` |/ _ \ \ \ / / / __| | __/ _ \| '__|         |
#   |       | | | | (_) | (_| |  __/  \ V /| \__ \ | || (_) | |            |
#   |       |_| |_|\___/ \__,_|\___|   \_/ |_|___/_|\__\___/|_|            |
#   |                                                                      |
#   '----------------------------------------------------------------------'


ImportSTMT = Union[ast.Import, ast.ImportFrom]


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._import_stmts: List[ImportSTMT] = []

    @property
    def import_stmts(self) -> Sequence[ImportSTMT]:
        return self._import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._import_stmts.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._import_stmts.append(node)


class ImportedModulesExtractor:
    def __init__(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: TModule,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._mapping = mapping
        self._project_path = project_path
        self._base_module = base_module
        self._import_stmts = import_stmts

        self._imported_modules: List[TModule] = []

    @property
    def imported_modules(self) -> Sequence[TModule]:
        return self._imported_modules

    def extract(self) -> Sequence[TModule]:
        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                self._add_imported_modules_from_aliases(import_stmt.names)

            elif isinstance(import_stmt, ast.ImportFrom):
                self._add_imported_from_modules(import_stmt)

        return self._imported_modules

    def _add_imported_from_modules(self, import_from_stmt: ast.ImportFrom) -> None:
        if not import_from_stmt.module:
            return

        if self._is_builtin_or_stdlib(import_from_stmt.module):
            return

        if import_from_stmt.level == 0:
            module_name = import_from_stmt.module
        else:
            module_name = ".".join(
                self._base_module.name.split(".")[: -import_from_stmt.level]
                + import_from_stmt.module.split(".")
            )

        module = Module.from_name(
            self._mapping,
            self._project_path,
            module_name,
        )

        if module is None:
            logger.debug(
                "Unhandled import in %s: %s",
                self._base_module.name,
                ast.dump(import_from_stmt),
            )
            return

        if isinstance(module, PyModule):
            self._imported_modules.append(module)
            return

        if isinstance(module, Package):
            self._add_imported_modules_from_aliases(
                import_from_stmt.names,
                from_name=module.name,
            )

    def _add_imported_modules_from_aliases(
        self, aliases: Sequence[ast.alias], from_name: str = ""
    ) -> None:
        for alias in aliases:
            if self._is_builtin_or_stdlib(alias.name):
                continue

            module = Module.from_name(
                self._mapping,
                self._project_path,
                ".".join([from_name, alias.name]) if from_name else alias.name,
            )

            if module is None:
                logger.debug(
                    "Unhandled import in %s: %s",
                    self._base_module.name,
                    ast.dump(alias),
                )
                continue

            self._imported_modules.append(module)

    @staticmethod
    def _is_builtin_or_stdlib(module_name: str) -> bool:
        if module_name in sys.builtin_module_names or module_name in sys.modules:
            # Avail in 3.10: or name in sys.stdlib_module_names
            return True

        try:
            return importlib.util.find_spec(module_name) is not None
        except ModuleNotFoundError:
            return False


def _visit_python_files(
    mapping: Mapping[str, str],
    project_path: Path,
    files: Iterable[Path],
    recursively: bool,
) -> ImportsByModule:
    imports_by_module = {
        visited[0]: visited[1]
        for path in files
        if (visited := _visit_python_file(mapping, project_path, path)) is not None
    }

    if not recursively:
        return imports_by_module

    # Collect imported modules and their imports
    for module in set(
        imported_module
        for imported_modules in imports_by_module.values()
        for imported_module in imported_modules
    ).difference(imports_by_module):
        if module in imports_by_module:
            continue

        if (visited := _visit_python_file(mapping, project_path, module.path)) is None:
            continue

        imports_by_module[visited[0]] = visited[1]

    return imports_by_module


def _visit_python_file(
    mapping: Mapping[str, str],
    project_path: Path,
    path: Path,
) -> Optional[Tuple[TModule, Sequence[TModule]]]:
    module = Module.from_path(mapping, project_path, path)

    if module is None:
        # Should not happen
        logger.debug("No such Python module: %s", module)
        return None

    if isinstance(module, Package):
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

    visitor = NodeVisitorImports(module.path)
    visitor.visit(tree)

    extractor = ImportedModulesExtractor(
        mapping,
        project_path,
        module,
        visitor.import_stmts,
    )
    extractor.extract()

    if imported_modules := extractor.imported_modules:
        return module, extractor.imported_modules

    return None


def _get_entry_points(imports_by_module: ImportsByModule) -> ImportsByModule:
    if not (
        entry_points := set(imports_by_module).difference(
            imported_module
            for imported_modules in imports_by_module.values()
            for imported_module in imported_modules
        )
    ):
        entry_points = set(imports_by_module)
    return sorted(entry_points)


# .
#   .--cycles--------------------------------------------------------------.
#   |                                     _                                |
#   |                      ___ _   _  ___| | ___  ___                      |
#   |                     / __| | | |/ __| |/ _ \/ __|                     |
#   |                    | (__| |_| | (__| |  __/\__ \                     |
#   |                     \___|\__, |\___|_|\___||___/                     |
#   |                          |___/                                       |
#   '----------------------------------------------------------------------'


ChainWithCycle = Tuple[TModule, ...]
ChainsWithCycle = Sequence[ChainWithCycle]


def _find_chains_with_cycle(
    args: argparse.Namespace,
    entry_points: Sequence[TModule],
    imports_by_module: ImportsByModule,
) -> ChainsWithCycle:
    detector = DetectChainsWithCycle(
        entry_points, imports_by_module, args.raise_on_first_cycle
    )
    try:
        detector.detect_cycles()
    except ChainWithCycleError as e:
        pass
    return detector.cycles


class ChainWithCycleError(Exception):
    pass


@dataclass(frozen=True)
class DetectChainsWithCycle:
    _entry_points: Sequence[TModule]
    _imports_by_module: ImportsByModule
    _raise_on_first_cycle: bool
    _cycles: Dict[ChainWithCycle, ChainWithCycle] = field(default_factory=dict)
    _checked_modules: Set[TModule] = field(default_factory=set)

    @property
    def cycles(self) -> ChainsWithCycle:
        return sorted(self._cycles.values())

    def detect_cycles(self) -> None:
        len_entry_points = len(self._entry_points)
        for nr, module in enumerate(self._entry_points):
            if module in self._checked_modules:
                continue

            logger.debug(
                "Check %s (Nr %s of %s)",
                module.name,
                nr + 1,
                len_entry_points,
            )

            self._detect_cycles([module], self._imports_by_module.get(module, []))

    def _detect_cycles(
        self,
        base_chain: List[TModule],
        imported_modules: Sequence[TModule],
    ) -> None:
        for module in imported_modules:
            chain = base_chain + [module]

            if module in base_chain:
                self._add_cycle(chain)
                if self._raise_on_first_cycle:
                    raise ChainWithCycleError(chain)
                return

            self._detect_cycles(
                chain,
                self._imports_by_module.get(module, []),
            )

            self._checked_modules.add(module)

    def _add_cycle(self, chain: Sequence[str]) -> None:
        cycle = _extract_cycle_from_chain(chain)
        if (short := tuple(sorted(cycle[:-1]))) not in self._cycles:
            self._cycles[short] = chain
            logger.debug("  Found cycle in: %s", [e.name for e in chain])


# .
#   .--graph---------------------------------------------------------------.
#   |                                           _                          |
#   |                      __ _ _ __ __ _ _ __ | |__                       |
#   |                     / _` | '__/ _` | '_ \| '_ \                      |
#   |                    | (_| | | | (_| | |_) | | | |                     |
#   |                     \__, |_|  \__,_| .__/|_| |_|                     |
#   |                     |___/          |_|                               |
#   '----------------------------------------------------------------------'


def _make_graph(args: argparse.Namespace, edges: Sequence[ImportEdge]) -> Digraph:
    target_dir = Path(os.path.abspath(__file__)).parent.parent.joinpath("outputs")
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = "%s-%s-%s-import-cycles.gv" % (
        "-".join(Path(args.project_path).parts[1:]),
        "-".join(sorted(args.folders)),
        "-".join(sorted(args.namespaces)),
    )

    d = Digraph("unix", filename=target_dir.joinpath(filename))

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(
                edge.from_module.name,
                shape=_get_shape(edge.from_module),
                style="filled",
                fillcolor=edge.from_module_color,
            )
            ds.node(
                edge.to_module.name,
                shape=_get_shape(edge.to_module),
                style="filled",
                fillcolor=edge.from_module_color,
            )
            ds.attr("edge", color=edge.edge_color)

            if edge.title:
                ds.edge(edge.from_module.name, edge.to_module.name, edge.title)
            else:
                ds.edge(edge.from_module.name, edge.to_module.name)

    return d.unflatten(stagger=50)


def _get_shape(module: TModule) -> str:
    return "" if isinstance(module, PyModule) else "box"


class ImportEdge(NamedTuple):
    title: str
    from_module: TModule
    from_module_color: str
    to_module: TModule
    to_module_color: str
    edge_color: str


def _make_edges(
    args: argparse.Namespace,
    imports_by_module: ImportsByModule,
    chains_with_cycle: ChainsWithCycle,
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, chains_with_cycle)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(imports_by_module, chains_with_cycle)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    imports_by_module: ImportsByModule,
    chains_with_cycle: ChainsWithCycle,
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for module, imported_modules in imports_by_module.items():
        for imported_module in imported_modules:
            edges.add(
                ImportEdge(
                    "",
                    module,
                    "white",
                    imported_module,
                    "white",
                    (
                        "red"
                        if _has_cycle(module, imported_module, chains_with_cycle)
                        is None
                        else "black"
                    ),
                )
            )
    return sorted(edges)


def _has_cycle(
    module: TModule, imported_module: TModule, chains_with_cycle: ChainsWithCycle
) -> bool:
    for chain_with_cycle in chains_with_cycle:
        cycle = _extract_cycle_from_chain(chain_with_cycle)

        try:
            idx = cycle.index(module)
        except ValueError:
            continue

        if cycle[idx + 1] == imported_module:
            return True
    return False


def _make_only_cycles_edges(
    imports_by_module: ImportsByModule,
    chains_with_cycle: ChainsWithCycle,
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for nr, chain_with_cycle in enumerate(chains_with_cycle):
        cycle = _extract_cycle_from_chain(chain_with_cycle)

        color = "#%02x%02x%02x" % (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        start_module = cycle[0]
        for module in cycle[1:]:
            edges.add(
                ImportEdge(
                    "%s (%s)" % (str(nr + 1), len(cycle) - 1),
                    start_module,
                    "gray" if start_module == cycle[0] else "white",
                    module,
                    "gray" if module == cycle[0] else "white",
                    color,
                )
            )
            start_module = module
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
        allow_abbrev=False,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="show additional information for debug purposes",
    )
    parser.add_argument(
        "--graph",
        choices=["all", "only-cycles", "no"],
        default="only-cycles",
        help="how the graph is drawn; default: only-cycles",
    )
    parser.add_argument(
        "--map",
        nargs="+",
        help=(
            "hack with symlinks: Sanitize module paths or import statments,"
            " ie. PREFIX:SHORT, eg.:"
            " from path.to.SHORT.module -> PREFIX/path/to/SHORT/module.py"
            " PREFIX/path/to/SHORT/module.py -> path.to.SHORT.module"
        ),
    )
    parser.add_argument(
        "--project-path",
        required=True,
        help="path to project",
    )
    parser.add_argument(
        "--folders",
        nargs="+",
        required=True,
        help="collect Python files from top-level folders",
    )
    parser.add_argument(
        "--namespaces",
        nargs="+",
        required=True,
        help="Visit Python file if all of these namespaces are part of this file path",
    )

    parser.add_argument(
        "--recursively",
        action="store_true",
        help="Visit Python modules or packages if not yet collected from Python files.",
    )
    parser.add_argument(
        "--raise-on-first-cycle",
        action="store_true",
        help="Stop if first cycle is found",
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

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _extract_cycle_from_chain(chain: Sequence[TModule]) -> Sequence[TModule]:
    first_idx = chain.index(chain[-1])
    return chain[first_idx:]


# .


def main(argv: Sequence[str]) -> int:
    args = _parse_arguments(argv)

    _setup_logging(args)

    project_path = Path(args.project_path)
    if not project_path.exists() or not project_path.is_dir():
        logger.debug("No such directory: %s", project_path)
        return 1

    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    logger.info("Get Python files")
    python_files = _get_python_files(project_path, args.folders, args.namespaces)

    logger.info("Visit Python files, get imports by module")
    imports_by_module = _visit_python_files(
        mapping, project_path, python_files, args.recursively
    )

    logger.info("Calculate entry points")
    entry_points = _get_entry_points(imports_by_module)

    logger.info("Detect import cycles")
    chains_with_cycle = _find_chains_with_cycle(args, entry_points, imports_by_module)
    logger.info("Found %d import cycles", len(chains_with_cycle))
    return_code = bool(chains_with_cycle)

    for chain_with_cycle in chains_with_cycle:
        sys.stderr.write("Found cycle in: %s\n" % [e.name for e in chain_with_cycle])

    if args.graph == "no":
        return return_code

    if not (edges := _make_edges(args, imports_by_module, chains_with_cycle)):
        logger.debug("No edges for graphing")
        return return_code

    logger.info("Make graph")
    graph = _make_graph(args, edges)
    graph.view()

    return return_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
