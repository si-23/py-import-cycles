#!/usr/bin/env python3

import pathlib

from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="py-import-cycles",
    version="0.1.4",
    description="Detect import cycles in Python projects",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/si-23/py-import-cycles",
    author="Simon Jess",
    author_email="simon86betz@yahoo.de",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
    packages=["py_import_cycles"],
    include_package_data=True,
    install_requires=["graphviz"],
    entry_points={
        "console_scripts": [
            "py_import_cycles=py_import_cycles.main:main",
        ]
    },
)
