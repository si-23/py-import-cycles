#!/usr/bin/env python3

import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


@dataclass(frozen=True)
class PyFile:
    path: Path
    package: Path


def iter_python_files(project_path: Path, packages: Sequence[Path]) -> Iterator[PyFile]:
    if packages:
        folders = [project_path / p for p in packages]
    else:
        folders = [project_path]
    for folder in folders:
        for file in folder.glob("**/*.py"):
            yield PyFile(file.resolve(), folder)


class OutputsFilepaths(NamedTuple):
    log: Path
    graph: Path


def get_outputs_filepaths(project_path: Path) -> OutputsFilepaths:
    target_dir = Path.home() / Path(".local", "py_import_cycles", "outputs")
    target_dir.mkdir(parents=True, exist_ok=True)

    filename_parts = list(project_path.parts[1:]) + [str(int(time.time()))]
    filename = Path("-".join(filename_parts).replace(".", "-"))

    return OutputsFilepaths(
        log=target_dir / filename.with_suffix(".log"),
        graph=target_dir / filename.with_suffix(".gv"),
    )
