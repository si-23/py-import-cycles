import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
E2E_DIR = REPO / "e2e_test_inputs"
PROJECTS = sorted(p for p in E2E_DIR.iterdir() if p.is_dir())


def run_tool(*args: str) -> str:
    result = subprocess.run(
        ["uv", "run", "-m", "py_import_cycles", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    return result.stderr.strip()


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
