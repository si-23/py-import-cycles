#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import itertools
import logging
import pprint
import random
import sys
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import (
    DefaultDict,
    Final,
    Iterable,
    Literal,
    Mapping,
    NamedTuple,
    Sequence,
    TypeVar,
    Union,
)

from graphviz import Digraph

from py_import_cycles.dfs import depth_first_search
from py_import_cycles.tarjan import strongly_connected_components as tarjan_scc
from py_import_cycles.type_defs import Comparable

logger = logging.getLogger(__name__)

# TODO #1
# Is args.map really needed?

# TODO #2
# what to do with RegularPackages in _visit_python_file?

# TODO #3
# improve logging:
#   verbose: log every step
#   debug: only log steps which are useful for dev

# TODO #4
# Check shebang

# TODO #5
# __all__ var

# TODO #6
# other imports like via importlib, imp


#   .--modules-------------------------------------------------------------.
#   |                                   _       _                          |
#   |               _ __ ___   ___   __| |_   _| | ___  ___                |
#   |              | '_ ` _ \ / _ \ / _` | | | | |/ _ \/ __|               |
#   |              | | | | | | (_) | (_| | |_| | |  __/\__ \               |
#   |              |_| |_| |_|\___/ \__,_|\__,_|_|\___||___/               |
#   |                                                                      |
#   '----------------------------------------------------------------------'


class ModuleName:
    """This class is inspired by pathlib.Path"""

    def __init__(self, *parts: str | ModuleName) -> None:
        self._parts: Final[tuple[str, ...]] = tuple(
            entry
            for part in parts
            for entry in (part.parts if isinstance(part, ModuleName) else part.split("."))
        )

    def __str__(self) -> str:
        return ".".join(self._parts)

    def __hash__(self) -> int:
        return hash(self._parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts == other._parts

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts < other._parts

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, ModuleName):
            return NotImplemented
        return self._parts > other._parts

    @property
    def parts(self) -> Sequence[str]:
        return self._parts

    @property
    def parent(self) -> ModuleName:
        return ModuleName(*self._parts[:-1])

    @property
    def parents(self) -> Sequence[ModuleName]:
        return [ModuleName(*self._parts[:idx]) for idx in range(1, len(self._parts))][::-1]

    def joinname(self, *names: str | ModuleName) -> ModuleName:
        return ModuleName(*self._parts, *names)


class RegularPackage(NamedTuple):
    path: Path
    name: ModuleName


class NamespacePackage(NamedTuple):
    path: Path
    name: ModuleName


class PyModule(NamedTuple):
    path: Path
    name: ModuleName


Module = Union[RegularPackage, NamespacePackage, PyModule]


