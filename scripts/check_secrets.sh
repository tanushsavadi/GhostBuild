#!/usr/bin/env bash
# Fails if a file git would commit contains something that looks like a real credential.
cd "$(dirname "$0")/.."
if git rev-parse --git-dir >/dev/null 2>&1; then files=$(git ls-files -co --exclude-standard); else files=$(find . -type f -not -path './.git/*' -not -path '*/node_modules/*' -not -path './.venv/*'); fi
pat='sk-ant-[A-Za-z0-9_-]{20,}|capi_[A-Za-z0-9_-]{20,}|https://[0-9a-f]{20,}@[a-z0-9.]*ingest[a-z0-9.]*sentry\.io|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abpr]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|^(ANTHROPIC_API_KEY|ELEVENLABS_API_KEY|CREAO_API_KEY|SENTRY_DSN|AGENT_SEED)=[A-Za-z0-9_-]{20,}'
hits=$(echo "$files" | grep -v -E '(^|/)scripts/check_secrets\.sh$' | tr '\n' '\0' | xargs -0 grep -lIE "$pat" 2>/dev/null)
if [ -n "$hits" ]; then echo "$hits"; echo "check-secrets: possible credential(s) in these files (values withheld)"; exit 1; fi
echo "check-secrets: ok ($(echo "$files" | wc -l | tr -d ' ') files scanned)"
