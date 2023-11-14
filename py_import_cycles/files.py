#!/usr/bin/env python3

import time
from pathlib import Path
from typing import Iterator, NamedTuple, Sequence


def iter_python_files(project_path: Path, packages: Sequence[Path]) -> Iterator[Path]:
    if packages:
        for pkg in packages:
            yield from (p.resolve() for p in (project_path / pkg).glob("**/*.py"))
        return

    for p in project_path.glob("**/*.py"):
        yield p.resolve()


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
