SHELL := /bin/bash -e
BLACK := ../scripts/run-black
ISORT := ../scripts/run-isort
PYTEST := ../scripts/run-pytest
MYPY := ../scripts/run-mypy
PYLINT := ../scripts/run-pylint
SHELLCHECK := ../scripts/run-shellcheck

.PHONY: test-format-python test-unit test-mypy test-pylint test-scripts

test-format-python:
	@$(BLACK) --diff
	@$(ISORT) --check

test-unit:
	@$(PYTEST)

test-mypy:
	@$(MYPY)

test-pylint:
	@$(PYLINT)

test-scripts:
	@$(SHELLCHECK)

tests: test-format-python test-unit test-mypy test-pylint test-scripts
