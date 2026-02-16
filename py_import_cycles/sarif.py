#!/usr/bin/env python3

import os
from collections.abc import Mapping, Sequence
from typing import Any

from .modules import PyModule


def make_sarif(
    sorted_cycles: Sequence[tuple[PyModule, ...]],
    version: str,
) -> Mapping[str, Any]:
    results = []
    for cycle in sorted_cycles:
        cycle_str = " -> ".join(str(m) for m in cycle) + " -> " + str(cycle[0])

        locations = [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": os.path.relpath(cycle[0].path)},
                    "region": {"startLine": 1, "startColumn": 1},
                },
            },
        ]

        related_locations = [
            {
                "id": idx,
                "physicalLocation": {
                    "artifactLocation": {"uri": os.path.relpath(m.path)},
                    "region": {"startLine": 1, "startColumn": 1},
                },
            }
            for idx, m in enumerate(cycle[1:], start=1)
        ]

        result: dict = {
            "ruleId": "import-cycle",
            "level": "warning",
            "message": {"text": f"Import cycle: {cycle_str}"},
            "locations": locations,
        }
        if related_locations:
            result["relatedLocations"] = related_locations

        results.append(result)

    return {
        "$schema": (
            # pylint: disable=line-too-long
            "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
        ),
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "py-import-cycles",
                        "version": version,
                        "rules": [
                            {
                                "id": "import-cycle",
                                "shortDescription": {
                                    "text": "Import cycle detected",
                                },
                            },
                        ],
                    },
                },
                "results": results,
            },
        ],
    }