@dataclass(frozen=True)
class ModuleFactory:
    _mapping: Mapping[str, str]
    _project_path: Path

    def make_module_from_name(self, module_name: ModuleName) -> Module:
        def _get_sanitized_module_name() -> ModuleName:
            for key, value in self._mapping.items():
                if value in module_name.parts:
                    return ModuleName(key).joinname(module_name)
            return module_name

        if module_name.parts[-1] == "*":
            # Note:
            # from a.b import *
            # - If a.b is a pkg everything from a.b.__init__.py is loaded
            # - If a.b is a mod everything from a.b.py is loaded
            # -> Getting the "right" filepath is already handled below
            module_name = _get_sanitized_module_name().parent
            module_path = self._project_path.joinpath(Path(*module_name.parts))
        else:
            module_path = self._project_path.joinpath(Path(*_get_sanitized_module_name().parts))

        if module_path.is_dir():
            if (init_module_path := module_path / "__init__.py").exists():
                return RegularPackage(
                    path=init_module_path,
                    name=module_name.joinname("__init__"),
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

        raise ValueError(module_name)

    def make_module_from_path(self, module_path: Path) -> Module:
        def _get_sanitized_module_name() -> ModuleName:
            parts = module_path.relative_to(self._project_path).with_suffix("").parts
            for key, value in self._mapping.items():
                if key == parts[0] and value in parts[1:]:
                    return ModuleName(*parts[1:])
            return ModuleName(*parts)

        module_name = _get_sanitized_module_name()

        if module_path.is_dir():
            return NamespacePackage(
                path=module_path,
                name=module_name,
            )

        if module_path.is_file() and module_path.suffix == ".py":
            if module_path.stem == "__init__":
                return RegularPackage(
                    path=module_path,
                    name=module_name,
                )

            return PyModule(
                path=module_path,
                name=module_name,
            )

        raise ValueError(module_path)


# .
#   .--files---------------------------------------------------------------.
#   |                           __ _ _                                     |
#   |                          / _(_) | ___  ___                           |
#   |                         | |_| | |/ _ \/ __|                          |
#   |                         |  _| | |  __/\__ \                          |
#   |                         |_| |_|_|\___||___/                          |
#   |                                                                      |
#   '----------------------------------------------------------------------'


def iter_python_files(project_path: Path, packages: Sequence[str]) -> Iterable[Path]:
    if packages:
        for pkg in packages:
            yield from (p.resolve() for p in (project_path / pkg).glob("**/*.py"))
        return

    for p in project_path.glob("**/*.py"):
        yield p.resolve()


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
        self._import_stmts: list[ImportSTMT] = []

    @property
    def import_stmts(self) -> Sequence[ImportSTMT]:
        return self._import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._import_stmts.append(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._import_stmts.append(node)


STDLIB_OR_BUILTIN = sys.stdlib_module_names.union(sys.builtin_module_names)


class ImportStmtsParser:
    def __init__(
        self,
        module_factory: ModuleFactory,
        base_module: Module,
        import_stmts: Sequence[ImportSTMT],
    ) -> None:
        self._module_factory = module_factory
        self._base_module = base_module
        self._import_stmts = import_stmts

    def get_imports(self) -> Iterable[Module]:
        for module_name in self._get_module_names():
            if not module_name.parts or module_name.parts[0] in STDLIB_OR_BUILTIN:
                continue

            try:
                module = self._module_factory.make_module_from_name(module_name)
                self._validate_module(module)
            except ValueError:
                continue

            yield module

    def _get_module_names(self) -> Iterable[ModuleName]:
        for import_stmt in self._import_stmts:
            if isinstance(import_stmt, ast.Import):
                yield from self._get_module_names_of_import_stmt(import_stmt)

            elif isinstance(import_stmt, ast.ImportFrom):
                yield from self._get_module_names_of_import_from_stmt(import_stmt)

    # -----ast.Import-----

    def _get_module_names_of_import_stmt(self, import_stmt: ast.Import) -> Iterable[ModuleName]:
        for alias in import_stmt.names:
            yield ModuleName(alias.name)

    # -----ast.ImportFrom-----

    def _get_module_names_of_import_from_stmt(
        self, import_from_stmt: ast.ImportFrom
    ) -> Iterable[ModuleName]:
        try:
            yield (anchor := self._get_anchor(import_from_stmt))
        except ValueError:
            return

        for alias in import_from_stmt.names:
            # Add packages/modules to above prefix:
            # 1 -> ../a/b/c{.py,/}
            # 2 -> ../BASE/c{.py,/}
            # 3 -> ../BASE/a/b/c{.py,/}
            # 4 -> ../BASE_PARENT/a/b/c{.py,/}
            yield anchor.joinname(alias.name)

    def _get_anchor(self, import_from_stmt: ast.ImportFrom) -> ModuleName:
        # Handle the cases:
        # 1 from a.b import c (module == "a.b", level == 0)
        #   -> Python module/package: ../a/b{.py,/}
        # 2 from . import c (module == None, level == 1)
        #   -> Python module/package: ../BASE{.py,/}
        # 3 from .a.b import c (module == "a.b", level == 1)
        #   -> Python module/package: ../BASE/a/b{.py,/}
        # 4 from ..a.b import c (module == "a.b", level == 2)
        #   -> Python module/package: ../BASE_PARENT/a/b{.py,/}
        if import_from_stmt.level == 0:
            if import_from_stmt.module:
                return ModuleName(import_from_stmt.module)
            raise ValueError(import_from_stmt.module)

        try:
            parent = self._base_module.name.parents[import_from_stmt.level - 1]
        except IndexError:
            parent = ModuleName()

        return parent.joinname(import_from_stmt.module) if import_from_stmt.module else parent

    # -----helper-----

    def _validate_module(self, module: Module) -> None:
        if module == self._base_module or (
            isinstance(module, RegularPackage)
            and module.name.parent == self._base_module.name.parent
        ):
            # Last if-part: do not add reg pkg, ie. __init__.py, of base module
            raise ValueError(module)


class ImportsOfModule(NamedTuple):
    module: Module
    imports: Sequence[Module]


def _visit_python_file(module_factory: ModuleFactory, path: Path) -> None | ImportsOfModule:
    try:
        module = module_factory.make_module_from_path(path)
    except ValueError:
        return None

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
        module_factory,
        module,
        visitor.import_stmts,
    )

    return ImportsOfModule(
        module,
        list(OrderedDict.fromkeys(parser.get_imports())),
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


def detect_cycles(
    strategy: Literal["dfs", "tarjan"],
    graph: Mapping[Module, Sequence[Module]],
) -> Iterable[tuple[Module, ...]]:
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
                str(edge.from_module.name),
                shape=_get_shape(edge.from_module),
            )

            ds.node(
                str(edge.to_module.name),
                shape=_get_shape(edge.to_module),
            )

            ds.attr("edge", color=edge.edge_color)

            if edge.title:
                ds.edge(str(edge.from_module.name), str(edge.to_module.name), edge.title)
            else:
                ds.edge(str(edge.from_module.name), str(edge.to_module.name))

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


def pairwise(iterable: Iterable[T]) -> Iterable[tuple[T, T]]:
    # pairwise('ABCDEFG') --> AB BC CD DE EF FG
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def dedup_edges(cycles: Iterable[tuple[TC, ...]]) -> Sequence[tuple[TC, TC]]:
    edges: set[tuple[TC, TC]] = set()
    for cycle in cycles:
        edges |= frozenset(pairwise(cycle))
    return list(edges)


def count_degree(edges: Sequence[tuple[T, T]]) -> Mapping[T, int]:
    degrees: DefaultDict[T, int] = defaultdict(int)
    for edge in edges:
        degrees[edge[0]] -= 1
        degrees[edge[1]] += 1
    return degrees


def badness(edges: Sequence[tuple[T, T]]) -> Mapping[tuple[T, T], float]:
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
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if args.graph == "only-cycles":
        if args.strategy == "dfs":
            return _make_dfs_import_edges(import_cycles)
        return _make_only_cycles_edges(import_cycles)

    raise NotImplementedError(f"Unknown graph option: {args.graph}")


def _make_all_edges(
    imports_by_module: Mapping[Module, Sequence[Module]],
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
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
    import_cycles: Sequence[tuple[Module, ...]],
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
    cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges = badness(dedup_edges(cycles))
    edges_values = edges.values()
    bound = max(abs(min(edges_values)), abs(max(edges_values)))

    out = []
    for edge, value in edges.items():
        nn = int(255 * normalize(value, -bound, bound + 1))
        assert 0 <= nn < 256
        if value < 0:
            color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
                0, 255 - nn, nn
            )
        else:
            color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
                nn, 0, 255 - nn
            )
        out.append(ImportEdge(str(value), edge[0], edge[1], color))
    return out


