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


class OutputsFilepaths(NamedTuple):
    log: Path
    graph: Path


def get_outputs_filepaths(outputs_folder: Path | None) -> OutputsFilepaths:
    if not outputs_folder:
        outputs_folder = Path.home() / Path(".local", "py-import-cycles", "outputs")
    outputs_folder.mkdir(parents=True, exist_ok=True)
    file_name = str(int(time.time()))
    return OutputsFilepaths(
        log=(outputs_folder / file_name).with_suffix(".log"),
        graph=(outputs_folder / file_name).with_suffix(".gv"),
    )
