from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.audit_mt5_diagnostic_parity import AuditError, audit_manifest


def _write_csv(path: Path, fields: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def _manifest(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dataset = folder / "ticks.zip"
    dataset.write_bytes(b"immutable tick archive fixture")
    context = {
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2025-04-01T00:00:00Z",
        "locked_oos_start": "2025-02-01T00:00:00Z",
        "locked_oos_end": "2025-03-01T00:00:00Z",
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "ea_source_sha": "a" * 40,
        "ea_build": "candidate-build-1",
        "terminal_build": "mt5-build-1",
        "data_vendor": "Exness",
        "tester_model": "Every tick based on real ticks",
        "spread_model": "real_ticks_plus_stress",
        "spread_widening_multiplier": 1.2,
        "spread_points": None,
        "baseline_spread_points": 15,
        "cash_per_point_per_lot": 0.1,
        "commission_per_lot": 7,
        "slippage_points": 2,
        "swap_included": True,
        "base_costs_applied_in_tester": True,
        "stress_costs_applied_in_analysis": True,
        "fill_policy": "real_ticks",
        "initial_balance": 10000,
        "account_currency": "USD",
        "leverage": "1:500",
        "diagnostic_input": "InpDiagnosticsMode",
        "diagnostic_off_value": "false",
        "diagnostic_on_value": "true",
    }
    observed = {k: v for k, v in context.items() if k not in {"diagnostic_off_value", "diagnostic_on_value"}}
    runs = []
    for role, enabled, decision_id, diagnostic_score in (
        ("diagnostic_off", "false", "D-OFF-1", "0"),
        ("diagnostic_on", "true", "D-ON-1", "0.8"),
    ):
        preset = folder / f"{role}.set"
        preset.write_text(
            f"InpDiagnosticsMode={enabled}||{enabled}||false||true||N\n"
            "InpRiskPercentPerTrade=0.5||0.5||0.1||1||N\n",
            encoding="utf-8",
        )
        report = folder / f"{role}.html"
        report.write_text("<html><body>MT5 Strategy Tester report</body></html>", encoding="utf-8")
        log = folder / f"{role}.log"
        log.write_text(
            "MT5 Strategy Tester started\n"
            "Symbol: XAUUSD\n"
            "Modeling: Every tick based on real ticks\n"
            "Historical tick data synchronized; symbol specification loaded\n",
            encoding="utf-8",
        )
        signals = folder / f"{role}-signals.csv"
        _write_csv(
            signals,
            ["SignalID", "Symbol", "EntryTF", "DateTime", "Direction", "Confidence",
             "ContradictionPenalty", "EnvScore", "ExecScore", "EnvExecConfidence", "SelectedStrategy"],
            [["S-1", "XAUUSD", "PERIOD_M5", "2025.01.06 10:00", "BUY", "80",
              diagnostic_score, diagnostic_score, diagnostic_score, diagnostic_score, "SMC"]],
        )
        outcomes = folder / f"{role}-outcomes.csv"
        _write_csv(
            outcomes,
            ["SignalID", "OutcomeEpoch", "Outcome", "Filled", "RealizedNetPnL", "RealizedR",
             "Commission", "SpreadCost", "SlippageCost"],
            [["S-1", "1736164800", "TP1_Hit", "Yes", "10", "1", "0.7", "0.2", "0.1"]],
        )
        decisions = folder / f"{role}-decisions.csv"
        _write_csv(
            decisions,
            ["SignalID", "DecisionID", "Decision", "SelectedStrategy", "Direction",
             "ExecutionAuthorized", "DecisionTime"],
            [["S-1", decision_id, "APPROVE", "SMC", "BUY", "Yes", "2025.01.06 10:00"]],
        )
        deals = folder / f"{role}-deals.csv"
        _write_csv(
            deals,
            ["Ticket", "Position_ID", "Time", "Entry", "Volume", "Profit", "Commission", "Swap", "Fee"],
            [
                ["1001", "P-1", "2025.01.06 10:00:01", "in", "0.1", "0", "-0.35", "0", "0"],
                ["1002", "P-1", "2025.01.06 11:00:01", "out", "0.1", "10", "-0.35", "0", "0"],
            ],
        )
        opened = folder / f"{role}-open.csv"
        opened.write_text("position_id\n", encoding="utf-8")
        runs.append({
            "role": role,
            "run_id": f"run-{role}",
            "observed_context": observed,
            "input_preset": preset.name,
            "tester_report": report.name,
            "tester_log": log.name,
            "signals_csv": signals.name,
            "outcomes_csv": outcomes.name,
            "decisions_csv": decisions.name,
            "deals_csv": deals.name,
            "open_positions_csv": opened.name,
        })
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "experiment_id": "diagnostic-mode-fixture-test",
        "dataset_path": dataset.name,
        "test_context": context,
        "runs": runs,
    }), encoding="utf-8")
    return manifest


