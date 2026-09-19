# Concept first, then one command per revision:
#
#     make concept-v2     pictures only, for sign-off — nothing printable
#     make v2             after sign-off: build everything and ship it
#
# Everything is produced by src/build.py from src/geomNN.py; this file only
# creates the venv and runs that one script. Nothing here generates a
# deliverable, so the pictures and the printable files cannot come from
# different models.

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
BUILD  := build
# The venv is uv-managed and has no pip inside it.
PIPI   := $(shell command -v uv >/dev/null 2>&1 && echo "uv pip install --python $(PY)" || echo "$(PY) -m pip install")

.DEFAULT_GOAL := help

help:
	@echo "make concept-vN   render views + schematic from geomNN into $(BUILD)/vN for sign-off"
	@echo "make vN           build geomNN, ship to revisions/vN and the root aliases"
	@echo "make build-vN     build into $(BUILD)/vN only, ship nothing"
	@echo "make verify       rebuild the current revision and diff it against what is shipped"
	@echo "make slice-check  slice the shipped 3MF headless in Bambu Studio, every plate"
	@echo "make deps         create $(VENV) and install the pinned requirements"
	@echo "make clean        remove $(BUILD)/"
	@echo ""
	@echo "Shipping refuses to overwrite an existing revisions/vNN."
	@echo "Pass FORCE=1 only if you really mean to replace a released revision."

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

deps: $(VENV)/bin/python requirements.txt
	@$(PIPI) --quiet -r requirements.txt
	@echo "dependencies installed into $(VENV)"

# Concept pictures only — never shipped, never printable.
concept-v%: deps
	@echo "$*" | grep -qE '^[0-9]+$$' || { \
	  echo "usage: make concept-vN  (e.g. make concept-v2)"; exit 1; }
	@test -f src/geom$$(printf %02d $*).py || { \
	  echo "src/geom$$(printf %02d $*).py does not exist."; \
	  echo "CLAUDE.md step 1: copy the previous geometry module to it and change"; \
	  echo "the parameters there. Never edit a released revision in place."; \
	  exit 1; }
	SILL_OUT=$(BUILD)/v$* $(PY) src/build.py geom$$(printf %02d $*) v$* --concept

# Build only -- leaves revisions/ and the root aliases untouched.
build-v%: deps
	@echo "$*" | grep -qE '^[0-9]+$$' || { \
	  echo "usage: make build-vN  (e.g. make build-v2)"; exit 1; }
	@test -f src/geom$$(printf %02d $*).py || { \
	  echo "src/geom$$(printf %02d $*).py does not exist."; exit 1; }
	SILL_OUT=$(BUILD)/v$* $(PY) src/build.py geom$$(printf %02d $*) v$*

# Build, then copy into revisions/vNN and refresh the root aliases.
v%: build-v%
	@$(PY) src/ship.py v$* $(if $(FORCE),--force,)

# Rebuild whatever the root currently ships and diff it, without shipping
# anything. Use this to confirm a checkout still reproduces its own output.
verify: deps
	@$(PY) src/verify.py

# Open and slice the shipped 3MF in Bambu Studio itself. Needs bambu-studio.
slice-check:
	@$(PY) src/slicecheck.py

clean:
	rm -rf $(BUILD)

.PHONY: help deps verify slice-check clean
