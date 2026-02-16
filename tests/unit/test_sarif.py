#!/usr/bin/env python3

from pathlib import Path

from py_import_cycles.modules import PyModule
from py_import_cycles.sarif import make_sarif


def _make_py_module(tmp_path: Path, package: str, module: str) -> PyModule:
    pkg_path = tmp_path / package
    pkg_path.mkdir(parents=True, exist_ok=True)
    (pkg_path / "__init__.py").touch()
    mod_path = pkg_path / f"{module}.py"
    mod_path.touch()
    return PyModule(package=pkg_path, path=mod_path)


def test_empty_cycles() -> None:
    sarif = make_sarif([], "1.0.0")

    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1

    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "py-import-cycles"
    assert run["tool"]["driver"]["version"] == "1.0.0"
    assert not run["results"]


def test_single_cycle(tmp_path: Path) -> None:
    mod_a = _make_py_module(tmp_path, "pkg", "a")
    mod_b = _make_py_module(tmp_path, "pkg", "b")

    sarif = make_sarif([(mod_a, mod_b)], "0.4.1")

    results = sarif["runs"][0]["results"]
    assert len(results) == 1

    result = results[0]
    assert result["ruleId"] == "import-cycle"
    assert result["level"] == "warning"
    assert "pkg.a" in result["message"]["text"]
    assert "pkg.b" in result["message"]["text"]

    assert len(result["locations"]) == 1
    loc = result["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"].endswith("a.py")
    assert loc["region"]["startLine"] == 1

    assert len(result["relatedLocations"]) == 1
    related = result["relatedLocations"][0]["physicalLocation"]
    assert related["artifactLocation"]["uri"].endswith("b.py")


def test_multiple_cycles(tmp_path: Path) -> None:
    mod_a = _make_py_module(tmp_path, "pkg", "a")
    mod_b = _make_py_module(tmp_path, "pkg", "b")
    mod_c = _make_py_module(tmp_path, "pkg", "c")

    cycles = [
        (mod_a, mod_b),
        (mod_a, mod_b, mod_c),
    ]
    sarif = make_sarif(cycles, "0.4.1")

    results = sarif["runs"][0]["results"]
    assert len(results) == 2

    assert "pkg.a" in results[0]["message"]["text"]
    assert "pkg.b" in results[0]["message"]["text"]
    assert "relatedLocations" in results[0]

    assert "pkg.c" in results[1]["message"]["text"]
    assert len(results[1]["relatedLocations"]) == 2
