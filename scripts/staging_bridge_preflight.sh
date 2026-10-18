#!/usr/bin/env bash
# Read-only staging smoke test. Never prints the API key or response body.
set -euo pipefail

: "${BRIDGE_BASE_URL:?Set BRIDGE_BASE_URL to the staging HTTPS URL}"
: "${BRIDGE_API_KEY:?Set BRIDGE_API_KEY to the staging SECRET_KEY}"

python3 - <<'PY'
import os
from urllib.parse import urlsplit

raw = os.environ["BRIDGE_BASE_URL"].strip()
parsed = urlsplit(raw)
if (
    parsed.scheme != "https"
    or not parsed.hostname
    or parsed.username
    or parsed.password
    or parsed.query
    or parsed.fragment
    or any(char.isspace() for char in raw)
):
    raise SystemExit("BRIDGE_BASE_URL must be an HTTPS origin/path without credentials, query, fragment, or whitespace.")
if not os.environ["BRIDGE_API_KEY"].strip():
    raise SystemExit("BRIDGE_API_KEY must be non-empty.")
PY

base="${BRIDGE_BASE_URL%/}"
health_body="$(mktemp)"
ledger_body="$(mktemp)"
unauth_body="$(mktemp)"
trap 'rm -f "$health_body" "$ledger_body" "$unauth_body"' EXIT

request_code() {
  local output_file="$1"
  shift
  curl --silent --show-error --output "$output_file" --write-out '%{http_code}' \
    --connect-timeout 8 --max-time 15 --retry 0 "$@"
}

# This route executes a real SELECT 1 through the running app's DATABASE_URL.
health_code="$(request_code "$health_body" --request GET --header 'Accept: application/json' "$base/health/db")"
if [[ "$health_code" != "200" ]]; then
  echo "FAIL: /health/db returned HTTP $health_code."
  exit 1
fi
python3 - "$health_body" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    body = json.load(stream)
if body.get("status") != "online" or body.get("database") != "connected":
    raise SystemExit("FAIL: bridge or database health is degraded.")
print("PASS: database-backed /health/db returned healthy status.")
PY

ledger_code="$(request_code "$ledger_body" --request GET \
  --header "X-API-Key: ${BRIDGE_API_KEY}" \
  --header 'Accept: application/json' "$base/execution-ledger/health")"
if [[ "$ledger_code" != "200" ]]; then
  echo "FAIL: authenticated execution-ledger health returned HTTP $ledger_code."
  exit 1
fi
python3 - "$ledger_body" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    body = json.load(stream)
expected = {
    "status": "online",
    "database": "connected",
    "execution_ledger": "ready",
}
if any(body.get(key) != value for key, value in expected.items()):
    raise SystemExit("FAIL: execution-ledger response is degraded or incomplete.")
print("PASS: authenticated execution-ledger and database health verified.")
PY

unauth_code="$(request_code "$unauth_body" --request GET \
  --header 'Accept: application/json' "$base/execution-ledger/health")"
if [[ "$unauth_code" != "401" ]]; then
  echo "FAIL: missing API key should return HTTP 401, got HTTP $unauth_code."
  exit 1
fi
echo "PASS: unauthenticated execution-ledger health returned HTTP 401."
echo "All read-only staging preflight checks passed."
