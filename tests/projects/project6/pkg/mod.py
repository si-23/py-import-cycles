#!/usr/bin/env python3

from pathlib import Path

print(
    Path(__file__).relative_to(
        Path("/home/si/private_projects/git/py-import-cycles/tests/projects/project6")
    )
)

from .pkg1 import mod1
from .pkg2 import mod2
from .pkg3 import mod3
