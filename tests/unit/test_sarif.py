#!/usr/bin/env python3

from collections.abc import Callable
from pathlib import Path

from py_import_cycles.modules import PyModule
from py_import_cycles.sarif import make_sarif


def test_sarif_version() -> None:
    assert make_sarif([], "1.0.0")["version"] == "2.1.0"


def test_tool_name() -> None:
    assert make_sarif([], "1.0.0")["runs"][0]["tool"]["driver"]["name"] == "py-import-cycles"


def test_tool_version() -> None:
    assert make_sarif([], "1.0.0")["runs"][0]["tool"]["driver"]["version"] == "1.0.0"


def test_no_results_without_cycles() -> None:
    assert not make_sarif([], "1.0.0")["runs"][0]["results"]


def test_one_result_per_cycle(make_py_module: Callable[[str], PyModule]) -> None:
    a, b, c = (make_py_module(n) for n in "abc")
    sarif = make_sarif([(a, b), (a, b, c)], "0.4.1")
    assert len(sarif["runs"][0]["results"]) == 2


def test_result_rule_id(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    assert make_sarif([(a, b)], "0.4.1")["runs"][0]["results"][0]["ruleId"] == "import-cycle"


def test_result_level(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    assert make_sarif([(a, b)], "0.4.1")["runs"][0]["results"][0]["level"] == "warning"


def test_result_message(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    result = make_sarif([(a, b)], "0.4.1")["runs"][0]["results"][0]
    assert result["message"]["text"] == "Import cycle: pkg.a -> pkg.b -> pkg.a"


def test_location_is_first_module(make_py_module: Callable[[str], PyModule]) -> None:
    a, b = make_py_module("a"), make_py_module("b")
    result = make_sarif([(a, b)], "0.4.1")["runs"][0]["results"][0]
    assert [
        Path(loc["physicalLocation"]["artifactLocation"]["uri"]).name for loc in result["locations"]
    ] == ["a.py"]


def test_related_locations_are_remaining_modules(
    make_py_module: Callable[[str], PyModule],
) -> None:
    a, b, c = (make_py_module(n) for n in "abc")
    result = make_sarif([(a, b, c)], "0.4.1")["runs"][0]["results"][0]
    assert [
        Path(loc["physicalLocation"]["artifactLocation"]["uri"]).name
        for loc in result["relatedLocations"]
    ] == ["b.py", "c.py"]
