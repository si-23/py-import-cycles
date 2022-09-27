#!/usr/bin/env python3

import sys

from .cli import main as cli_main


def main() -> int:
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
