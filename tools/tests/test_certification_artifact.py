from tools.certification_artifact import build_certificate


def test_certificate_contains_hash_and_insufficient_evidence_by_default():
    artifact = build_certificate(
        build={"commit": "abc"},
        ea={"version": "x"},
        decision_schema={"version": "decision-v1"},
        dataset={"id": "ds1"},
        training={"status": "PASS"},
        validation={"status": "PASS"},
        oos={"status": "INSUFFICIENT_EVIDENCE"},
        trades={},
        costs={},
        metrics={},
        gates={"parity": "PASS", "temporal_isolation": "PASS", "replay_determinism": "PASS", "data_provenance": "PASS"},
    )
    assert artifact["certificate_hash"]
    assert artifact["certification"] == "INSUFFICIENT_EVIDENCE"
