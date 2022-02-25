SHELL := /bin/bash -e
BLACK := ../scripts/run-black
ISORT := ../scripts/run-isort
PYTEST := py.test -vv unit
MYPY := ../scripts/run-mypy
PYLINT := ../scripts/run-pylint
SHELLCHECK := ../scripts/run-shellcheck

test-format-python:
	@$(BLACK) --diff
	@$(ISORT)

test-unit:
	@$(PYTEST)

test-mypy:
	@$(MYPY)

test-pylint:
	@$(PYLINT)

test-scripts:
	@$(SHELLCHECK)

tests: test-format-python test-unit test-mypy test-pylint test-scripts
