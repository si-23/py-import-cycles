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


#   .--type defs-----------------------------------------------------------.
#   |              _                          _       __                   |
#   |             | |_ _   _ _ __   ___    __| | ___ / _|___               |
#   |             | __| | | | '_ \ / _ \  / _` |/ _ \ |_/ __|              |
#   |             | |_| |_| | |_) |  __/ | (_| |  __/  _\__ \              |
#   |              \__|\__, | .__/ \___|  \__,_|\___|_| |___/              |
#   |                  |___/|_|                                            |
#   '----------------------------------------------------------------------'


ImportContext = Tuple[Union[ast.If, ast.Try, ast.ClassDef, ast.FunctionDef], ...]


class Module:
    @classmethod
    def from_name(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_name: str,
    ) -> Optional[Union[Package, PyModule]]:
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

        logger.debug("Module.from_name: Unhandled %s", module_name)
        return None

    @classmethod
    def from_path(
        cls,
        mapping: Mapping[str, str],
        project_path: Path,
        module_path: Path,
    ) -> Optional[Union[Package, PyModule]]:
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

        logger.debug("Module.from_path: Unhandled %s", module_path)
        return None


class Package(NamedTuple):
    path: Path
    name: str


class PyModule(NamedTuple):
    path: Path
    name: str


ImportsByModule = Mapping[PyModule, Sequence[PyModule]]


# .
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


