#!/usr/bin/env python3

from pathlib import Path

import pytest

from py_import_cycles.files import parse_files, scan_packages
from py_import_cycles.modules import ModuleName, PyModule, PyModuleType


@pytest.fixture(name="root")
def fixture_root(tmp_path: Path) -> Path:
    p = tmp_path / "root"
    p.mkdir()
    return p


def setup_py_module(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("print('hello world')")


def test_no_files(root: Path) -> None:
    projdir = root / "projdir"
    projdir.mkdir()

    assert (
        frozenset(
            [f for f in scan_packages([projdir]) if f.type is not PyModuleType.NAMESPACE_PACKAGE]
        )
        == frozenset()
    )


def test_multiple_file_with_excludes(root: Path) -> None:
    proj = {root / "p1" / "p.py", root / "p2" / "p.py", root / "p3" / "p.py"}
    excluded = {root / "other1" / "x.py", root / "other2" / "x.py"}
    for p in proj | excluded:
        setup_py_module(p)

    assert frozenset(
        [
            f
            for f in scan_packages([p.parent for p in proj])
            if f.type is not PyModuleType.NAMESPACE_PACKAGE
        ]
    ) == {PyModule(package=p.parent, path=p) for p in proj}


def test_ignore_files_without_py_extention(root: Path) -> None:
    projdir = root / "p"
    proj = {projdir / "p1.py", projdir / "p2.py", projdir / "p3.py"}
    nopy = {projdir / "f1", projdir / "f2", projdir / "f3"}
    for p in proj | nopy:
        setup_py_module(p)

    assert frozenset(
        [f for f in scan_packages([projdir]) if f.type is not PyModuleType.NAMESPACE_PACKAGE]
    ) == {PyModule(package=p.parent, path=p) for p in proj}


def test_ignore_extra_names_in_second_arg(root: Path) -> None:
    projdir = root / "p"
    proj = {projdir / "p1.py", projdir / "p2.py", projdir / "p3.py"}
    for p in proj:
        setup_py_module(p)

    assert frozenset(
        [
            f
            for f in scan_packages([projdir, projdir / Path("extra"), projdir / Path("args")])
            if f.type is not PyModuleType.NAMESPACE_PACKAGE
        ]
    ) == {PyModule(package=p.parent, path=p) for p in proj}


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
        setup_py_module(p)

    assert frozenset(
        [
            f
            for f in scan_packages([root / Path("p1"), root / Path("p2")])
            if f.type is not PyModuleType.NAMESPACE_PACKAGE
        ]
    ) == {PyModule(package=p.parents[-7], path=p) for p in proj}


def test_ignore_pycache(root: Path) -> None:
    projdir = root / "p"
    setup_py_module(projdir / "p1.py")
    (projdir / "__pycache__").mkdir()
    (projdir / "__pycache__" / "p1.cpython-312.pyc").touch()

    assert ModuleName("p", "__pycache__") not in {m.name for m in scan_packages([projdir])}


def test_parse_files_with_absolute_root(root: Path) -> None:
    setup_py_module(root / "repo" / "pkg" / "mod.py")

    assert [m.name for m in parse_files([f"{root / 'repo'}::pkg/mod.py"], Path("/elsewhere"))] == [
        ModuleName("pkg.mod")
    ]


def test_parse_files_resolves_relative_root_against_cwd(root: Path) -> None:
    setup_py_module(root / "repo" / "pkg" / "mod.py")

    assert [m.path for m in parse_files(["repo::pkg/mod.py"], root)] == [
        root / "repo" / "pkg" / "mod.py"
    ]
