SHELL := /bin/bash
PIPENV := ./scripts/run-pipenv
LOCK_FD := 200
LOCK_PATH := .venv.lock

.PHONY: setup

setup:
	sudo apt-get install \
	    python3-pip \
	    shellcheck
	python3 -m pip install --user --upgrade \
	    pipenv \
	    virtualenv

Pipfile.lock: Pipfile
	@( \
	    echo "Locking Python requirements..." ; \
	    flock $(LOCK_FD); \
	    SKIP_MAKEFILE_CALL=1 $(PIPENV) lock; RC=$$? ; \
	    rm -rf .venv ; \
	    exit $$RC \
	) $(LOCK_FD)>$(LOCK_PATH)

.venv: Pipfile.lock
	@( \
	    echo "Creating .venv..." ; \
	    flock $(LOCK_FD); \
	    $(RM) -r .venv; \
	    ( SKIP_MAKEFILE_CALL=1 $(PIPENV) sync --dev && touch .venv ) || ( $(RM) -r .venv ; exit 1 ) \
	) $(LOCK_FD)>$(LOCK_PATH)
