#!/usr/bin/env python3

from pathlib import Path

print(
    Path(__file__).relative_to(
        Path("/home/si/private_projects/git/py-import-cycles/tests/projects/project4")
    )
)

import pkg.mod1
import pkg.mod2
import pkg.mod3
