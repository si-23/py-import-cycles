#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import importlib
import logging
import os
import random
import sys
from pathlib import Path
from typing import (
    Dict,
    Generic,
    Iterable,
    List,
    Literal,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from graphviz import Digraph

from project.dfs import depth_first_search
from project.tarjan import strongly_connected_components as tarjan_scc

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


Module = Union[Package, PyModule]


def make_module_from_name(
    mapping: Mapping[str, str],
    project_path: Path,
    module_name: str,
) -> Optional[Module]:
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


def make_module_from_path(
    mapping: Mapping[str, str],
    project_path: Path,
    module_path: Path,
) -> Optional[Module]:
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
        base_module: Module,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._mapping = mapping
        self._project_path = project_path
        self._base_module = base_module
        self._import_stmts = import_stmts

        self._imported_modules: List[Module] = []

    @property
    def imported_modules(self) -> Sequence[Module]:
        return self._imported_modules

    def extract(self) -> Sequence[Module]:
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

        module = make_module_from_name(
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

            module = make_module_from_name(
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
            return importlib.util.find_spec(module_name) is not None  # type: ignore[attr-defined]
        except ModuleNotFoundError:
            return False


def _visit_python_files(
    mapping: Mapping[str, str],
    project_path: Path,
    files: Iterable[Path],
    recursively: bool,
) -> Mapping[Module, Sequence[Module]]:
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
) -> Optional[Tuple[Module, Sequence[Module]]]:
    module = make_module_from_path(mapping, project_path, path)

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
        return module, imported_modules

    return None


# .
#   .--cycles--------------------------------------------------------------.
#   |                                     _                                |
#   |                      ___ _   _  ___| | ___  ___                      |
#   |                     / __| | | |/ __| |/ _ \/ __|                     |
#   |                    | (__| |_| | (__| |  __/\__ \                     |
#   |                     \___|\__, |\___|_|\___||___/                     |
#   |                          |___/                                       |
#   '----------------------------------------------------------------------'


def detect_cycles(
    strategy: Literal["dfs", "johnson", "tarjan"],
    graph: Mapping[Module, Sequence[Module]],
) -> Iterable[Tuple[Module, ...]]:
    if strategy == "dfs":
        return depth_first_search(graph)
    if strategy == "johnson":
        return Johnson[Module](graph).detect()
    if strategy == "tarjan":
        return (scc for scc in tarjan_scc(graph) if len(scc) > 1)
    raise NotImplementedError()


T = TypeVar("T")


class Johnson(Generic[T]):
    def __init__(self, graph: Mapping[T, Sequence[T]]) -> None:
        self._adjacency_list = graph
        # Does not matter if it's a Package or PyModule
        self._root = Package(Path(), "root")
        self._blocked: Dict[T, bool] = {}

    def detect(self) -> Iterable[Tuple[T, ...]]:
        pass


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
    edges: Sequence[ImportEdge],
    outputs_filepath: Path,
) -> Digraph:
    d = Digraph("unix", filename=outputs_filepath.with_suffix(".gv"))

    with d.subgraph() as ds:
        for edge in edges:
            ds.node(
                edge.from_module.name,
                shape=_get_shape(edge.from_module),
            )

            ds.node(
                edge.to_module.name,
                shape=_get_shape(edge.to_module),
            )

            ds.attr("edge", color=edge.edge_color)

            if edge.title:
                ds.edge(edge.from_module.name, edge.to_module.name, edge.title)
            else:
                ds.edge(edge.from_module.name, edge.to_module.name)

    return d.unflatten(stagger=50)


def _get_shape(module: Module) -> str:
    return "" if isinstance(module, PyModule) else "box"


class ImportEdge(NamedTuple):
    title: str
    from_module: Module
    to_module: Module
    edge_color: str


def _make_edges(
    args: argparse.Namespace,
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[Tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(import_cycles)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[Tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for module, imported_modules in imports_by_module.items():
        for imported_module in imported_modules:
            edges.add(
                ImportEdge(
                    "",
                    module,
                    imported_module,
                    (
                        "red"
                        if _has_cycle(module, imported_module, import_cycles) is None
                        else "black"
                    ),
                )
            )
    return sorted(edges)


def _has_cycle(
    module: Module,
    imported_module: Module,
    import_cycles: Sequence[Tuple[Module, ...]],
) -> bool:
    for import_cycle in import_cycles:
        try:
            idx = import_cycle.index(module)
        except ValueError:
            continue

        if import_cycle[idx + 1] == imported_module:
            return True
    return False


def _make_only_cycles_edges(
    import_cycles: Sequence[Tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles, start=1):
        color = "#%02x%02x%02x" % (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        start_module = import_cycle[0]
        for next_module in import_cycle[1:]:
            edges.add(
                ImportEdge(
                    "%s (%s)" % (str(nr), len(import_cycle) - 1),
                    start_module,
                    next_module,
                    color,
                )
            )
            start_module = next_module
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
        "-v",
        "--verbose",
        action="store_true",
        help="show cycles if some are found",
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
        "--strategy",
        choices=["dfs", "johnson", "tarjan"],
        default="dfs",
        help="path-based strong component algorithm",
    )

    parser.add_argument(
        "--store-cycles",
        type=str,
        help="Write cycles to file instead of printing on stderr",
    )

    return parser.parse_args(argv)


def _get_outputs_filepath(args: argparse.Namespace) -> Path:
    target_dir = Path(os.path.abspath(__file__)).parent.parent.joinpath("outputs")
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir.joinpath(
        "%s-%s-%s-import-cycles.log"
        % (
            "-".join(Path(args.project_path).parts[1:]),
            "-".join(sorted(args.folders)),
            "-".join(sorted(args.namespaces)),
        )
    )


def _setup_logging(args: argparse.Namespace, outputs_filepath: Path) -> None:
    log_filepath = outputs_filepath.with_suffix(".log")
    if args.debug:
        sys.stderr.write("Write log to %s\n" % log_filepath)
        log_level = logging.DEBUG
    else:
        log_level = logging.NOTSET

    logger.setLevel(log_level)

    handler = logging.FileHandler(filename=log_filepath)
    handler.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _show_or_store_cycles(
    args: argparse.Namespace,
    import_cycles: Sequence[Tuple[Module, ...]],
) -> None:
    if not import_cycles:
        return

    sys.stderr.write("Found %d import cycles\n" % len(import_cycles))

    if not args.store_cycles:
        if not args.verbose:
            return

        for nr, import_cycle in enumerate(import_cycles, start=1):
            sys.stderr.write("  %d: %s\n" % (nr, [ic.name for ic in import_cycle]))
        return

    with Path(args.store_cycles).open("w") as f:
        f.write("\n".join([str(ic) for ic in import_cycles]))


# .


def main(argv: Sequence[str]) -> int:
    args = _parse_arguments(argv)

    outputs_filepath = _get_outputs_filepath(args)

    _setup_logging(args, outputs_filepath)

    project_path = Path(args.project_path)
    if not project_path.exists() or not project_path.is_dir():
        sys.stderr.write("No such directory: %s\n" % project_path)
        return 1

    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    logger.info("Get Python files")
    python_files = _get_python_files(project_path, args.folders, args.namespaces)

    logger.info("Visit Python files, get imports by module")
    imports_by_module = _visit_python_files(mapping, project_path, python_files, args.recursively)

    logger.info("Detect import cycles with strategy %s", args.strategy)
    unsorted_cycles = detect_cycles(args.strategy, imports_by_module)
    return_code = bool(unsorted_cycles)

    logger.info("Sort import cycles")
    import_cycles = sorted(set(unsorted_cycles), key=len)

    _show_or_store_cycles(args, import_cycles)

    if args.graph == "no":
        return return_code

    # pylint: disable=superfluous-parens
    if not (edges := _make_edges(args, imports_by_module, import_cycles)):
        logger.debug("No edges for graphing")
        return return_code

    logger.info("Make graph")
    graph = _make_graph(edges, outputs_filepath)
    graph.view()

    return return_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
