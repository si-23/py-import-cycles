#!/usr/bin/env python3

from pathlib import Path

print(
    Path(__file__).relative_to(
        Path("/home/si/private_projects/git/py-import-cycles/tests/projects/project7")
    )
)

import pkg.pkg1.mod1
import pkg.pkg2.mod2
import pkg.pkg3.mod3
