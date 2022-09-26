#!/usr/bin/env python3

import argparse
import logging
import pprint
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .cycles import detect_cycles
from .files import get_outputs_filepaths, iter_python_files
from .graphs import make_edges, make_graph
from .log import logger, setup_logging
from .modules import Module, ModuleFactory
from .visitors import visit_python_file


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
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


def main() -> int:
    args = _parse_arguments()

    project_path = Path(args.project_path)
    packages = args.packages if args.packages else []
    mapping = {} if args.map is None else dict([entry.split(":") for entry in args.map])

    if not project_path.exists() or not project_path.is_dir():
        sys.stderr.write(f"No such directory: {project_path}\n")
        return 1

    outputs_filepaths = get_outputs_filepaths(project_path, packages)

    setup_logging(args.debug, outputs_filepaths)

    logger.info("Get Python files")
    python_files = iter_python_files(project_path, packages)

    logger.info("Visit Python files, get imports by module")
    module_factory = ModuleFactory(mapping, project_path)
    imports_by_module = {
        visited.module: visited.imports
        for path in python_files
        if (visited := visit_python_file(module_factory, path)) is not None
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
    if not (edges := make_edges(args.graph, args.strategy, imports_by_module, import_cycles)):
        logger.debug("No edges for graphing")
        return return_code

    logger.info("Make graph")
    graph = make_graph(edges, outputs_filepaths)
    graph.view()

    return return_code


#   .--helper--------------------------------------------------------------.
#   |                    _          _                                      |
#   |                   | |__   ___| |_ __   ___ _ __                      |
#   |                   | '_ \ / _ \ | '_ \ / _ \ '__|                     |
#   |                   | | | |  __/ | |_) |  __/ |                        |
#   |                   |_| |_|\___|_| .__/ \___|_|                        |
#   |                                |_|                                   |
#   '----------------------------------------------------------------------'


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
