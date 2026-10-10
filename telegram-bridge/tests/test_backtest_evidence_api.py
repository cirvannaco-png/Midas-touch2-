from datetime import datetime, timedelta, timezone

import pytest


def _outcome(trade_id, timestamp, partition, index, fold_id=None):
    is_win = index % 5 != 0
    return {
        "trade_id": trade_id,
        "timestamp": timestamp.isoformat(),
        "partition": partition,
        "fold_id": fold_id,
        "outcome": "win" if is_win else "loss",
        "realized_r": 0.5 if is_win else -0.5,
        "filled": True,
        "commission_cost": 0.07,
        "spread_cost": 0.03,
        "slippage_cost": 0.02,
    }


def _valid_payload():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    trades = []
    fold_specs = (
        (1, 20, 21),
        (2, 30, 31),
        (3, 40, 41),
    )
    for fold_id, train_count, validation_start_day in fold_specs:
        for i in range(train_count):
            trades.append(_outcome(
                f"fold-{fold_id}-train-{i}",
                start + timedelta(days=i),
                "train", i, fold_id,
            ))
        for i in range(10):
            trades.append(_outcome(
                f"fold-{fold_id}-validation-{i}",
                start + timedelta(days=validation_start_day + i),
                "validation", i, fold_id,
            ))

    for i in range(30):
        trades.append(_outcome(
            f"holdout-{i}", start + timedelta(days=60 + i),
            "locked_oos", i, None,
        ))

    return {
        "strategy": "SMC",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "parameters": {"min_confidence": 60},
        "data_version": "xauusd-m15-2024-v1",
        "optimizer_version": "mt2-evidence-import-v1",
        "change_scope": "ENTRY",
        "provenance": {
            "source": "MT5_STRATEGY_TESTER",
            "run_id": "tester-run-valid-001",
            "report_sha256": "a" * 64,
            "dataset_sha256": "b" * 64,
            "ea_source_commit": "c" * 40,
            "ea_build": "MidasTouch-test-build",
            "terminal_build": "MT5-test-terminal",
            "data_vendor": "fixture-only",
            "period_start": start.isoformat(),
            "period_end": (start + timedelta(days=100)).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "spread_model": "fixed-spread",
            "spread_points": 20,
            "commission_per_lot": 7,
            "slippage_points": 2,
            "fill_policy": "FILL_CONSERVATIVE",
        },
        "trades": trades,
        "parameter_neighbors": [{
            "parameters": {"min_confidence": 61},
            "report_sha256": "d" * 64,
            "dataset_sha256": "b" * 64,
            "ea_source_commit": "c" * 40,
            "ea_build": "MidasTouch-test-build",
            "terminal_build": "MT5-test-terminal",
            "period_start": start.isoformat(),
            "period_end": (start + timedelta(days=100)).isoformat(),
            "trades": [{
                "trade_id": f"neighbor-holdout-{i}",
                "timestamp": (start + timedelta(days=60 + i)).isoformat(),
                "outcome": "win" if i % 5 != 0 else "loss",
                "realized_r": 0.5 if i % 5 != 0 else -0.5,
            } for i in range(30)],
        }],
        "feature_importance": [{
            "feature": "liquidity_sweep",
            "delta_metric": 0.04,
        }],
        "clustered_mda": [{
            "group_name": "liquidity_structure",
            "features": ["liquidity_sweep", "bos_confirmation"],
            "delta_metric": 0.03,
        }],
        "counterfactual": [{
            "scenario_id": f"scenario-{i}",
            "baseline_realized_r": 0.2,
            "candidate_realized_r": 0.3,
        } for i in range(30)],
        "paired_test_p_value": 0.02,
        "scale_out": [],
    }


def test_backtest_evidence_ingestion_requires_api_key(client):
    response = client.post("/research/backtest-evidence", json=_valid_payload())
    assert response.status_code in (401, 403)


def test_backtest_evidence_is_persisted_but_never_activated(client, auth_headers):
    payload = _valid_payload()
    response = client.post(
        "/research/backtest-evidence",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "stored"
    assert body["decision"] == "VALIDATED"
    assert body["lifecycle_status"] == "VALIDATED"
    assert body["locked_oos"]["resolved_trades"] == 30
    assert body["walk_forward_verdicts"] == ["consistent", "consistent", "consistent"]
    assert "not activated" in body["promotion_boundary"]

    # A validated research candidate is not a Champion and cannot be served
    # through the production configuration-sync endpoint.
    config_response = client.get("/config/XAUUSD", headers=auth_headers)
    assert config_response.status_code == 404


def test_backtest_evidence_ingestion_rejects_duplicate_run_id(client, auth_headers):
    payload = _valid_payload()
    first = client.post("/research/backtest-evidence", headers=auth_headers, json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/research/backtest-evidence", headers=auth_headers, json=payload)
    assert second.status_code == 409
    assert "already been ingested" in second.json()["detail"]


def test_backtest_evidence_rejects_locked_oos_before_validation(client, auth_headers):
    payload = _valid_payload()
    payload["trades"][-1]["timestamp"] = (
        datetime.fromisoformat(payload["provenance"]["period_start"])
        + timedelta(days=45)
    ).isoformat()
    response = client.post(
        "/research/backtest-evidence",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 422
    assert "locked_oos must start after" in response.json()["detail"]


def test_backtest_evidence_requires_three_walk_forward_folds(client, auth_headers):
    payload = _valid_payload()
    payload["trades"] = [
        row for row in payload["trades"]
        if row["fold_id"] != 3 or row["partition"] == "locked_oos"
    ]
    response = client.post(
        "/research/backtest-evidence",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 422
    assert "at least 3 walk-forward folds" in response.json()["detail"]


@pytest.mark.parametrize(
    "partition,outcome,realized_r,filled",
    [
        ("train", "win", -0.5, True),
        ("train", "no_fill", 0.0, False),
        ("locked_oos", "win", -0.5, True),
    ],
)
def test_trade_schema_rejects_inconsistent_outcome_contract(
    partition, outcome, realized_r, filled
):
    from app.api.backtest_evidence import TesterTrade
    from pydantic import ValidationError

    data = {
        "trade_id": "bad-row",
        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "partition": partition,
        "fold_id": 1 if partition == "train" else None,
        "outcome": outcome,
        "realized_r": realized_r,
        "filled": filled,
        "commission_cost": 0.1 if filled else None,
        "spread_cost": 0.1 if filled else None,
        "slippage_cost": 0.1 if filled else None,
    }
    with pytest.raises(ValidationError):
        TesterTrade.model_validate(data)
