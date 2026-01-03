from risk_decision.core.fingerprints import build_fingerprints


def test_fingerprints_are_stable():
    payload = {"a": 1, "b": 2}
    config = {"x": "y"}

    fp1 = build_fingerprints(payload=payload, config=config, model_ref="test")
    fp2 = build_fingerprints(payload=payload, config=config, model_ref="test")

    assert fp1["input_hash"] == fp2["input_hash"]
    assert fp1["config_hash"] == fp2["config_hash"]
    assert fp1["model_hash"] == "test"
