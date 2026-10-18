import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
E2E_DIR = REPO / "e2e_test_inputs"
PROJECTS = sorted(p for p in E2E_DIR.iterdir() if p.is_dir())


def run_cli(outputs_folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "-m", "py_import_cycles", "--outputs-folder", str(outputs_folder), *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def run_tool(outputs_folder: Path, *args: str) -> str:
    return run_cli(outputs_folder, *args).stderr.strip()


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
def test_packages(tmp_path: Path, project: Path) -> None:
    expected = int((project / "found_cycles").read_text())
    packages = [str(project / w) for w in (project / "packages").read_text().split()]
    assert (
        run_tool(tmp_path, "--packages", *packages, "--strategy", "johnson")
        == f"Found {expected} import cycles"
    )


def _files_of_project1(root: str) -> Sequence[str]:
    return [f"{root}::{w}" for w in (E2E_DIR / "project1" / "files").read_text().split()]


def test_files_absolute(tmp_path: Path) -> None:
    files = _files_of_project1(str(E2E_DIR / "project1"))
    assert run_tool(tmp_path, "--files", *files) == "Found 1 import cycles"


def test_files_relative(tmp_path: Path) -> None:
    files = _files_of_project1(str((E2E_DIR / "project1").relative_to(REPO)))
    assert run_tool(tmp_path, "--files", *files) == "Found 1 import cycles"


def test_self(tmp_path: Path) -> None:
    assert (
        run_tool(tmp_path, "--packages", str(REPO / "py_import_cycles"), "--strategy", "johnson")
        == "Found 0 import cycles"
    )


def test_stats_are_logged(tmp_path: Path) -> None:
    run_tool(
        tmp_path,
        "--packages",
        str(REPO / "py_import_cycles"),
        "--stats",
        "--outputs-filename",
        "run",
    )
    assert "Number of found modules" in (tmp_path / "run.log").read_text()


def _run_on_project1(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    package = str(E2E_DIR / "project1" / "pkg")
    return run_cli(tmp_path, "--packages", package, *args)


def test_exit_status_when_cycles_exceed_threshold(tmp_path: Path) -> None:
    assert _run_on_project1(tmp_path).returncode == 1


def test_exit_status_when_cycles_within_threshold(tmp_path: Path) -> None:
    assert _run_on_project1(tmp_path, "--threshold", "1").returncode == 0


def test_verbose_prints_cycles(tmp_path: Path) -> None:
    assert "Cycle 1:" in _run_on_project1(tmp_path, "--verbose").stderr


def test_sarif_to_stdout(tmp_path: Path) -> None:
    sarif = json.loads(_run_on_project1(tmp_path, "--sarif", "-").stdout)
    assert len(sarif["runs"][0]["results"]) == 1
