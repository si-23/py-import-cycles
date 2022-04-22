#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import importlib
import itertools
import logging
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import (
    DefaultDict,
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
from project.typing import Comparable

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
# what to do with RegularPackages in _visit_python_file?

# TODO #5
# Handle star imports

# TODO #6
# Handle relative imports properly

# TODO #7
# Exclude specific folders like tests...

# TODO #8
# more log levels: verbose: log nrealy every step
#                  debug: only log steps which are useful for dev

# TODO #9
# Check shebang

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


class RegularPackage(NamedTuple):
    path: Path
    folder: Path
    name: str


class NamespacePackage(NamedTuple):
    path: Path
    name: str


class PyModule(NamedTuple):
    path: Path
    name: str


Module = Union[RegularPackage, NamespacePackage, PyModule]


def _make_module_from_name(
    mapping: Mapping[str, str], project_path: Path, module_name: str
) -> Optional[Module]:
    parts = module_name.split(".")
    for key, value in mapping.items():
        if value in parts:
            parts = [key] + parts
            break

    module_path = project_path.joinpath(Path(*parts))

    if module_path.is_dir():
        if (init_module_path := module_path / "__init__.py").exists():
            return RegularPackage(
                path=init_module_path,
                folder=module_path,
                name=module_name,
            )

        return NamespacePackage(
            path=module_path,
            name=module_name,
        )

    if (py_module_path := module_path.with_suffix(".py")).exists():
        return PyModule(
            path=py_module_path,
            name=module_name,
        )

    return None


def _make_module_from_path(
    mapping: Mapping[str, str], project_path: Path, module_path: Path
) -> Module:
    def _make_module_name_from_path(
        mapping: Mapping[str, str], project_path: Path, module_path: Path
    ) -> str:
        parts = module_path.relative_to(project_path).with_suffix("").parts

        for key, value in mapping.items():
            if key == parts[0] and value in parts[1:]:
                parts = parts[1:]
                break

        return ".".join(parts)

    if module_path.stem == "__init__":
        folder = Path(*module_path.parts[:-1])
        return RegularPackage(
            path=module_path,
            folder=folder,
            name=_make_module_name_from_path(mapping, project_path, folder),
        )

    return PyModule(
        path=module_path,
        name=_make_module_name_from_path(mapping, project_path, module_path),
    )


# .
#   .--files---------------------------------------------------------------.
#   |                           __ _ _                                     |
#   |                          / _(_) | ___  ___                           |
#   |                         | |_| | |/ _ \/ __|                          |
#   |                         |  _| | |  __/\__ \                          |
#   |                         |_| |_|_|\___||___/                          |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def iter_python_files(project_path: Path, folders: Sequence[str]) -> Iterable[Path]:
    for f in folders:
        yield from (p.resolve() for p in (project_path / f).glob("**/*.py"))


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
    def __init__(self) -> None:
        self._import_stmts: List[ImportSTMT] = []

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
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: Module,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._mapping = mapping
        self._project_path = project_path
        self._base_module = base_module
        self._import_stmts = import_stmts

    def get_imports(self) -> Iterable[Module]:
        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                yield from self._get_imported_modules_from_aliases(import_stmt.names)

            elif isinstance(import_stmt, ast.ImportFrom):
                yield from self._get_imported_from_modules(import_stmt)

    def _get_imported_from_modules(self, import_from_stmt: ast.ImportFrom) -> Iterable[Module]:
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

        module = _make_module_from_name(
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
            yield module

        elif isinstance(module, (RegularPackage, NamespacePackage)):
            # TODO correct handling of NamespacePackage here?
            yield from self._get_imported_modules_from_aliases(
                import_from_stmt.names,
                from_name=module.name,
            )

    def _get_imported_modules_from_aliases(
        self, aliases: Sequence[ast.alias], from_name: str = ""
    ) -> Iterable[Module]:
        for alias in aliases:
            if self._is_builtin_or_stdlib(alias.name):
                continue

            module = _make_module_from_name(
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

            yield module

    @staticmethod
    def _is_builtin_or_stdlib(module_name: str) -> bool:
        if module_name in sys.builtin_module_names or module_name in sys.modules:
            # Avail in 3.10: or name in sys.stdlib_module_names
            return True

        try:
            return importlib.util.find_spec(module_name) is not None  # type: ignore[attr-defined]
        except ModuleNotFoundError:
            return False


class ImportsOfModule(NamedTuple):
    module: Module
    imports: Sequence[Module]


def _visit_python_file(
    mapping: Mapping[str, str],
    project_path: Path,
    path: Path,
) -> Optional[ImportsOfModule]:
    module = _make_module_from_path(mapping, project_path, path)

    if isinstance(module, NamespacePackage):
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

    visitor = NodeVisitorImports()
    visitor.visit(tree)

    parser = ImportStmtsParser(
        mapping,
        project_path,
        module,
        visitor.import_stmts,
    )

    if imports := list(parser.get_imports()):
        return ImportsOfModule(module, imports)

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
    strategy: Literal["dfs", "tarjan"],
    graph: Mapping[Module, Sequence[Module]],
) -> Iterable[Tuple[Module, ...]]:
    if strategy == "dfs":
        return depth_first_search(graph)
    if strategy == "tarjan":
        return (scc for scc in tarjan_scc(graph) if len(scc) > 1)
    raise NotImplementedError()


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
    outputs_filepaths: OutputsFilepaths,
) -> Digraph:
    d = Digraph("unix", filename=outputs_filepaths.graph)

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


T = TypeVar("T")
TC = TypeVar("TC", bound=Comparable)


def pairwise(iterable: Iterable[T]) -> Iterable[Tuple[T, T]]:
    # pairwise('ABCDEFG') --> AB BC CD DE EF FG
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def dedup_edges(cycles: Iterable[Tuple[TC, ...]]) -> Sequence[Tuple[TC, TC]]:
    edges: Set[Tuple[TC, TC]] = set()
    for cycle in cycles:
        edges |= frozenset(pairwise(cycle))
    return list(edges)


def count_degree(edges: Sequence[Tuple[T, T]]) -> Mapping[T, int]:
    degrees: DefaultDict[T, int] = defaultdict(int)
    for edge in edges:
        degrees[edge[0]] -= 1
        degrees[edge[1]] += 1
    return degrees


def badness(edges: Sequence[Tuple[T, T]]) -> Mapping[Tuple[T, T], float]:
    # Get some idea of the badness of an edge by computing
    # the average of the degrees of its vertices.
    degree = count_degree(edges)
    return {edge: 0.5 * (degree[edge[0]] + degree[edge[1]]) for edge in edges}


def normalize(value: float, lower: float, higher: float) -> float:
    if not lower <= value < higher:
        raise ValueError(f"{value} is not within bounds")
    if higher < lower:
        raise ValueError("bounds are reverted")
    if higher == lower:
        raise ValueError("must use different bounds")
    return (value - lower) / (higher - lower)


def _make_edges(
    args: argparse.Namespace,
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[Tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if args.graph == "only-cycles":
        if args.strategy == "dfs":
            return _make_dfs_import_edges(import_cycles)
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


def _make_dfs_import_edges(
    cycles: Sequence[Tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges = badness(dedup_edges(cycles))
    edges_values = edges.values()
    bound = max(abs(min(edges_values)), abs(max(edges_values)))

    out = []
    for edge, value in edges.items():
        nn = int(255 * normalize(value, -bound, bound + 1))
        assert 0 <= nn < 256
        if value < 0:
            color = "#%02x%02x%02x" % (0, 255 - nn, nn)
        else:
            color = "#%02x%02x%02x" % (nn, 0, 255 - nn)
        out.append(ImportEdge(str(value), edge[0], edge[1], color))
    return out


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
        "--strategy",
        choices=["dfs", "tarjan"],
        default="dfs",
        help="path-based strong component algorithm",
    )

    parser.add_argument(
        "--store-cycles",
        type=str,
        help="Write cycles to file instead of printing on stderr",
    )

    return parser.parse_args(argv)


class OutputsFilepaths(NamedTuple):
    log: Path
    graph: Path


def _get_outputs_filepaths(args: argparse.Namespace) -> OutputsFilepaths:
    target_dir = Path(os.path.abspath(__file__)).parent.parent.joinpath("outputs")
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = "%s-%s" % (
        "-".join(Path(args.project_path).parts[1:]),
        "-".join(sorted(args.folders)),
    )
    return OutputsFilepaths(
        log=(target_dir / filename).with_suffix(".log"),
        graph=(target_dir / filename).with_suffix(".gv"),
    )


def _setup_logging(args: argparse.Namespace, outputs_filepaths: OutputsFilepaths) -> None:
    log_filepath = outputs_filepaths.log
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

    outputs_filepaths = _get_outputs_filepaths(args)

    _setup_logging(args, outputs_filepaths)

    project_path = Path(args.project_path)
    if not project_path.exists() or not project_path.is_dir():
        sys.stderr.write("No such directory: %s\n" % project_path)
        return 1

    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    logger.info("Get Python files")
    python_files = iter_python_files(project_path, args.folders)

    logger.info("Visit Python files, get imports by module")
    imports_by_module = {
        visited.module: visited.imports
        for path in python_files
        if (visited := _visit_python_file(mapping, project_path, path)) is not None
    }

    logger.info("Detect import cycles with strategy %s", args.strategy)
    unsorted_cycles = detect_cycles(args.strategy, imports_by_module)
    return_code = bool(unsorted_cycles)

    logger.info("Sort import cycles")
    sorted_cycles = sorted(set(unsorted_cycles), key=lambda t: (len(t), t[0].name))

    logger.info("Close cycles")
    import_cycles: Sequence[Tuple[Module, ...]] = [
        ((cycle[-1],) + cycle) for cycle in sorted_cycles
    ]

    _show_or_store_cycles(args, import_cycles)

    if args.graph == "no":
        return return_code

    # pylint: disable=superfluous-parens
    if not (edges := _make_edges(args, imports_by_module, import_cycles)):
        logger.debug("No edges for graphing")
        return return_code

    logger.info("Make graph")
    graph = _make_graph(edges, outputs_filepaths)
    graph.view()

    return return_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
