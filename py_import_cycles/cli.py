#!/usr/bin/env python3

import argparse
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Callable

from . import __version__
from .cycles import detect_cycles
from .files import get_outputs_file_paths, scan_packages
from .graphs import make_graph
from .log import logger, setup_logging
from .modules import PyModule, PyModuleType
from .visitors import visit_py_module


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
        "--outputs-folder",
        help="path to outputs folder. If not set $HOME/.local/py-import-cycles/outputs/ is used",
    )
    parser.add_argument(
        "--outputs-filename",
        help="outputs filename. If not set the current timestamp is used",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="create graphical representation",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        help="collect Python files from top-level packages",
        default=[],
    )
    parser.add_argument(
        "--strategy",
        choices=["dfs", "tarjan", "johnson"],
        default="dfs",
        help="path-based strong component algorithm",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="Tolerate a certain number of cycles, ie. an upper threshold.",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_arguments()

    packages = [pp for p in args.packages if (pp := Path(p)).is_dir()]

    outputs_filepaths = get_outputs_file_paths(
        Path(args.outputs_folder) if args.outputs_folder else None,
        args.outputs_filename or "",
    )

    setup_logging(outputs_filepaths.log, args.debug)

    logger.info("Get Python files")
    py_modules = list(scan_packages(packages))

    logger.info("Visit Python files, get imports of py files")
    py_modules_by_name = {p.name: p for p in py_modules}

    imports_by_py_module = {
        py_module: imports
        for py_module in py_modules
        if py_module.type is not PyModuleType.NAMESPACE_PACKAGE
        and (imports := visit_py_module(py_modules_by_name, py_module))
    }

    if _debug():
        logger.debug(
            "Imports of py files:\n%s",
            "\n".join(_make_readable_imports_by_py_module(imports_by_py_module)),
        )

    logger.info("Detect import cycles with strategy %s", args.strategy)
    unsorted_cycles = set(detect_cycles(args.strategy, imports_by_py_module))

    logger.info("Sort import cycles")
    sorted_cycles = sorted(unsorted_cycles, key=lambda t: (len(t), t[0].name))

    sys.stderr.write(f"Found {len(sorted_cycles)} import cycles\n")
    _log_or_show_cycles(args.verbose, sorted_cycles)

    if args.graph:
        logger.info("Close cycle and make graph")
        make_graph(
            outputs_filepaths.graph,
            args.strategy,
            [((cycle[-1],) + cycle) for cycle in sorted_cycles],
        )

    return len(unsorted_cycles) > args.threshold


#   .--helper--------------------------------------------------------------.
#   |                    _          _                                      |
#   |                   | |__   ___| |_ __   ___ _ __                      |
#   |                   | '_ \ / _ \ | '_ \ / _ \ '__|                     |
#   |                   | | | |  __/ | |_) |  __/ |                        |
#   |                   |_| |_|\___|_| .__/ \___|_|                        |
#   |                                |_|                                   |
#   '----------------------------------------------------------------------'


def _make_readable_imports_by_py_module(
    imports_by_py_module: Mapping[PyModule, Sequence[PyModule]],
) -> Sequence[str]:
    lines = []
    for ibm, ms in imports_by_py_module.items():
        if ms:
            lines.append(f"  {str(ibm)} imports: {', '.join(str(m) for m in ms)}")
    return lines


def _make_readable_cycles(
    line_handler: Callable[[int, tuple[PyModule, ...]], Sequence[str]],
    sorted_cycles: Sequence[tuple[PyModule, ...]],
) -> Sequence[str]:
    return [
        line for nr, ic in enumerate(sorted_cycles, start=1) for line in line_handler(nr, ic) if ic
    ]


def _log_or_show_cycles(
    verbose: bool,
    sorted_cycles: Sequence[tuple[PyModule, ...]],
) -> None:
    if verbose:
        for line in _make_readable_cycles(
            lambda nr, ic: [f"  Cycle {nr}:"] + [f"   {str(m)}" for m in ic],
            sorted_cycles,
        ):
            sys.stderr.write(f"{line}\n")

    if _debug():
        logger.debug(
            "Import cycles:\n%s",
            "\n".join(
                _make_readable_cycles(
                    lambda nr, ic: [f"  Cycle {nr}: {' > '.join(str(m) for m in ic)}"],
                    sorted_cycles,
                )
            ),
        )


def _debug() -> bool:
    return logger.level == logging.DEBUG
