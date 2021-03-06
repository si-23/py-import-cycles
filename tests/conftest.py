#!/usr/bin/env python3

import os
import sys


def _repo_path() -> str:
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _add_python_paths() -> None:
    # make the repo directory available
    sys.path.insert(0, _repo_path())


_add_python_paths()