class NodeVisitorImports(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._import_stmts: List[Union[ImportSTMT, ImportFromSTMT]] = []

    @property
    def import_stmts(self) -> Sequence[Union[ImportSTMT, ImportFromSTMT]]:
        return self._import_stmts

    def visit_Import(self, node: ast.Import) -> None:
        self._import_stmts.append(ImportSTMT(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._import_stmts.append(ImportFromSTMT(node))


def _visit_python_files(files: Iterable[Path]) -> Iterable[NodeVisitorImports]:
    for path in files:
        if (visitor := _visit_python_file(path)) is not None:
            yield visitor


def _visit_python_file(path: Path) -> Optional[NodeVisitorImports]:
    if path.name in ["__pycache__", "__init__.py"]:
        return None

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        logger.debug("Cannot read python file %s: %s", path, e)
        return None

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Cannot visit python file %s: %s", path, e)
        return None

    visitor = NodeVisitorImports(path)
    visitor.visit(tree)
    return visitor


class ImportSTMT(NamedTuple):
    node: ast.Import

    def get_imported_modules(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: PyModule,
    ) -> Iterable[Union[PyModule, Package]]:
        yield from _get_imported_modules_from_aliases(
            "import",
            mapping,
            project_path,
            base_module,
            self.node.names,
        )


class ImportFromSTMT(NamedTuple):
    node: ast.ImportFrom

    def get_imported_modules(
        self,
        mapping: Mapping[str, str],
        project_path: Path,
        base_module: PyModule,
    ) -> Iterable[Union[PyModule, Package]]:
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
        )

        if module is None:
            logger.debug("Unhandled import from in %s:", base_module.name)
            logger.debug("  Dump: %s", ast.dump(self.node))
            return

        if isinstance(module, PyModule):
            yield module
            return

        if isinstance(module, Package):
            yield from _get_imported_modules_from_aliases(
                "import from",
                mapping,
                project_path,
                base_module,
                self.node.names,
                from_name=module.name,
            )
            return


def _get_imported_modules_from_aliases(
    title: str,
    mapping: Mapping[str, str],
    project_path: Path,
    base_module: PyModule,
    aliases: Sequence[ast.alias],
    from_name: str = "",
) -> Iterable[Union[PyModule, Package]]:
    for alias in aliases:
        if _is_builtin_or_stdlib(alias.name):
            continue

        module = Module.from_name(
            mapping,
            project_path,
            ".".join([from_name, alias.name]) if from_name else alias.name,
        )

        if module is None:
            logger.debug("Unhandled %s in %s:", title, base_module.name)
            logger.debug("  Dump: %s", ast.dump(alias))
            continue

        if isinstance(module, PyModule):
            yield module
            continue

        if isinstance(module, Package):
            yield module
            continue


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
ImportCycles = Sequence[ImportCycle]


def _find_import_cycles(imports_by_module: ImportsByModule) -> ImportCycles:
    detector = DetectImportCycles(imports_by_module)
    detector.detect_cycles()
    return sorted(detector.cycles)


@dataclass(frozen=True)
class DetectImportCycles:
    _imports_by_module: ImportsByModule
    _cycles: Dict[ImportCycle, ImportCycle] = field(default_factory=dict)

    @property
    def cycles(self) -> ImportCycles:
        return sorted(self._cycles.values())

    def detect_cycles(self) -> None:
        for nr, (module, imported_modules) in enumerate(
            sorted(
                self._get_entry_points(self._imports_by_module).items(),
                key=lambda t: t[0].name,
            )
        ):
            logger.debug("Check %s (Nr %s)", module.name, nr + 1)
            self._detect_cycles([module.name], imported_modules)

    def _get_entry_points(self, imports_by_module: ImportsByModule) -> ImportsByModule:
        known_imported_modules = set(
            imported_module.name
            for imported_modules in imports_by_module.values()
            for imported_module in imported_modules
        )
        entry_points = {
            module: imported_modules
            for module, imported_modules in imports_by_module.items()
            if module.name not in known_imported_modules
        }

        logger.info(
            "Found %d modules, %d imported modules and %d entry points",
            len(imports_by_module),
            len(known_imported_modules),
            len(entry_points),
        )

        if entry_points:
            return entry_points
        return imports_by_module

    def _detect_cycles(
        self,
        base_chain: List[str],
        imported_modules: Sequence[PyModule],
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

    def _add_cycle(self, chain: Sequence[str]) -> None:
        first_idx = chain.index(chain[-1])
        cycle = tuple(chain[first_idx:])
        if (short := tuple(sorted(cycle[:-1]))) not in self._cycles:
            self._cycles[short] = cycle
            logger.debug("  Found cycle in %s", chain)
            logger.debug("  Cycle: %s", cycle)


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


def _make_edges(
    args: argparse.Namespace,
    imports_by_module: ImportsByModule,
    import_cycles: ImportCycles,
) -> Sequence[ImportEdge]:
    if args.graph == "all":
        return _make_all_edges(imports_by_module, import_cycles)

    if args.graph == "only-cycles":
        return _make_only_cycles_edges(imports_by_module, import_cycles)

    raise NotImplementedError("Unknown graph option: %s" % args.graph)


def _make_all_edges(
    imports_by_module: ImportsByModule,
    import_cycles: ImportCycles,
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
                )
            )
    return sorted(edges)


def _is_in_cycle(
    module: PyModule, the_import: str, import_cycles: ImportCycles
) -> Optional[ImportCycle]:
    for import_cycle in import_cycles:
        try:
            idx = import_cycle.index(module.name)
        except ValueError:
            continue

        if import_cycle[idx + 1] == the_import:
            return import_cycle
    return None


def _make_only_cycles_edges(
    imports_by_module: ImportsByModule,
    import_cycles: ImportCycles,
) -> Sequence[ImportEdge]:
    edges: Set[ImportEdge] = set()
    for nr, import_cycle in enumerate(import_cycles):
        color = "#%02x%02x%02x" % (
            random.randint(50, 200),
            random.randint(50, 200),
            random.randint(50, 200),
        )
        module = import_cycle[0]
        for module_name in import_cycle[1:]:
            edges.add(
                ImportEdge(
                    str(nr + 1),
                    module,
                    module_name,
                    color,
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
    imports_by_module: Dict[PyModule, List[PyModule]] = {}

    for visitor in visitors:
        module = Module.from_path(
            mapping,
            project_path,
            visitor.path,
        )

        if not isinstance(module, PyModule):
            continue

        if module in imports_by_module:
            continue

        imported_modules: List[PyModule] = []
        for import_stmt in visitor.import_stmts:
            for imported_module in import_stmt.get_imported_modules(
                mapping, project_path, module
            ):
                if isinstance(imported_module, PyModule):
                    imported_modules.append(imported_module)
                    continue

                if isinstance(imported_module, Package):
                    # TODO what to do with packages?
                    logger.debug("Found %s", imported_module)
                    continue

        if imported_modules:
            imports_by_module[module] = imported_modules

    return imports_by_module


def _get_return_code(import_cycles: ImportCycles) -> bool:
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

    logger.info("Detect import cycles")
    import_cycles = _find_import_cycles(imports_by_module)

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