def _make_only_cycles_edges(
    import_cycles: Sequence[tuple[Module, ...]],
) -> Sequence[ImportEdge]:
    edges: set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles, start=1):
        color = "#{:02x}{:02x}{:02x}".format(  # pylint: disable=consider-using-f-string
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )

        start_module = import_cycle[0]
        for next_module in import_cycle[1:]:
            edges.add(
                ImportEdge(
                    f"{str(nr)} ({len(import_cycle) - 1})",
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


def _parse_arguments() -> argparse.Namespace:
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
        help=(
            "path to project. If no packages are given collect all Python"
            " files from this directory."
        ),
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        help="collect Python files from top-level packages",
    )
    parser.add_argument(
        "--strategy",
        choices=["dfs", "tarjan"],
        default="dfs",
        help="path-based strong component algorithm",
    )

    return parser.parse_args()


class OutputsFilepaths(NamedTuple):
    log: Path
    graph: Path


def _get_outputs_filepaths(project_path: Path, packages: Sequence[str]) -> OutputsFilepaths:
    target_dir = Path.home() / Path(".local", "py_import_cycles", "outputs")
    target_dir.mkdir(parents=True, exist_ok=True)

    filename_parts = list(Path(project_path).parts[1:])
    if packages:
        filename_parts.extend(sorted(packages))

    filename = "-".join(filename_parts)

    return OutputsFilepaths(
        log=(target_dir / filename).with_suffix(".log"),
        graph=(target_dir / filename).with_suffix(".gv"),
    )


def _setup_logging(args: argparse.Namespace, outputs_filepaths: OutputsFilepaths) -> None:
    log_filepath = outputs_filepaths.log

    log_filepath.unlink(missing_ok=True)

    if args.debug:
        sys.stderr.write(f"Write log to {log_filepath}\n")
        log_level = logging.DEBUG
    else:
        log_level = logging.NOTSET

    logger.setLevel(log_level)

    handler = logging.FileHandler(filename=log_filepath)
    handler.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _log_or_show_cycles(import_cycles: Sequence[tuple[Module, ...]], verbose: bool) -> None:
    sys.stderr.write(f"Found {len(import_cycles)} import cycles\n")

    if logger.level == logging.DEBUG:
        # Avoid execution of pprint.pformat call if not debug
        logger.debug(
            "Import cycles: %s",
            pprint.pformat(
                {
                    nr: [str(p.name) for p in import_cycle]
                    for nr, import_cycle in enumerate(import_cycles, start=1)
                }
            ),
        )

    if verbose:
        for nr, import_cycle in enumerate(import_cycles, start=1):
            sys.stderr.write(f"  {nr}: {[str(ic.name) for ic in import_cycle]}\n")


# .


def main() -> int:
    args = _parse_arguments()

    project_path = Path(args.project_path)
    packages = args.packages if args.packages else []
    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    if not project_path.exists() or not project_path.is_dir():
        sys.stderr.write(f"No such directory: {project_path}\n")
        return 1

    outputs_filepaths = _get_outputs_filepaths(project_path, packages)

    _setup_logging(args, outputs_filepaths)

    logger.info("Get Python files")
    python_files = iter_python_files(project_path, packages)

    logger.info("Visit Python files, get imports by module")
    module_factory = ModuleFactory(mapping, project_path)
    imports_by_module = {
        visited.module: visited.imports
        for path in python_files
        if (visited := _visit_python_file(module_factory, path)) is not None
    }

    if logger.level == logging.DEBUG:
        # Avoid execution of pprint.pformat call if not debug
        logger.debug(
            "Imports by module: %s",
            pprint.pformat(
                {str(ibm.name): [str(m.name) for m in ms] for ibm, ms in imports_by_module.items()}
            ),
        )

    logger.info("Detect import cycles with strategy %s", args.strategy)
    unsorted_cycles = detect_cycles(args.strategy, imports_by_module)
    return_code = bool(unsorted_cycles)

    logger.info("Sort import cycles")
    sorted_cycles = sorted(set(unsorted_cycles), key=lambda t: (len(t), t[0].name))

    logger.info("Close cycles")
    import_cycles: Sequence[tuple[Module, ...]] = [
        ((cycle[-1],) + cycle) for cycle in sorted_cycles
    ]

    _log_or_show_cycles(import_cycles, args.verbose)

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
    sys.exit(main())
