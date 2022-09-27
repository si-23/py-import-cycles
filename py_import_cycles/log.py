#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(filepath: Path, opt_debug: bool) -> None:
    filepath.unlink(missing_ok=True)

    if opt_debug:
        sys.stderr.write(f"Write log to {filepath}\n")
        log_level = logging.DEBUG
    else:
        log_level = logging.NOTSET

    logger.setLevel(log_level)

    handler = logging.FileHandler(filename=filepath)
    handler.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
