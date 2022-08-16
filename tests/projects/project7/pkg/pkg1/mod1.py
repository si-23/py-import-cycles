#!/usr/bin/env python3

from pathlib import Path

print(
    Path(__file__).relative_to(
        Path("/home/si/private_projects/git/py-import-cycles/tests/projects/project7")
    )
)

from ..pkg2 import mod2
