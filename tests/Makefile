SHELL := /bin/bash -e
BLACK := pipenv run ../scripts/run-black
ISORT := pipenv run ../scripts/run-isort
PYTEST := pipenv run py.test -vv unit
MYPY := pipenv run ../scripts/run-mypy
PYLINT := pipenv run ../scripts/run-pylint
SHELLCHECK := ../scripts/run-shellcheck

.PHONY: venv-lock

venv:
	pipenv install --dev

test-format-python:
	@$(BLACK) --diff
	@$(ISORT)

test-unit: venv
	@$(PYTEST)

test-mypy:
	@$(MYPY)

test-pylint:
	@$(PYLINT)

test-scripts:
	@$(SHELLCHECK)

tests: test-format-python test-unit test-mypy test-pylint test-scripts
