from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.risk_trailing_experiment import ExperimentError, compare_manifest

ROLES = (
    "A_current_baseline", "B_trailing_off", "C_trailing_candidate",
    "D_tight_risk", "E_calibrated_risk",
)


def _base_preset() -> dict[str, str]:
    return {
        "InpRiskPercentPerTrade": "0.5", "InpMaxOpenTrades": "3",
        "InpMaxDailyLossPercent": "3", "InpMaxDrawdownPercent": "10",
        "InpDeriskStartPercent": "5", "InpDeriskFloor": "0.25",
        "InpMaxPortfolioRiskPercent": "3", "InpMaxPositionsPerSymbol": "3",
        "InpMaxPositionsPerGroup": "3", "InpEnableDynamicStop": "true",
        "InpDynamicStopActivateAtR": "0.75", "InpDynamicStopBreakevenAtR": "1",
        "InpDynamicStopATRMult": "1.5", "InpDynamicStopMinImprovementPoints": "2",
        "InpDynamicStopMaxSpreadPoints": "0", "InpDynamicStopMinATR": "0",
        "InpDynamicStopMaxATR": "0", "InpDynamicStopModifyIntervalSec": "5",
        "InpDynamicStopUseStructuralAnchor": "true", "InpDynamicStopStructuralBufferATR": "0.1",
        "InpBreakEvenAtR": "1", "InpPartialAtR": "2", "InpPartialFraction": "0.5",
        "InpTrailATRMult": "1.5", "InpSimCommissionPerLot": "7",
        "InpSimSpreadPoints": "10", "InpSimSlippagePoints": "2",
        "InpEnableExecution": "true", "InpMinRiskReward": "1.5",
    }


def _context(dataset_hash: str) -> dict:
    return {
        "account_profile": "small_account", "symbol": "XAUUSD", "timeframe": "M5",
        "period_start": "2025-01-01T00:00:00Z", "period_end": "2025-04-01T00:00:00Z",
        "locked_oos_start": "2025-02-01T00:00:00Z", "locked_oos_end": "2025-03-01T00:00:00Z",
        "dataset_sha256": dataset_hash, "ea_source_sha": "a" * 40,
        "ea_build": "build-1", "terminal_build": "terminal-1", "data_vendor": "Exness",
        "spread_model": "real_ticks_plus_stress", "spread_widening_multiplier": 1.5,
        "spread_points": None, "commission_per_lot": 7.0, "slippage_points": 2.0,
        "swap_included": True, "fill_policy": "real_ticks", "costs_applied_in_tester": True,
        "initial_balance": 10000.0, "account_currency": "USD", "leverage": "1:500",
    }


