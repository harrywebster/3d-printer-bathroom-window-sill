# One command per revision:
#
#     make v1
#
# builds src/geom01.py and ships it. Everything shipped is produced by
# src/build.py; this file only creates the venv, runs that one script, and
# hands its output to src/ship.py to copy. Nothing here generates a
# deliverable, so the renders and the printable files cannot come from
# different models.

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
BUILD  := build
UV     := $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)

.DEFAULT_GOAL := help

help:
	@echo "make v1          build geom01, ship to revisions/v1 and the root aliases"
	@echo "make build-v1    build into $(BUILD)/v1 only, ship nothing"
	@echo "make deps        create $(VENV) and install the pinned requirements (via uv)"
	@echo "make verify      rebuild the current revision and diff it against what is shipped"
	@echo "make clean       remove $(BUILD)/"
	@echo ""
	@echo "Shipping refuses to overwrite an existing revisions/vNN."
	@echo "Pass FORCE=1 only if you really mean to replace a released revision."

$(VENV)/bin/python:
	$(UV) venv $(VENV)

# uv, not pip: this venv is created and populated by uv, and has no pip
# module installed into it.
deps: $(VENV)/bin/python requirements.txt
	@$(UV) pip install --quiet --python $(PY) -r requirements.txt
	@echo "dependencies installed into $(VENV)"

# Build only -- leaves revisions/ and the root aliases untouched.
build-v%: deps
	@echo "$*" | grep -qE '^[0-9]+$$' || { \
	  echo "usage: make build-vNN  (e.g. make build-v1)"; exit 1; }
	@test -f src/geom$$(printf %02d $*).py || { \
	  echo "src/geom$$(printf %02d $*).py does not exist."; \
	  echo "CLAUDE.md step 1: copy the previous geometry module to it and change"; \
	  echo "the parameters there. Never edit a released revision in place."; \
	  exit 1; }
	SILLDRAIN_OUT=$(BUILD)/v$* $(PY) src/build.py geom$$(printf %02d $*) v$*

# Build, then copy into revisions/vNN and refresh the root aliases.
v%: build-v%
	@$(PY) src/ship.py v$* $(if $(FORCE),--force,)

# Rebuild whatever the root currently ships and diff it, without shipping
# anything. Use this to confirm a checkout still reproduces its own output.
verify: deps
	@$(PY) src/verify.py

clean:
	rm -rf $(BUILD)

.PHONY: help deps verify clean
