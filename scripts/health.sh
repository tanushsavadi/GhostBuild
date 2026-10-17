#!/usr/bin/env bash
# "Are the services up?" CORE=http://<mac1>:8787 G2=<host> to probe other machines.
CORE=${CORE:-http://localhost:8787}
G2=${G2:-localhost}
probe() { if eval "$2" >/dev/null 2>&1; then echo "UP    $1"; else echo "DOWN  $1"; fi; }
curl -fsS --max-time 2 "$CORE/health" && echo || echo "DOWN  core $CORE/health"
probe "g2 plugin dev http://$G2:5173"       "curl -fsS --max-time 2 -o /dev/null http://$G2:5173"
