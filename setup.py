#!/usr/bin/env python3

from pathlib import Path

from setuptools import setup


def read(version_filepath: Path) -> str:
    with version_filepath.open("r") as fp:
        return fp.read()


def get_version(version_filepath: Path) -> str:
    for line in read(version_filepath).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]

    raise RuntimeError("Unable to find version string.")


# The directory containing this file
HERE = Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="py-import-cycles",
    version=get_version(HERE / "py_import_cycles/__init__.py"),
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
            "py_import_cycles=py_import_cycles.__main__:main",
        ]
    },
)
