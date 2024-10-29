#!/usr/bin/env python3

import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


@dataclass(frozen=True, kw_only=True)
class PyFile:
    package: Path
    path: Path


def iter_python_files(project_path: Path, packages: Sequence[Path]) -> Iterator[PyFile]:
    if packages:
        for pkg in packages:
            yield from (
                PyFile(package=project_path / pkg, path=p.resolve())
                for p in (project_path / pkg).glob("**/*.py")
            )

        return

    for p in project_path.glob("**/*.py"):
        yield PyFile(package=project_path, path=p.resolve())


class OutputsFilePaths(NamedTuple):
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
