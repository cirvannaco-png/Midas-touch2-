from tools.research.feature_importance import permutation_importance


def test_permutation_importance_identifies_predictive_feature():
    rows = [
        {"structure": 0.0, "noise": 0.0},
        {"structure": 1.0, "noise": 0.2},
        {"structure": 2.0, "noise": -0.1},
        {"structure": 3.0, "noise": 0.5},
        {"structure": 4.0, "noise": 0.1},
        {"structure": 5.0, "noise": -0.3},
    ]
    targets = [row["structure"] * 2.0 for row in rows]

    def predictor(features):
        return features["structure"] * 2.0

    def score(y_true, y_pred):
        return -sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / len(y_true)

    report = permutation_importance(
        rows, targets, ["structure", "noise"], predictor=predictor,
        scorer=score, repetitions=12, seed=7
    )
    ranked = report.ranked()
    assert ranked[0].feature == "structure"
    assert ranked[0].importance > ranked[1].importance
    assert ranked[0].importance > 0.0
