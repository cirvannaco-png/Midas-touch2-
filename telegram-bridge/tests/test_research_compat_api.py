from app.api.research_compat import canonical_hash
from app.canonical_config import canonical_json
import pytest


def experiment_payload(experiment_id: str) -> dict:
    return {
        "experiment_id": experiment_id,
        "name": "Compatibility API test",
        "code_sha": "abcdef1234567",
        "config": {"risk": 0.5, "filter": "volatility"},
        "data_snapshot": "test-data-snapshot-v1",
        "train_start": "2025-01-01T00:00:00Z",
        "train_end": "2025-06-30T23:59:59Z",
        "oos_start": "2025-07-01T00:00:00Z",
        "oos_end": "2025-12-31T23:59:59Z",
        "walk_forward_id": "wf-test-1",
    }


def create_experiment(client, auth_headers, experiment_id: str) -> dict:
    response = client.post(
        "/research/experiments",
        json=experiment_payload(experiment_id),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_experiment_creation_preserves_config_hash_and_rejects_duplicates(client, auth_headers):
    payload = experiment_payload("research-api-create-test")
    response = client.post("/research/experiments", json=payload, headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["config_hash"] == canonical_hash(payload["config"])
    assert body["holdout_locked"] is False

    duplicate = client.post("/research/experiments", json=payload, headers=auth_headers)
    assert duplicate.status_code == 409


def test_experiment_rejects_overlapping_training_and_oos_windows(client, auth_headers):
    payload = experiment_payload("research-api-invalid-chronology")
    payload["oos_start"] = "2025-06-01T00:00:00Z"
    response = client.post("/research/experiments", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_observation_ingestion_is_fingerprint_idempotent(client, auth_headers):
    experiment_id = "research-api-observation-test"
    create_experiment(client, auth_headers, experiment_id)
    payload = {
        "signal_id": "signal-observation-1",
        "symbol": "EURUSD",
        "timestamp": "2025-10-01T10:00:00Z",
        "payload": {"realized_r": 0.75, "source": "backtest"},
    }
    url = f"/research/experiments/{experiment_id}/observations"
    first = client.post(url, json=payload, headers=auth_headers)
    second = client.post(url, json=payload, headers=auth_headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["fingerprint"] == second.json()["fingerprint"]
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


def test_holdout_lock_is_one_way_and_validation_does_not_promote(client, auth_headers):
    experiment_id = "research-api-holdout-test"
    create_experiment(client, auth_headers, experiment_id)
    url = f"/research/experiments/{experiment_id}/holdout-lock"
    locked = client.post(url, headers=auth_headers)
    assert locked.status_code == 200, locked.text
    assert locked.json()["holdout_locked"] is True
    repeated = client.post(url, headers=auth_headers)
    assert repeated.status_code == 200
    assert repeated.json()["already_locked"] is True

    validation = client.post(
        f"/research/experiments/{experiment_id}/validation-runs",
        json={
            "validation_type": "walk_forward",
            "window": {"start": "2025-07-01", "end": "2025-12-31"},
            "metrics": {"expectancy_r": 0.12, "profit_factor": 1.4},
            "passed": True,
        },
        headers=auth_headers,
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["promoted"] is False


def test_research_api_requires_authentication(client):
    response = client.post(
        "/research/experiments",
        json=experiment_payload("research-api-auth-test"),
    )
    assert response.status_code == 422



def test_canonical_config_hash_matches_source_float_and_unicode_normalization():
    value = {"b": 1.2345678901234567, "a": "café"}
    assert canonical_json(value) == '{"a":"caf\\u00e9","b":1.23456789012346}'
    assert canonical_hash(value) == canonical_hash({"a": "café", "b": 1.2345678901234567})


def test_canonical_config_hash_rejects_non_finite_numbers():
    with pytest.raises(ValueError, match="non-finite"):
        canonical_hash({"risk": float("nan")})
