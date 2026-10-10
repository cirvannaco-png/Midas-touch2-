import json
from contextlib import nullcontext
from unittest.mock import patch

import pytest

from submit_tester_evidence import EvidenceSubmissionError, submit_bundle


def _bundle():
    return {
        "strategy": "SMC",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "parameters": {"min_confidence": 60},
        "data_version": "xauusd-m15-v1",
        "optimizer_version": "optimizer-v1",
        "provenance": {
            "source": "MT5_STRATEGY_TESTER",
            "run_id": "run-001",
            "report_sha256": "a" * 64,
            "dataset_sha256": "b" * 64,
        },
        "trades": [{"trade_id": "1"}],
    }


def _write_bundle(tmp_path, payload=None):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload or _bundle()), encoding="utf-8")
    return path


def test_submit_tester_evidence_dry_run_does_not_need_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("BRIDGE_API_KEY", raising=False)
    monkeypatch.delenv("BRIDGE_BASE_URL", raising=False)
    path = _write_bundle(tmp_path)
    result = submit_bundle(path, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["run_id"] == "run-001"
    assert len(result["payload_sha256"]) == 64
    assert result["endpoint"] == "/research/backtest-evidence"


def test_submit_tester_evidence_requires_https_and_key(tmp_path):
    path = _write_bundle(tmp_path)
    with pytest.raises(EvidenceSubmissionError, match="https://"):
        submit_bundle(path, base_url="http://bridge.example", api_key="secret")
    with pytest.raises(EvidenceSubmissionError, match="BRIDGE_API_KEY"):
        submit_bundle(path, base_url="https://bridge.example", api_key="")


def test_submit_tester_evidence_sends_auth_without_logging_it(tmp_path):
    path = _write_bundle(tmp_path)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "status": "stored",
                "config_hash": "c" * 64,
                "evidence_version": 2,
                "decision": "VALIDATED",
                "lifecycle_status": "VALIDATED",
            }).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["key"] = request.get_header("X-api-key")
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode())
        return FakeResponse()

    with patch("submit_tester_evidence.urlopen", fake_urlopen):
        result = submit_bundle(
            path,
            base_url="https://bridge.example",
            api_key="secret-value",
            timeout=45,
        )

    assert captured["url"] == "https://bridge.example/research/backtest-evidence"
    assert captured["key"] == "secret-value"
    assert captured["timeout"] == 45
    assert captured["body"]["provenance"]["run_id"] == "run-001"
    assert result["decision"] == "VALIDATED"
    assert result["evidence_version"] == 2
    assert "secret-value" not in json.dumps(result)


def test_submit_tester_evidence_rejects_bad_source_digest(tmp_path):
    payload = _bundle()
    payload["provenance"]["report_sha256"] = "not-a-sha"
    path = _write_bundle(tmp_path, payload)
    with pytest.raises(EvidenceSubmissionError, match="report_sha256"):
        submit_bundle(path, dry_run=True)
