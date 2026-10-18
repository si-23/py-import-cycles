import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
E2E_DIR = REPO / "e2e_test_inputs"
PROJECTS = sorted(p for p in E2E_DIR.iterdir() if p.is_dir())


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "-m", "py_import_cycles", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def run_tool(*args: str) -> str:
    return run_cli(*args).stderr.strip()


@pytest.fixture(scope="session", autouse=True)
def clean_e2e_pycache() -> None:
    for d in E2E_DIR.rglob("__pycache__"):
        shutil.rmtree(d)


@pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p.name)
def test_main(project: Path) -> None:
    if (skip := project / "skip_main").exists():
        pytest.skip(skip.read_text().strip())
    result = subprocess.run(["uv", "run", "python", str(project / "main.py")], cwd=REPO)
    assert result.returncode == 0


@pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p.name)
def test_packages(project: Path) -> None:
    expected = int((project / "found_cycles").read_text())
    packages = [str(project / w) for w in (project / "packages").read_text().split()]
    assert (
        run_tool("--packages", *packages, "--strategy", "johnson")
        == f"Found {expected} import cycles"
    )


@pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p.name)
def test_files_absolute(project: Path) -> None:
    expected = int((project / "found_cycles").read_text())
    files = [f"{project}::{w}" for w in (project / "files").read_text().split()]
    assert run_tool("--files", *files, "--strategy", "johnson") == f"Found {expected} import cycles"


@pytest.mark.parametrize("project", PROJECTS, ids=lambda p: p.name)
def test_files_relative(project: Path) -> None:
    expected = int((project / "found_cycles").read_text())
    rel = project.relative_to(REPO)
    files = [f"{rel}::{w}" for w in (project / "files").read_text().split()]
    assert run_tool("--files", *files, "--strategy", "johnson") == f"Found {expected} import cycles"


def test_self() -> None:
    assert (
        run_tool("--packages", str(REPO / "py_import_cycles"), "--strategy", "johnson")
        == "Found 0 import cycles"
    )


def test_stats_are_logged(tmp_path: Path) -> None:
    run_tool(
        "--packages",
        str(REPO / "py_import_cycles"),
        "--stats",
        "--outputs-folder",
        str(tmp_path),
        "--outputs-filename",
        "run",
    )
    assert "Number of found modules" in (tmp_path / "run.log").read_text()


def _run_on_project1(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    package = str(E2E_DIR / "project1" / "pkg")
    return run_cli("--packages", package, "--outputs-folder", str(tmp_path), *args)


def test_exit_status_when_cycles_exceed_threshold(tmp_path: Path) -> None:
    assert _run_on_project1(tmp_path).returncode == 1


def test_exit_status_when_cycles_within_threshold(tmp_path: Path) -> None:
    assert _run_on_project1(tmp_path, "--threshold", "1").returncode == 0


def test_verbose_prints_cycles(tmp_path: Path) -> None:
    assert "Cycle 1:" in _run_on_project1(tmp_path, "--verbose").stderr


def test_sarif_to_stdout(tmp_path: Path) -> None:
    sarif = json.loads(_run_on_project1(tmp_path, "--sarif", "-").stdout)
    assert len(sarif["runs"][0]["results"]) == 1
