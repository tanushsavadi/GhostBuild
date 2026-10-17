# GhostBuild developer commands (docs/15_SONNET_HANDOFF.md §6).
# Targets for lanes that don't exist yet stop with "not yet: <path> missing (owner X)".
# Owners: fill in your lane's command here in a small, separate commit (this file is a merge hotspot).

SHELL := /bin/bash
export PYTHONPATH := $(CURDIR):$(CURDIR)/core:$(CURDIR)/perception
PY := uv run python
need = @test -e $(1) || { echo "not yet: $(1) missing (owner $(2))"; exit 1; }

.PHONY: help doctor setup contracts test lint-generic lint-arkit check-secrets health \
        core core-mock perception spatial-adapter compile compile-proof twin \
        g2-dev g2-sim g2-qr g2-pack demo sentry-bridge fetch-agent

help:
	@grep -E '^[a-z0-9-]+:' Makefile | cut -d: -f1 | tr '\n' ' '; echo

# --- bootstrap -------------------------------------------------------------
doctor:            ## is my environment working?
	@scripts/doctor.sh

setup:             ## python env (3.11, all groups) + node deps that exist
	uv sync --all-groups
	cd contracts/ts && npm ci
	@for d in g2 twin; do [ -f $$d/package-lock.json ] && (cd $$d && npm ci) || true; done

contracts:         ## THE 12:45 contract-lock check: export schema + TS, validate every example in Python and TS
	$(PY) contracts/tools/lock_check.py
	cd contracts/ts && npm run -s check

check-secrets:     ## no real credential in files git would commit
	@scripts/check_secrets.sh

health:            ## are the running services up? (CORE=http://<mac1>:8787 to check another host)
	@scripts/health.sh

# --- lint / test -----------------------------------------------------------
lint-generic:      ## no domain terms in core source or the contract source (05 design rule)
	@! grep -rniE 'lego|brick|stud|2x4|ldraw' --include='*.py' --include='*.ts' \
	    core/ghostbuild_core contracts/models.py contracts/ts/index.ts 2>/dev/null \
	  || { echo "lint-generic: domain terms found above"; exit 1; }
	@echo "lint-generic: ok"

lint-arkit:        ## .resetTracking/.removeExistingAnchors only on lines marked `// first-run` (18 v3 §5)
	@! grep -rnE '\.resetTracking|\.removeExistingAnchors' --include='*.swift' spatial 2>/dev/null | grep -v 'first-run' \
	  || { echo "lint-arkit: reset outside the first-run path"; exit 1; }
	@echo "lint-arkit: ok"

test: contracts lint-generic lint-arkit check-secrets
	@for t in contracts/tests core/tests perception/tests knowledge/tests adapters/lego_grid/tests adapters/spatial_pose/tests; do \
	  [ -d $$t ] && { echo "== pytest $$t"; $(PY) -m pytest -q $$t || exit 1; } || true; done
	@for d in g2 twin; do [ -f $$d/package.json ] && { echo "== $$d"; (cd $$d && npx tsc --noEmit && npx vitest run --passWithNoTests) || exit 1; } || true; done

# --- services (Mac 1 unless noted) -----------------------------------------
core:              ## core :8787
	$(call need,core/ghostbuild_core/__main__.py,D)
	$(PY) -m ghostbuild_core $(CORE_FLAGS)

core-mock:         ## core :8787 on scripted observations
	$(call need,core/ghostbuild_core/__main__.py,D)
	$(PY) -m ghostbuild_core --mock-vision scenarios/demo.yaml --bundle knowledge/fixtures/rocket_bundle.json $(CORE_FLAGS)

perception:        ## webcam -> core (HANDS=--hands to enable hand veto)
	$(call need,perception/ghostbuild_perception,C)
	$(PY) -m ghostbuild_perception --camera 0 --core 'ws://localhost:8787/ws?role=vision' $(HANDS)

spatial-adapter:   ## :8790/pose -> core (only with core --spatial)
	$(call need,adapters/spatial_pose,C)
	$(PY) -m adapters.spatial_pose --listen :8790 --core 'ws://localhost:8787/ws?role=vision'

compile:           ## build-time manual/CAD compiler (TASK=rocket|rover); D wires ARGS to compile.py's real flags
	$(call need,knowledge/compile.py,D)
	$(PY) -m knowledge.compile $(ARGS)

compile-proof:     ## optional offline generality proof (no code changes allowed for it)
	$(call need,knowledge/fixtures/ifixit_158506.pdf,D)
	$(PY) -m knowledge.compile --pdf knowledge/fixtures/ifixit_158506.pdf --kind service_pdf --out knowledge/ifixit-158506/

twin:              ## 2D supervisor: Mac 2 opens http://<mac1>:8787/twin?mode=2d
	@echo "open http://$$(ipconfig getifaddr en0):8787/twin?mode=2d (served by core)"

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

demo:              ## core + perception with the gated-in flags in demo.flags
	$(call need,demo.flags,D)
	$(MAKE) -j2 core perception CORE_FLAGS="$$(cat demo.flags)"

# --- isolated sponsor clients (separate uv projects; never imported) -------
sentry-bridge:     ## Mac 1, nice 19; needs SENTRY_DSN
	$(call need,integrations/sentry_bridge/pyproject.toml,Devin->B)
	cd integrations/sentry_bridge && nice -n 19 uv run python -m sentry_bridge

fetch-agent:       ## B's laptop; GB_CORE_URL required (no default)
	$(call need,integrations/fetch_agent/pyproject.toml,Devin->B)
	@test -n "$$GB_CORE_URL" || { echo "GB_CORE_URL is required; point it at the GhostBuild Core host."; exit 1; }
	cd integrations/fetch_agent && uv run python -m fetch_agent
