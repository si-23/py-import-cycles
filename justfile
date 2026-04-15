set positional-arguments := true

default:
    @just --list

clean:
    rm -rf .cache .mypy_cache .pytest_cache .venv ./*.egg-info build
    find py_import_cycles tests -type d -name __pycache__ -print0 | xargs --null --no-run-if-empty rm -rf

test *args:
    uv run pytest {{ args }}

lint *args:
    pre-commit run {{ args }}

lint-all:
    pre-commit run --all-files

docs:
    @echo "TODO: generate documentation"

ci: lint-all test

update:
    uv sync
    pre-commit autoupdate