def _write_deals(path: Path, profits=(120.0, -60.0, 90.0, -15.0)) -> None:
    fields = ["position_id", "time", "entry", "volume", "profit", "commission", "swap", "fee", "risk_cash"]
    schedule = [
        ("P1", "2025-01-05T10:00:00Z", "in", 0.0, -3.5, 0.0, 0.0, 100.0),
        ("P1", "2025-01-05T11:00:00Z", "out", profits[0], -3.5, 0.0, 0.0, 0.0),
        ("P2", "2025-02-05T10:00:00Z", "in", 0.0, -3.5, 0.0, 0.0, 100.0),
        ("P2", "2025-02-06T11:00:00Z", "out", profits[1], -3.5, -0.5, 0.0, 0.0),
        ("P3", "2025-02-12T10:00:00Z", "in", 0.0, -3.5, 0.0, 0.0, 100.0),
        ("P3", "2025-02-13T11:00:00Z", "out", profits[2], -3.5, 0.0, 0.0, 0.0),
        ("P4", "2025-03-10T10:00:00Z", "in", 0.0, -3.5, 0.0, 0.0, 100.0),
        ("P4", "2025-03-11T11:00:00Z", "out", profits[3], -3.5, -1.0, 0.0, 0.0),
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        for row in schedule:
            pid, time, entry, profit, commission, swap, fee, risk_cash = row
            writer.writerow([pid, time, entry, 1.0, profit, commission, swap, fee, risk_cash])


def _manifest(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dataset = folder / "ticks.bin"
    dataset.write_bytes(b"immutable test tick data")
    context = _context(hashlib.sha256(dataset.read_bytes()).hexdigest())
    presets = {role: _base_preset() for role in ROLES}
    presets["B_trailing_off"]["InpEnableDynamicStop"] = "false"
    presets["C_trailing_candidate"]["InpDynamicStopATRMult"] = "1.75"
    presets["D_tight_risk"].update({
        "InpRiskPercentPerTrade": "0.35", "InpMaxOpenTrades": "2",
        "InpMaxDailyLossPercent": "2", "InpMaxDrawdownPercent": "8",
        "InpDeriskStartPercent": "3", "InpDeriskFloor": "0.15",
        "InpMaxPortfolioRiskPercent": "1.5", "InpMaxPositionsPerSymbol": "2",
        "InpMaxPositionsPerGroup": "2",
    })
    presets["E_calibrated_risk"].update({
        "InpRiskPercentPerTrade": "0.45", "InpMaxDailyLossPercent": "2.5",
        "InpMaxDrawdownPercent": "9", "InpDeriskStartPercent": "4",
        "InpDeriskFloor": "0.2", "InpMaxPortfolioRiskPercent": "2.5",
    })
    variants = []
    for i, role in enumerate(ROLES):
        preset = folder / f"{role}.set"
        preset.write_text("".join(f"{k}={v}\n" for k, v in presets[role].items()), encoding="utf-8")
        report = folder / f"{role}.html"
        report.write_text(f"tester report {role}", encoding="utf-8")
        deals = folder / f"{role}.csv"
        _write_deals(deals)
        opened = folder / f"{role}-open.csv"
        opened.write_text("position_id\n", encoding="utf-8")
        variants.append({
            "role": role, "run_id": f"tester-{i}", "observed_context": dict(context),
            "input_preset": preset.name, "report_path": report.name,
            "deals_csv": deals.name, "open_positions_csv": opened.name,
        })
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "experiment_id": "risk-trailing-test",
        "dataset_path": dataset.name, "test_context": context, "variants": variants,
    }), encoding="utf-8")
    return manifest


def test_matched_cost_inclusive_five_arm_report_is_reproducible(tmp_path):
    manifest = _manifest(tmp_path)
    report, summary = compare_manifest(manifest, simulations=100, seed=123)
    assert summary["matched_context_verified"] is True
    assert report["promotion_recommendation"] is None
    assert report["variants"]["A_current_baseline"]["full_period"]["completed_positions"] == 4
    assert report["variants"]["A_current_baseline"]["locked_oos"]["completed_positions"] == 2
    assert report["variants"]["A_current_baseline"]["full_period"]["net_pnl"] == pytest.approx(105.5)
    first = report["variants"]["A_current_baseline"]["locked_oos"]["monte_carlo_trade_order_drawdown"]
    again, _ = compare_manifest(manifest, simulations=100, seed=123)
    assert first == again["variants"]["A_current_baseline"]["locked_oos"]["monte_carlo_trade_order_drawdown"]


def test_dataset_digest_mismatch_is_rejected(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    payload["test_context"]["dataset_sha256"] = "0" * 64
    path.write_text(json.dumps(payload))
    with pytest.raises(ExperimentError, match="dataset SHA-256"):
        compare_manifest(path, simulations=10)


def test_outcome_context_mismatch_is_rejected(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    payload["variants"][2]["observed_context"]["slippage_points"] = 3.0
    path.write_text(json.dumps(payload))
    with pytest.raises(ExperimentError, match="context differs"):
        compare_manifest(path, simulations=10)


def test_risk_and_trailing_ablation_must_be_isolated(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    preset = tmp_path / payload["variants"][1]["input_preset"]
    preset.write_text(preset.read_text().replace("InpMinRiskReward=1.5", "InpMinRiskReward=1.2"))
    path.write_text(json.dumps(payload))
    with pytest.raises(ExperimentError, match="changes non-risk/trailing settings"):
        compare_manifest(path, simulations=10)


def test_missing_role_is_rejected(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text())
    payload["variants"] = payload["variants"][:-1]
    path.write_text(json.dumps(payload))
    with pytest.raises(ExperimentError, match="missing required experiment roles"):
        compare_manifest(path, simulations=10)
