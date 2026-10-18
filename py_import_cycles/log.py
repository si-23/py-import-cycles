#!/usr/bin/env python3

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(filepath: Path, level: int) -> None:
    filepath.unlink(missing_ok=True)

    logger.setLevel(level)

    handler = logging.FileHandler(filename=filepath)
    handler.setLevel(level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
