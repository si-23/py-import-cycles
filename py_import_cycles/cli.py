#!/usr/bin/env python3

import argparse
import json
import logging
import sys
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Literal

from . import __version__
from .cycles import detect_cycles
from .files import get_outputs_file_paths, parse_files, scan_packages
from .graphs import make_graph
from .log import logger, setup_logging
from .modules import PyModule
from .sarif import make_sarif
from .visitors import visit_py_module


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""description:
  Detect import cycles in Python projects.

  It indicates whether Python packages have structural weak points. Python's module finders
  and loaders are not taken into account.

  Single import statements can be ignored via '# py-import-cycles: ignore':

    import a  # py-import-cycles: ignore

    # py-import-cycles: ignore
    import b
""",
        formatter_class=argparse.RawTextHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="log additional information for debugging",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print the found cycles",
    )
    parser.add_argument(
        "--outputs-folder",
        metavar="DIR",
        help="folder for the log and graph files (default: ~/.local/py-import-cycles/outputs/)",
    )
    parser.add_argument(
        "--outputs-filename",
        metavar="NAME",
        help="base name of the log and graph files (default: the current Unix timestamp)",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        metavar="PATH",
        help="top-level package folders to collect Python modules from",
        default=[],
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="REPO::FILE",
        help="""Python files to analyse, given as REPO::pkg/module.py, e.g.
  - /path/to/repo::pkg/module.py
  - relpath/to/repo::pkg/module.py
a relative REPO is resolved against the current working directory""",
        default=[],
    )
    parser.add_argument(
        "--strategy",
        choices=["dfs", "tarjan", "johnson"],
        default="dfs",
        help="""cycle detection algorithm (default: %(default)s):
- dfs: one cycle per start module, found by depth-first search (fast)
- tarjan: the strongly connected components with more than one module
- johnson: all simple cycles (may take very long, see --length-bound)""",
    )
    parser.add_argument(
        "--length-bound",
        type=int,
        metavar="N",
        help="maximum length of the cycles found by the johnson strategy (default: unbounded)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=0,
        metavar="N",
        help="exit with status 1 only if more than N cycles are found (default: %(default)s)",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="write the cycles as Graphviz file to the outputs folder and open it",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="log the duration and the number of modules and imports",
    )
    parser.add_argument(
        "--sarif",
        metavar="FILE",
        help="write the cycles as SARIF to FILE, or to stdout if FILE is '-'",
    )

    return parser.parse_args()


def _make_readable_imports_by_py_module(
    imports_by_py_module: Mapping[PyModule, Sequence[PyModule]],
) -> Iterator[str]:
    for ibm, ms in imports_by_py_module.items():
        if ms:
            yield f"  {str(ibm)} imports:"
            yield from (f"    {str(m)}" for m in ms)


def _make_readable_cycles(
    sorted_cycles: Sequence[tuple[PyModule, ...]],
) -> Iterator[str]:
    for nr, ic in enumerate(sorted_cycles, start=1):
        if ic:
            yield f"  Cycle {nr}:"
            yield f"    {str(ic[0])}"
            yield from (f"    > {str(i)} " for i in ic[1:])


def _log_or_show_cycles(
    verbose: bool,
    sorted_cycles: Sequence[tuple[PyModule, ...]],
) -> None:
    if verbose:
        for line in _make_readable_cycles(sorted_cycles):
            sys.stderr.write(f"{line}\n")

    if _debug():
        logger.debug(
            "Import cycles:\n%s",
            "\n".join(_make_readable_cycles(sorted_cycles)),
        )


def _show_stats(
    duration: float,
    stats: Counter[Literal["num_of_modules", "num_of_modules_with_imports", "num_of_imports"]],
) -> None:
    logger.info("Duration: %ss", f"{duration:.2f}")
    logger.info("Number of found modules: %s", stats["num_of_modules"])
    logger.info("Number of imports: %s", stats["num_of_imports"])
    logger.info("Number of modules with imports: %s", stats["num_of_modules_with_imports"])


def _write_sarif(
    path: str,
    sorted_cycles: Sequence[tuple[PyModule, ...]],
) -> None:
    sarif = json.dumps(make_sarif(sorted_cycles, __version__), indent=2) + "\n"
    if path == "-":
        sys.stdout.write(sarif)
    else:
        Path(path).write_text(sarif, encoding="utf-8")


def _debug() -> bool:
    return logger.level == logging.DEBUG


def main() -> int:
    now = time.time()
    stats: Counter[Literal["num_of_modules", "num_of_modules_with_imports", "num_of_imports"]] = (
        Counter()
    )

    args = _parse_arguments()

    packages = [pp for p in args.packages if (pp := Path(p)).is_dir()]

    outputs_filepaths = get_outputs_file_paths(
        Path(args.outputs_folder) if args.outputs_folder else None,
        args.outputs_filename or "",
    )

    setup_logging(outputs_filepaths.log, logging.DEBUG if args.debug else logging.INFO)
    if args.debug:
        sys.stderr.write(f"Write log to {outputs_filepaths.log}\n")

    logger.info("Scan packages")
    py_modules = list(scan_packages(packages))
    if args.files:
        logger.info("Parse files")
        py_modules.extend(parse_files(args.files))

    if args.stats:
        stats["num_of_modules"] = len(py_modules)

    logger.info("Visit and compute imports of py modules")
    py_modules_by_name = {p.name: p for p in py_modules}

    imports_by_py_module = {
        py_module: imports
        for py_module in py_modules
        if (
            imports := sorted(
                frozenset(visit_py_module(py_modules_by_name, py_module)),
                key=lambda m: tuple(m.name.parts),
                reverse=True,
            )
        )
    }

    if args.stats:
        stats["num_of_imports"] = sum(len(ims) for ims in imports_by_py_module.values())
        stats["num_of_modules_with_imports"] = len(imports_by_py_module)

    if _debug():
        logger.debug(
            "Imports of py modules:\n%s",
            "\n".join(_make_readable_imports_by_py_module(imports_by_py_module)),
        )

    logger.info("Detect import cycles with strategy %s", args.strategy)
    unsorted_cycles = set(detect_cycles(args.strategy, args.length_bound, imports_by_py_module))

    logger.info("Sort import cycles")
    sorted_cycles = sorted(unsorted_cycles, key=lambda t: (len(t), t[0].name))

    sys.stderr.write(f"Found {len(sorted_cycles)} import cycles\n")
    _log_or_show_cycles(args.verbose, sorted_cycles)

    if args.sarif:
        _write_sarif(args.sarif, sorted_cycles)

    if args.graph:
        logger.info("Close cycle and make graph")
        make_graph(
            outputs_filepaths.graph,
            args.strategy,
            [((cycle[-1],) + cycle) for cycle in sorted_cycles],
        )

    if args.stats:
        _show_stats(time.time() - now, stats)

    return len(unsorted_cycles) > args.threshold
