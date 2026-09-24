from tools.research.clustered_mda import build_feature_clusters, clustered_permutation_importance


def test_cluster_builder_groups_correlated_evidence():
    rows = [
        {"bos": 1.0, "impulse": 2.0, "trend": 0.0},
        {"bos": 2.0, "impulse": 4.0, "trend": 2.0},
        {"bos": 3.0, "impulse": 6.0, "trend": -1.0},
        {"bos": 4.0, "impulse": 8.0, "trend": 1.0},
    ]
    clusters = build_feature_clusters(
        rows, ["bos", "impulse", "trend"], correlation_threshold=0.95
    )
    assert any(set(cluster.features) == {"bos", "impulse"} for cluster in clusters)


def test_clustered_mda_has_positive_group_importance():
    rows = [
        {"bos": 1.0, "impulse": 2.0, "noise": 0.0},
        {"bos": 2.0, "impulse": 4.0, "noise": 1.0},
        {"bos": 3.0, "impulse": 6.0, "noise": -1.0},
        {"bos": 4.0, "impulse": 8.0, "noise": 2.0},
        {"bos": 5.0, "impulse": 10.0, "noise": -2.0},
    ]
    targets = [row["bos"] + row["impulse"] for row in rows]

    def predictor(features):
        return features["bos"] + features["impulse"]

    def score(y_true, y_pred):
        return -sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / len(y_true)

    report = clustered_permutation_importance(
        rows, targets, feature_names=["bos", "impulse", "noise"],
        predictor=predictor, scorer=score,
        correlation_threshold=0.9, repetitions=8, seed=4
    )
    combined = next(
        item for item in report.clusters
        if set(item.cluster.features) == {"bos", "impulse"}
    )
    assert combined.importance > 0.0
