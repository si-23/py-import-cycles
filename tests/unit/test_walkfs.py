#!/usr/bin/env python3

from pathlib import Path

import pytest

from py_import_cycles.files import iter_python_files  # pylint: disable=import-error


@pytest.fixture(name="root")
def fixture_root(tmp_path: Path) -> Path:
    p = tmp_path / "root"
    p.mkdir()
    return p


def setup_py_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("print('hello world')")


def test_no_files(root: Path) -> None:
    projdir = root / "projdir"
    projdir.mkdir()

    assert frozenset(iter_python_files(root, [projdir])) == frozenset()


def test_single_file(root: Path) -> None:
    # The code requires at least an extra directory under the project
    # root.  This is probably a bug.
    proj = root / "projdir" / "proj.py"
    setup_py_file(proj)

    assert frozenset(iter_python_files(root, [proj.parent])) == {proj}


def test_multiple_files(root: Path) -> None:
    proj = {
        root / "p1" / "p11.py",
        root / "p1" / "p12.py",
        root / "p2" / "p.py",
        root / "p3" / "p.py",
    }
    for p in proj:
        setup_py_file(p)

    assert frozenset(iter_python_files(root, [p.parent for p in proj])) == proj


def test_multiple_file_with_excludes(root: Path) -> None:
    proj = {root / "p1" / "p.py", root / "p2" / "p.py", root / "p3" / "p.py"}
    excluded = {root / "other1" / "x.py", root / "other2" / "x.py"}
    for p in proj | excluded:
        setup_py_file(p)

    assert frozenset(iter_python_files(root, [p.parent for p in proj])) == proj


def test_ignore_files_without_py_extention(root: Path) -> None:
    # Identifying the file by its extension only may be too naive.
    projdir = root / "p"
    proj = {projdir / "p1.py", projdir / "p2.py", projdir / "p3.py"}
    nopy = {projdir / "f1", projdir / "f2", projdir / "f3"}
    for p in proj | nopy:
        setup_py_file(p)

    assert frozenset(iter_python_files(root, [projdir])) == proj


def test_ignore_extra_names_in_second_arg(root: Path) -> None:
    projdir = root / "p"
    proj = {projdir / "p1.py", projdir / "p2.py", projdir / "p3.py"}
    for p in proj:
        setup_py_file(p)

    assert frozenset(iter_python_files(root, [projdir, Path("extra"), Path("args")])) == proj


def test_recurse_dirs(root: Path) -> None:
    proj = {
        root / "p1" / "p.py",
        root / "p1" / "p11" / "p111.py",
        root / "p2" / "p.py",
        root / "p2" / "p21" / "p211.py",
        root / "p2" / "p21" / "p212.py",
        root / "p2" / "p22" / "p221.py",
        root / "p2" / "p22" / "p222.py",
    }
    for p in proj:
        setup_py_file(p)

    assert frozenset(iter_python_files(root, [Path("p1"), Path("p2")])) == proj
