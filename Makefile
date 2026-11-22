# TCGTube — one command to build: `make build`
PY ?= .venv/bin/python
.PHONY: setup build rank site test mine refresh serve clean

setup:            ## create venv + deps
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

build: setup-if-needed  ## rank (if raw data exists) + build site/ from corpus/
	@if ls data/vouches_arctic/*.jsonl >/dev/null 2>&1 || ls data/vouches/*.jsonl >/dev/null 2>&1; then \
	  [ -f data/legacy.json ] || $(PY) pipeline/import_legacy.py; \
	  $(PY) pipeline/aggregate.py; \
	else echo "no raw vouches in data/: building from committed corpus/"; fi
	$(PY) pipeline/build_site.py

site: setup-if-needed     ## build site/ from committed corpus/ only (no network)
	$(PY) pipeline/build_site.py

rank: setup-if-needed
	$(PY) pipeline/aggregate.py

test: setup-if-needed
	$(PY) -m pytest -q

mine: setup-if-needed     ## full (resumable) Arctic Shift mine; hours on first run
	$(PY) pipeline/mine_arctic.py

refresh: setup-if-needed  ## weekly: re-mine the last 2 months, rank, build
	./scripts/refresh.sh

serve:
	python3 -m http.server 8000 -d site

setup-if-needed:
	@[ -x $(PY) ] || $(MAKE) setup

clean:
	rm -rf site