def test_identical_decision_path_ignores_only_declared_diagnostic_fields(tmp_path):
    report, code = audit_manifest(_manifest(tmp_path))
    assert code == 0
    assert report["status"] == "diagnostic_parity_verified_not_performance_certified"
    assert report["promotion_eligible"] is False
    assert report["matched_preset_check"]["other_inputs_identical"] is True
    assert report["parity"]["signals"]["field_parity"] is True
    assert report["parity"]["decisions"]["field_parity"] is True
    assert report["parity"]["outcomes"]["field_parity"] is True
    assert report["run_coverage"]["diagnostic_off"]["decision_attribution_coverage_pct"] == 100
    assert report["run_coverage"]["diagnostic_off"]["cost_ledger"]["cost_fields_explicit_and_finite"] is True


def test_behavioral_decision_change_blocks_parity(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    decision_file = tmp_path / payload["runs"][1]["decisions_csv"]
    rows = list(csv.DictReader(decision_file.open(encoding="utf-8")))
    rows[0]["Decision"] = "BLOCK"
    with decision_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    report, code = audit_manifest(path)
    assert code == 1
    assert report["status"] == "blocked"
    assert report["promotion_eligible"] is False
    assert any("decision parity differs" in item for item in report["blockers"])


def test_math_mode_log_blocks_real_market_data_claim(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    log = tmp_path / payload["runs"][0]["tester_log"]
    log.write_text(
        "Symbol: XAUUSD\nMathematical test mode, no market history and no symbol information\n",
        encoding="utf-8",
    )
    report, code = audit_manifest(path)
    assert code == 1
    assert report["status"] == "blocked"
    assert report["market_data_log_check"]["status"] == "blocked"
    assert any("mathematical test mode" in item for item in report["blockers"])


@pytest.mark.parametrize("field", ["Commission", "Swap", "Fee"])
def test_missing_explicit_deal_cost_is_rejected_not_defaulted_to_zero(tmp_path, field):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    deals = tmp_path / payload["runs"][0]["deals_csv"]
    with deals.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
        headers = list(rows[0].keys())
    rows[0][field] = ""
    with deals.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(AuditError, match=f"deals row 2.{field.lower()}"):
        audit_manifest(path)


def test_extra_changed_input_is_rejected(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    preset = tmp_path / payload["runs"][1]["input_preset"]
    preset.write_text(
        "InpDiagnosticsMode=true||true||false||true||N\n"
        "InpRiskPercentPerTrade=0.75||0.5||0.1||1||N\n",
        encoding="utf-8",
    )
    with pytest.raises(AuditError, match="differ in additional inputs"):
        audit_manifest(path)


def test_missing_decision_record_is_a_blocker_not_perfect_coverage(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    decisions = tmp_path / payload["runs"][0]["decisions_csv"]
    decisions.write_text(
        "SignalID,DecisionID,Decision,SelectedStrategy,Direction,ExecutionAuthorized,DecisionTime\n",
        encoding="utf-8",
    )
    report, code = audit_manifest(path)
    assert code == 1
    assert report["run_coverage"]["diagnostic_off"]["decision_attribution_coverage_pct"] == 0
    assert any("without a final decision record" in item for item in report["blockers"])


def test_open_position_csv_can_be_header_only(tmp_path):
    report, code = audit_manifest(_manifest(tmp_path))
    assert code == 0
    assert report["run_coverage"]["diagnostic_off"]["open_position_ids"] == []
