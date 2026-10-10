"""Submit a normalized MT5 Tester evidence JSON bundle to the protected bridge API.

This is a transport client, not an MT5 report parser. A trusted exporter must
produce the endpoint's normalized evidence schema from genuine Tester artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
REQUIRED_TOP_LEVEL = {
    "strategy",
    "instrument",
    "timeframe",
    "parameters",
    "data_version",
    "optimizer_version",
    "provenance",
    "trades",
}


class EvidenceSubmissionError(RuntimeError):
    """Safe-to-display submission error; never contains request headers/secrets."""


def load_bundle(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise EvidenceSubmissionError(f"evidence file not found: {source}")
    raw = source.read_bytes()
    maximum = int(os.environ.get("MAX_BACKTEST_EVIDENCE_BODY_SIZE", DEFAULT_MAX_UPLOAD_BYTES))
    if maximum < 1:
        raise EvidenceSubmissionError("MAX_BACKTEST_EVIDENCE_BODY_SIZE must be positive")
    if len(raw) > maximum:
        raise EvidenceSubmissionError(
            f"evidence file is {len(raw)} bytes; upload limit is {maximum} bytes"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceSubmissionError("evidence file must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise EvidenceSubmissionError("evidence JSON root must be an object")
    missing = sorted(REQUIRED_TOP_LEVEL - set(payload))
    if missing:
        raise EvidenceSubmissionError(f"evidence bundle is missing required fields: {', '.join(missing)}")
    if not isinstance(payload.get("parameters"), dict) or not payload["parameters"]:
        raise EvidenceSubmissionError("parameters must be a non-empty JSON object")
    if not isinstance(payload.get("trades"), list) or not payload["trades"]:
        raise EvidenceSubmissionError("trades must be a non-empty JSON array")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise EvidenceSubmissionError("provenance must be a JSON object")
    if provenance.get("source") != "MT5_STRATEGY_TESTER":
        raise EvidenceSubmissionError("provenance.source must be MT5_STRATEGY_TESTER")
    if not str(provenance.get("run_id", "")).strip():
        raise EvidenceSubmissionError("provenance.run_id is required")
    for name in ("report_sha256", "dataset_sha256"):
        if not SHA256_RE.fullmatch(str(provenance.get(name, ""))):
            raise EvidenceSubmissionError(f"provenance.{name} must be a SHA-256 hex digest")
    return payload


def _encode_payload(payload: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvidenceSubmissionError("evidence bundle contains non-JSON or non-finite values") from exc


def submit_bundle(
    path: str | Path,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    payload = load_bundle(path)
    body = _encode_payload(payload)
    maximum = int(os.environ.get("MAX_BACKTEST_EVIDENCE_BODY_SIZE", DEFAULT_MAX_UPLOAD_BYTES))
    if len(body) > maximum:
        raise EvidenceSubmissionError(
            f"normalized evidence payload is {len(body)} bytes; upload limit is {maximum} bytes"
        )
    payload_digest = hashlib.sha256(body).hexdigest()
    run_id = payload["provenance"]["run_id"]
    if dry_run:
        return {
            "status": "dry_run",
            "run_id": run_id,
            "payload_sha256": payload_digest,
            "bytes": len(body),
            "endpoint": "/research/backtest-evidence",
        }

    target = (base_url or os.environ.get("BRIDGE_BASE_URL", "")).strip().rstrip("/")
    secret = api_key or os.environ.get("BRIDGE_API_KEY", "")
    if not target.startswith("https://"):
        raise EvidenceSubmissionError("BRIDGE_BASE_URL must be configured with an https:// URL")
    if not secret:
        raise EvidenceSubmissionError("BRIDGE_API_KEY is required; provide it through the environment")
    if timeout <= 0:
        raise EvidenceSubmissionError("timeout must be positive")

    request = Request(
        target + "/research/backtest-evidence",
        data=body,
        method="POST",
        headers={
            "X-API-Key": secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read()
            status_code = response.status
    except HTTPError as exc:
        detail = ""
        try:
            decoded = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(decoded)
            detail = str(parsed.get("detail", "")) if isinstance(parsed, dict) else ""
        except Exception:
            detail = ""
        suffix = f": {detail}" if detail else ""
        raise EvidenceSubmissionError(f"bridge rejected Tester evidence (HTTP {exc.code}){suffix}") from exc
    except URLError as exc:
        raise EvidenceSubmissionError(f"could not reach the evidence endpoint ({type(exc.reason).__name__})") from exc
    except TimeoutError as exc:
        raise EvidenceSubmissionError("evidence submission timed out") from exc

    try:
        result = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceSubmissionError(f"bridge returned non-JSON response (HTTP {status_code})") from exc
    if not isinstance(result, dict):
        raise EvidenceSubmissionError(f"bridge returned an unexpected response (HTTP {status_code})")
    if status_code < 200 or status_code >= 300:
        raise EvidenceSubmissionError(f"bridge returned HTTP {status_code}")
    return {
        "status": result.get("status", "submitted"),
        "http_status": status_code,
        "run_id": run_id,
        "config_hash": result.get("config_hash"),
        "evidence_version": result.get("evidence_version"),
        "decision": result.get("decision"),
        "lifecycle_status": result.get("lifecycle_status"),
        "payload_sha256": payload_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Normalized Tester evidence JSON bundle")
    parser.add_argument("--base-url", help="HTTPS bridge base URL (or BRIDGE_BASE_URL)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without sending data")
    args = parser.parse_args()
    try:
        result = submit_bundle(
            args.file,
            base_url=args.base_url,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    except EvidenceSubmissionError as exc:
        print(f"submit_tester_evidence: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
