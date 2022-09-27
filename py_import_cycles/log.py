#!/usr/bin/env python3

import logging
import sys

from .files import OutputsFilepaths

logger = logging.getLogger(__name__)


def setup_logging(outputs_filepaths: OutputsFilepaths, opt_debug: bool) -> None:
    log_filepath = outputs_filepaths.log
    log_filepath.unlink(missing_ok=True)

    if opt_debug:
        sys.stderr.write(f"Write log to {log_filepath}\n")
        log_level = logging.DEBUG
    else:
        log_level = logging.NOTSET

    logger.setLevel(log_level)

    handler = logging.FileHandler(filename=log_filepath)
    handler.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
