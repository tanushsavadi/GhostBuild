# GhostBuild developer commands (docs/15_SONNET_HANDOFF.md §6).
# Targets for lanes that don't exist yet stop with "not yet: <path> missing (owner X)".
# Owners: fill in your lane's command here in a small, separate commit (this file is a merge hotspot).

SHELL := /bin/bash
export PYTHONPATH := $(CURDIR):$(CURDIR)/core:$(CURDIR)/pi
PY := uv run python
need = @test -e $(1) || { echo "not yet: $(1) missing (owner $(2))"; exit 1; }

.PHONY: help doctor setup contracts test lint-generic check-secrets health \
        core core-sim pi pi-sim guides compile g2-dev g2-sim g2-qr g2-pack demo

help:
	@grep -E '^[a-z0-9-]+:' Makefile | cut -d: -f1 | tr '\n' ' '; echo

# --- bootstrap -------------------------------------------------------------
doctor:            ## is my environment working?
	@scripts/doctor.sh

setup:             ## python env (3.11, all groups) + node deps that exist
	uv sync --all-groups
	cd contracts/ts && npm ci
	@for d in g2; do [ -f $$d/package-lock.json ] && (cd $$d && npm ci) || true; done

contracts:         ## THE 12:45 contract-lock check: export schema + TS, validate every example in Python and TS
	$(PY) contracts/tools/lock_check.py
	cd contracts/ts && npm run -s check

check-secrets:     ## no real credential in files git would commit
	@scripts/check_secrets.sh

health:            ## are the running services up? (CORE=http://<mac1>:8787 to check another host)
	@scripts/health.sh

# --- lint / test -----------------------------------------------------------
lint-generic:      ## no domain terms in core source or the contract source (05 design rule)
	@! grep -rniE 'lego|brick|ldraw|picamera|gpiozero|raspberry' --include='*.py' --include='*.ts' \
	    core/ghostbuild_core contracts/models.py contracts/ts/index.ts 2>/dev/null \
	  || { echo "lint-generic: domain terms found above"; exit 1; }
	@echo "lint-generic: ok"

test: contracts lint-generic check-secrets
	@for t in contracts/tests core/tests pi/tests knowledge/tests assets/tests; do \
	  [ -d $$t ] && { echo "== pytest $$t"; $(PY) -m pytest -q $$t || exit 1; } || true; done
	@for d in g2; do [ -f $$d/package.json ] && { echo "== $$d"; (cd $$d && npx tsc --noEmit && npx vitest run --passWithNoTests) || exit 1; } || true; done

# --- services (Mac 1 unless noted) -----------------------------------------
core:              ## core :8787 (live Pi observations)
	$(call need,core/ghostbuild_core/__main__.py,D)
	$(PY) -m ghostbuild_core $(CORE_FLAGS)

core-sim:          ## core :8787 fed by SIMULATED observations (banner: SIMULATED; never a judge demo)
	$(call need,core/ghostbuild_core/__main__.py,D)
	$(PY) -m ghostbuild_core --simulate $(CORE_FLAGS)

pi:                ## run ON the Pi: camera + LED -> core (CORE=http://<laptop>:8787)
	$(call need,pi/ghostbuild_pi/__main__.py,C)
	cd pi && python3 -m ghostbuild_pi --core $(CORE)

pi-sim:            ## laptop: Pi client with a fake camera (source=simulated)
	$(call need,pi/ghostbuild_pi/__main__.py,C)
	cd pi && $(PY) -m ghostbuild_pi --fake-camera --core $${CORE:-http://localhost:8787}

guides:            ## build G2-ready guide PNGs from knowledge/guides sources
	$(call need,assets/build_guides.py,A)
	$(PY) assets/build_guides.py

compile:           ## optional build-time card compiler (needs ANTHROPIC_API_KEY)
	$(call need,knowledge/compile.py,D)
	$(PY) -m knowledge.compile $(ARGS)

# --- G2 (B's laptop) -------------------------------------------------------
g2-dev:
	$(call need,g2/package.json,B)
	cd g2 && npx vite --host --port 5173

g2-sim:
	evenhub-simulator -g http://localhost:5173

g2-qr:
	evenhub qr --url "http://$$(ipconfig getifaddr en0):5173"

g2-pack:
	$(call need,g2/app.json,B)
	cd g2 && npm run build && evenhub pack app.json dist -o ghostbuild.ehpk --sdk-ver 0.0.16 -c

demo:              ## core + browser mirror; run `make pi` on the Pi and open G2
	$(call need,core/ghostbuild_core/__main__.py,D)
	$(PY) -m ghostbuild_core $(CORE_FLAGS)

# Superseded by PIVOT §0A: perception, compile-proof, twin, sentry-bridge, fetch-agent targets were removed.
# integrations/* directories are kept as history; sponsor work stays outside core/, g2/, pi/.
