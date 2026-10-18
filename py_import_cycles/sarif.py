#!/usr/bin/env python3

import os
from collections.abc import Sequence
from typing import NotRequired, TypedDict

from .modules import PyModule

SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
SARIF_VERSION = "2.1.0"
RULE_ID = "import-cycle"


class Region(TypedDict):
    startLine: int
    startColumn: int


class ArtifactLocation(TypedDict):
    uri: str
    uriBaseId: NotRequired[str]


class PhysicalLocation(TypedDict):
    artifactLocation: ArtifactLocation
    region: Region


class Location(TypedDict):
    id: NotRequired[int]
    physicalLocation: PhysicalLocation


class Message(TypedDict):
    text: str


class Result(TypedDict):
    ruleId: str
    level: str
    message: Message
    locations: Sequence[Location]
    relatedLocations: NotRequired[Sequence[Location]]


class Rule(TypedDict):
    id: str
    shortDescription: Message


class Driver(TypedDict):
    name: str
    version: str
    rules: Sequence[Rule]


class Tool(TypedDict):
    driver: Driver


class Run(TypedDict):
    tool: Tool
    results: Sequence[Result]


Sarif = TypedDict("Sarif", {"$schema": str, "version": str, "runs": Sequence[Run]})


def _make_physical_location(py_module: PyModule) -> PhysicalLocation:
    return {
        "artifactLocation": {"uri": os.path.relpath(py_module.path)},
        "region": {"startLine": 1, "startColumn": 1},
    }


def _make_result(cycle: tuple[PyModule, ...]) -> Result:
    cycle_str = " -> ".join(str(m) for m in cycle) + " -> " + str(cycle[0])

    physical_location = _make_physical_location(cycle[0])
    physical_location["artifactLocation"]["uriBaseId"] = "%SRCROOT%"

    result: Result = {
        "ruleId": RULE_ID,
        "level": "warning",
        "message": {"text": f"Import cycle: {cycle_str}"},
        "locations": [{"physicalLocation": physical_location}],
    }
    if related_locations := [
        Location(id=idx, physicalLocation=_make_physical_location(m))
        for idx, m in enumerate(cycle[1:], start=1)
    ]:
        result["relatedLocations"] = related_locations
    return result


def make_sarif(
    sorted_cycles: Sequence[tuple[PyModule, ...]],
    version: str,
) -> Sarif:
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "py-import-cycles",
                        "version": version,
                        "rules": [
                            {
                                "id": RULE_ID,
                                "shortDescription": {"text": "Import cycle detected"},
                            },
                        ],
                    },
                },
                "results": [_make_result(cycle) for cycle in sorted_cycles],
            },
        ],
    }
