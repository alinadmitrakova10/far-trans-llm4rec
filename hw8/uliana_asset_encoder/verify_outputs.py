#!/usr/bin/env python3
"""Independently check saved inputs, vectors, rankings, and metrics for both HW8 branches."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def independent_ndcg(ids, truth):
    if not truth:
        return 0.0
    discounts = [math.log2(rank + 1) ** -1 for rank in range(1, 11)]
    return math.fsum(weight for item, weight in zip(ids, discounts) if item in truth) / math.fsum(discounts[:len(truth)])


def verify(root):
    frozen = read_json(root / "protocol.json")
    catalog = read_json(root / "catalog_inputs.json")
    users = read_json(root / "evaluation.json")
    manifest = read_json(root / "run_manifest.json")
    require(manifest["status"] == "complete" and not manifest["errors"], "Experiment failed")
    for source, expected in manifest["code_sha256"].items():
        observed = hashlib.sha256(Path(__file__).with_name(source).read_bytes()).hexdigest()
        require(observed == expected, f"Runnable code differs from recorded code: {source}")

    allowed = [row["ISIN"] for row in catalog]
    require(allowed == frozen["eligible_assets"] and len(allowed) == len(set(allowed)) == 767, "Catalog mismatch")
    require([u["user_id"] for u in users] == frozen["users"] and len(users) == 100, "User list mismatch")
    require(sum(bool(u["truth"]) for u in users) == 11 and frozen["exclude_seen"] is False, "Truth or seen policy mismatch")
    allowed_set = set(allowed)
    for row in users:
        for field in ("history", "truth"):
            require(set(row[field]) <= allowed_set and len(row[field]) == len(set(row[field])),
                    f"Unexpected {field} for {row['user_id']}")
        require(bool(row["history"]), "No history in warm cohort")

    columns = ["assetCategory", "assetSubCategory", "sector", "industry"]
    for asset in catalog:
        require(asset["metadata_date"] < frozen["cutoff"], f"Non-as-of snapshot for {asset['ISIN']}")
        require(list(asset["fields"]) == columns, f"Unexpected fields for {asset['ISIN']}")
        require(asset["text"].splitlines() == [f"{key}={asset['fields'][key]}" for key in columns],
                f"Noncanonical text for {asset['ISIN']}")
    texts = [asset["text"] for asset in catalog]
    documents = [text.splitlines() for text in texts]
    document_frequency = Counter(token for document in documents for token in set(document))
    vocabulary = {token: i for i, token in enumerate(sorted(document_frequency))}
    reference_tfidf = np.zeros((len(allowed), len(vocabulary)))
    for row, document in enumerate(documents):
        for token, count in Counter(document).items():
            reference_tfidf[row, vocabulary[token]] = count * (1 + math.log((1 + len(documents)) / (1 + document_frequency[token])))
    reference_tfidf /= np.linalg.norm(reference_tfidf, axis=1, keepdims=True)

    positions = {isin: i for i, isin in enumerate(allowed)}
    result = {"checked_by": "automated agent check", "protocol_hash": frozen["protocol_hash"], "methods": {}}
    all_scores = {}
    for method in ("tfidf", "qwen"):
        target = root / method
        vectors = np.load(target / "asset_vectors.npy", allow_pickle=False)
        require(vectors.shape[0] == 767 and np.isfinite(vectors).all(), "Invalid asset vectors")
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=0, atol=1e-14)
        if method == "tfidf":
            np.testing.assert_allclose(vectors, reference_tfidf, rtol=0, atol=1e-14)
        else:
            require(vectors.shape[1] == 1024, "Wrong model output dimension")
            by_text = {}
            for text, vector in zip(texts, vectors):
                np.testing.assert_array_equal(vector, by_text.setdefault(text, vector))
            require(len(np.unique(vectors, axis=0)) == len(by_text), "Different asset texts have identical vectors")

        saved_top = read_csv(target / "top10.csv")
        saved_metrics = read_csv(target / "per_user.csv")
        require(len(saved_top) == 1000 and len(saved_metrics) == 100, "Wrong saved output row count")
        scores = []
        for i, (user, row) in enumerate(zip(users, saved_metrics)):
            uid, truth = user["user_id"], set(user["truth"])
            rows = saved_top[10 * i:10 * (i + 1)]
            ids = [item["ISIN"] for item in rows]
            require(all(item["user_id"] == uid and int(item["rank"]) == rank for rank, item in enumerate(rows, 1)),
                    f"Prediction indexing error: {method} {uid}")
            require(len(set(ids)) == 10 and set(ids) <= allowed_set, f"Invalid Top-10: {method} {uid}")

            profile = vectors[[positions[isin] for isin in user["history"]]].sum(axis=0)
            similarity = np.clip((vectors * profile).sum(axis=1) / np.sqrt(np.square(profile).sum()), -1, 1)
            ranked = sorted(zip(allowed, similarity, catalog),
                            key=lambda item: (-round(float(item[1]), 12), -item[2]["historical_buyers"], item[0]))
            require(ids == [item[0] for item in ranked[:10]], f"Recomputed Top-10 mismatch: {method} {uid}")
            np.testing.assert_allclose([float(item["cosine"]) for item in rows],
                                       [value for _, value, _ in ranked[:10]], rtol=0, atol=1e-14)
            for item in rows:
                require(float(item["rank_score"]) == round(float(item["cosine"]), 12), "Wrong tie score")

            expected = independent_ndcg(ids, truth)
            require(row["user_id"] == uid and int(row["relevant_count"]) == len(truth), "Per-user coverage mismatch")
            require(math.isclose(float(row["ndcg_at_10"]), expected, rel_tol=0, abs_tol=1e-14), "Wrong per-user nDCG")
            scores.append(expected)
        all_mean = math.fsum(scores) / 100
        nonempty_mean = math.fsum(score for score, user in zip(scores, users) if user["truth"]) / 11
        summary = manifest["methods"][method]["metrics"]
        np.testing.assert_allclose([all_mean, nonempty_mean], [summary["ndcg_at_10"], summary["ndcg_at_10_nonempty"]],
                                   rtol=0, atol=1e-14)
        result["methods"][method] = {"top10_lists_checked": len(scores), "per_user_metrics_checked": len(scores),
                                     "ndcg_at_10": all_mean, "ndcg_at_10_nonempty": nonempty_mean}
        all_scores[method] = scores

    deltas = [qwen - control for qwen, control in zip(all_scores["qwen"], all_scores["tfidf"])]
    paired = manifest["paired_qwen_minus_tfidf"]
    np.testing.assert_allclose([math.fsum(deltas) / 100, math.fsum(deltas) / 11],
                               [paired["delta_all"], paired["delta_nonempty"]], rtol=0, atol=1e-14)
    require((sum(v > 0 for v in deltas), sum(v < 0 for v in deltas), deltas.count(0)) ==
            (paired["users_improved"], paired["users_declined"], paired["users_unchanged"]), "Wrong paired counts")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.run_directory), indent=2))
