#!/usr/bin/env python3

from pathlib import Path

print(
    Path(__file__).relative_to(
        Path("/home/si/private_projects/git/py-import-cycles/tests/projects/project5")
    )
)

from pkg1 import mod1
