#!/usr/bin/env bash
# "Is my environment working?" — prints ok/MISSING per tool. Lane-specific tools are informational.
cd "$(dirname "$0")/.."
fail=0
chk() { if eval "$2" >/dev/null 2>&1; then printf "ok       %-28s %s\n" "$1" "$(eval "$2" 2>&1 | head -1)"; else printf "MISSING  %-28s (%s)\n" "$1" "$3"; [ "$3" = all ] && fail=1; fi; }
echo "== everyone"
chk git            "git --version"                 all
chk uv             "uv --version"                  all
chk "python 3.11"  "uv python find 3.11"           all
chk node           "node --version"                all
chk npm            "npm --version"                 all
chk ".venv synced" "uv run --frozen python -c 'import pydantic, fastapi; print(\"pydantic\", pydantic.VERSION)'" all
chk "contracts/ts deps" "test -d contracts/ts/node_modules && echo installed" all
echo "== lane tools (only your lane needs its line)"
chk "evenhub CLI (B)"        "(cd g2 && npx --no-install evenhub --version)" "B: cd g2 && npm ci"
chk "evenhub-simulator (B)"  "(cd g2 && npx --no-install evenhub-simulator --version)" "B: cd g2 && npm ci && npm rebuild @evenrealities/evenhub-simulator"
chk "tailscale (optional)"   "tailscale version"                   "only for the HTTPS-tunnel fallback if http://LAN is blocked in the packaged app"
chk "pymupdf+anthropic (D)" "uv run --frozen python -c 'import pymupdf, anthropic; print(anthropic.__version__)'" "D: uv sync --all-groups"
echo "== env"
[ -f .env ] && echo "ok       .env present (gitignored)" || echo "info     no .env (copy .env.example when your lane needs keys)"
exit $fail
