default:
    @just --list

clean:
    rm -rf .cache .mypy_cache .pytest_cache .venv ./*.egg-info build
    find py_import_cycles tests -type d -name __pycache__ -print0 | xargs --null --no-run-if-empty rm -rf

test:
    uv run pytest

check-format:
    uv run ruff format --check --diff

mypy:
    uv run mypy py_import_cycles tests

lint:
    uv run ruff check --diff

bandit:
    uv run bandit --configfile=pyproject.toml --quiet --recursive --severity-level=medium py_import_cycles tests

e2e:
    ./scripts/run-e2e-tests

format:
    uv run ruff format
    uv run ruff check --fix

docs:
    @echo "TODO: generate documentation"

ci: test check-format mypy lint bandit e2e
