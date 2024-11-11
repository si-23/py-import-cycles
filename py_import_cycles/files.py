#!/usr/bin/env python3

import os
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .modules import PyModule


def scan_packages(packages: Sequence[Path]) -> Iterator[PyModule]:
    paths_to_ignore: set[Path] = set()
    for package_path in packages:
        for root, _dirs, files in os.walk(package_path):
            root_path = Path(root)

            if root_path.name.startswith(".") or root_path.name == "__pycache_":
                paths_to_ignore.add(root_path)
                continue

            if any(root_path.is_relative_to(p) for p in paths_to_ignore):
                continue

            for file in files:
                # May be a regular package or a module
                file_path = root_path / file
                try:
                    yield PyModule(package=package_path, path=file_path)
                except ValueError:
                    pass

            # May be a namespace package
            try:
                yield PyModule(package=package_path, path=root_path)
            except ValueError:
                pass


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
