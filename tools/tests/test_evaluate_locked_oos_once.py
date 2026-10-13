import csv
import hashlib
import json
from pathlib import Path

import pytest

try:
    from tools.evaluate_locked_oos_once import LockedOOSGateError, evaluate_once
except ImportError:
    from evaluate_locked_oos_once import LockedOOSGateError, evaluate_once


def _make_fixture(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    dataset = root / "ticks.bin"
    dataset.write_bytes(b"synthetic fixture only; not strategy or OOS trading history")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    context = {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2026-01-01T00:00:00Z",
        "locked_oos_start": "2025-10-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "dataset_sha256": digest,
        "ea_source_sha": "a" * 40,
        "ea_build": "synthetic-test-build",
        "terminal_build": "synthetic-test-terminal",
        "data_vendor": "SyntheticFixture",
        "spread_model": "real_ticks",
        "spread_points": None,
        "commission_per_lot": 7.0,
        "slippage_points": 2.0,
        "fill_policy": "real_ticks",
        "initial_balance": 10000.0,
        "risk_percent": 0.5,
        "account_currency": "USD",
        "leverage": "1:500",
    }
    variants = []
    for role, toggle in (("htf_trailing_off", "false"), ("htf_trailing_on", "true")):
        preset = root / f"{role}.set"
        preset.write_text(
            "\n".join([
                f"InpDynamicStopUseHTFReferenceLevels={toggle}||N",
                "InpDynamicStopUseWeeklyReference=true||N",
                "InpDynamicStopUseMonthlyReference=true||N",
                "InpRiskPercentPerTrade=0.5||0.1||0.1||1.0||N",
            ]) + "\n",
            encoding="utf-8",
        )
        report = root / f"{role}.html"
        report.write_text(f"synthetic fixture report only: {role}\n", encoding="utf-8")
        deals = root / f"{role}_deals.csv"
        with deals.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee"])
            writer.writerow(["P1", "2025-09-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0])
            writer.writerow(["P1", "2025-09-05T11:00:00Z", "out", 1.0, 5.0, -1.0, 0.0, 0.0])
            writer.writerow(["P2", "2025-10-05T10:00:00Z", "in", 1.0, 0.0, -1.0, 0.0, 0.0])
            writer.writerow(["P2", "2025-10-05T11:00:00Z", "out", 1.0, -20.0, -1.0, 0.0, 0.0])
        opens = root / f"{role}_open.csv"
        opens.write_text("position_id\n", encoding="utf-8")
        variants.append({
            "role": role,
            "run_id": f"synthetic-{role}",
            "observed_context": dict(context),
            "input_preset": preset.name,
            "report_path": report.name,
            "deals_csv": deals.name,
            "open_positions_csv": opens.name,
        })
    manifest = root / "matched-manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "synthetic-one-shot-oos-contract-test",
        "test_context": context,
        "dataset_path": dataset.name,
        "variants": variants,
    }, indent=2), encoding="utf-8")
    reservation = root / "reservation.json"
    reservation.write_text(json.dumps({
        "schema_version": 1,
        "reservation_id": "synthetic-test-reservation",
        "status": "reserved_unscored",
        "locked_oos_start": "2025-10-01T00:00:00Z",
        "locked_oos_end": "2025-12-01T00:00:00Z",
        "maturity_end": "2026-01-01T00:00:00Z",
        "external_freshness_attestation_required": True,
    }, indent=2), encoding="utf-8")
    freeze = root / "frozen-config.json"
    freeze.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "synthetic-one-shot-oos-contract-test",
        "frozen_at": "2026-10-13T00:00:00Z",
        "matched_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "point_value_per_lot": 1.0,
        "spread_widening_points": [0],
        "slippage_points_per_fill": [0],
        "simulations": 100,
        "seed": 12345,
        "train_months": 1,
        "test_months": 1,
        "folds": 1,
        "promotion_criteria": ["synthetic test contract only; never use as strategy performance evidence"],
        "oos_previously_inspected": False,
    }, indent=2), encoding="utf-8")
    return reservation, manifest, freeze


def test_one_shot_oos_requires_explicit_untouched_attestation(tmp_path):
    reservation, manifest, freeze = _make_fixture(tmp_path)
    with pytest.raises(LockedOOSGateError, match="--attest-untouched"):
        evaluate_once(reservation, manifest, freeze, tmp_path / "one-shot.lock", tmp_path / "report.json", attest_untouched=False)


def test_one_shot_oos_scores_both_variants_once_and_writes_consumption_lock(tmp_path):
    reservation, manifest, freeze = _make_fixture(tmp_path)
    lock = tmp_path / "one-shot.lock"
    output = tmp_path / "one-shot-report.json"
    result = evaluate_once(reservation, manifest, freeze, lock, output, attest_untouched=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    lock_payload = json.loads(lock.read_text(encoding="utf-8"))
    assert result["status"] == "consumed_evaluation_complete"
    assert lock_payload["status"] == "consumed_evaluation_complete"
    assert payload["one_shot"]["operator_untouched_attestation_required_and_received"] is True
    assert payload["matched_htf_trailing_comparison"]["variants"]["htf_trailing_off"]["locked_oos_cost_inclusive_metrics"]["completed_positions"] == 1
    assert len(payload["predeclared_cost_stress_and_monte_carlo"]["htf_trailing_off"]["locked_oos"]["cost_stress_monte_carlo"]) == 1


def test_consumed_oos_lock_prevents_a_second_evaluation(tmp_path):
    reservation, manifest, freeze = _make_fixture(tmp_path)
    lock = tmp_path / "one-shot.lock"
    output = tmp_path / "one-shot-report.json"
    evaluate_once(reservation, manifest, freeze, lock, output, attest_untouched=True)
    with pytest.raises(LockedOOSGateError, match="already been consumed"):
        evaluate_once(reservation, manifest, freeze, lock, tmp_path / "second-report.json", attest_untouched=True)


def test_freeze_hash_mismatch_is_rejected_before_consuming_lock(tmp_path):
    reservation, manifest, freeze = _make_fixture(tmp_path)
    data = json.loads(freeze.read_text(encoding="utf-8"))
    data["matched_manifest_sha256"] = "0" * 64
    freeze.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LockedOOSGateError, match="manifest changed after"):
        evaluate_once(reservation, manifest, freeze, tmp_path / "one-shot.lock", tmp_path / "report.json", attest_untouched=True)
