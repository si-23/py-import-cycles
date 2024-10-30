#!/usr/bin/env python3

import os
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .log import logger
from .modules import PyFile


def scan_project(project_path: Path, packages: Sequence[Path]) -> Iterator[PyFile]:
    for package_path in [project_path / p for p in packages] if packages else [project_path]:
        for root, _dirs, files in os.walk(package_path):
            root_path = Path(root)

            if root_path.name.startswith("."):
                break

            for file in files:
                # Regular package or Python module
                if (file_path := root_path / file).suffix == ".py":
                    try:
                        yield PyFile(package=package_path, path=file_path)
                    except ValueError as e:
                        logger.error("Cannot make py file from %s: %s", file_path, e)

            if not (root_path / "__init__.py").exists():
                # Namespace package
                try:
                    yield PyFile(package=package_path, path=root_path)
                except ValueError as e:
                    logger.error("Cannot make py file from %s: %s", root_path, e)


@dataclass(frozen=True, kw_only=True)
class OutputsFilePaths:
    log: Path
    graph: Path


def get_outputs_file_paths(outputs_folder: Path | None, outputs_filename: str) -> OutputsFilePaths:
    if not outputs_folder:
        outputs_folder = Path.home() / Path(".local", "py-import-cycles", "outputs")
    outputs_folder.mkdir(parents=True, exist_ok=True)
    if not outputs_filename:
        outputs_filename = str(int(time.time()))
    return OutputsFilePaths(
        log=(outputs_folder / outputs_filename).with_suffix(".log"),
        graph=(outputs_folder / outputs_filename).with_suffix(".gv"),
    )
