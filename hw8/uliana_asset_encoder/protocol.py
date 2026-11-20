"""Read the frozen teaching protocol and reconstruct inputs from FAR-Trans."""

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from zipfile import ZipFile


PROTOCOL_HASH = "50efd4aeb415ba6f0c66dd0793a7c2033cdc32a42b86b58eebbca3e81eaf3417"
FIELDS = ("assetCategory", "assetSubCategory", "sector", "industry")
MISSING = "[MISSING]"
BASELINES = {
    "popularity": "Popularity",
    "cbf": "CBF (стартер)",
    "latest_buy": "Latest buy",
    "latest_buy_or_sell": "Latest buy or sell",
}


def rows(archive, member):
    with io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_bundle(archive):
    files = ("protocol.json", "metrics.json", "predictions.csv", "per_user.csv", "runtime.json", "commit.txt")
    manifest = json.loads(archive.read("SHA256.json"))
    for name in files:
        if hashlib.sha256(archive.read(name)).hexdigest() != manifest[name]:
            raise ValueError(f"Alina bundle member hash mismatch: {name}")
    protocol = json.loads(archive.read("protocol.json"))
    contents = {key: value for key, value in protocol.items() if key != "protocol_hash"}
    if hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest() != PROTOCOL_HASH:
        raise ValueError("Unexpected teaching protocol contents")
    if protocol["protocol_hash"] != PROTOCOL_HASH:
        raise ValueError("Unexpected teaching protocol sha256 label")
    return protocol, {name: manifest[name] for name in files}


def clean_field(value):
    value = value.strip()
    return MISSING if value.casefold() in {"", "not_available", "nan"} else value


def load_catalog(archive, cutoff, allowed_ids):
    snapshots = defaultdict(list)
    for row in rows(archive, "FAR-Trans/asset_information.csv"):
        if row["timestamp"][:10] < cutoff:
            snapshots[row["ISIN"]].append(row)
    priced = {row["ISIN"] for row in rows(archive, "FAR-Trans/close_prices.csv")
              if row["timestamp"][:10] < cutoff and float(row["closePrice"]) > 0}
    if snapshots.keys() & priced != set(allowed_ids):
        raise ValueError("Source-derived catalog disagrees with the frozen eligible asset list")
    catalog = []
    for isin in allowed_ids:
        date = max(row["timestamp"][:10] for row in snapshots[isin])
        latest = [row for row in snapshots[isin] if row["timestamp"][:10] == date]
        values, conflicts = {}, []
        for field in FIELDS:
            observed = {clean_field(row[field]) for row in latest}
            if len(observed) == 1:
                values[field] = observed.pop()
            else:
                conflicts.append(field)
                values[field] = MISSING
        text = "\n".join(f"{field}={values[field]}" for field in FIELDS)
        catalog.append({"ISIN": isin, "metadata_date": date, "fields": values,
                        "conflicting_fields": conflicts, "text": text})
    return catalog


def load_data(archive, protocol):
    for name, expected in protocol["source_sha256"].items():
        with archive.open(f"FAR-Trans/{name}") as stream:
            observed = hashlib.file_digest(stream, "sha256").hexdigest()
        if observed != expected:
            raise ValueError(f"FAR-Trans source hash mismatch: {name}")

    cutoff, end = protocol["cutoff"], protocol["end_exclusive"]
    users, allowed = set(protocol["users"]), set(protocol["eligible_assets"])
    if len(users) != len(protocol["users"]) or len(allowed) != len(protocol["eligible_assets"]):
        raise ValueError("Frozen protocol contains duplicate IDs")
    catalog = load_catalog(archive, cutoff, protocol["eligible_assets"])
    history, truth = defaultdict(set), defaultdict(set)
    seen = set()
    excluded = {"exact_duplicate_rows": 0, "reconstructed_initial_position_rows": 0}
    for row in rows(archive, "FAR-Trans/transactions.csv"):
        # DictReader preserves header order. Include every column in the exact-row key.
        key = tuple(row.values())
        if key in seen:
            excluded["exact_duplicate_rows"] += 1
            continue
        seen.add(key)
        if int(row["transactionID"]) < 0:
            excluded["reconstructed_initial_position_rows"] += 1
            continue
        isin, uid, date = row["ISIN"], row["customerID"], row["timestamp"][:10]
        if row["transactionType"] != "Buy" or isin not in allowed:
            continue
        if date < cutoff:
            history[uid].add(isin)
        elif date < end and uid in users:
            truth[uid].add(isin)

    # Popularity is the number of distinct historical buyers in the full data.
    buyers = Counter(isin for assets in history.values() for isin in assets)
    for asset in catalog:
        asset["historical_buyers"] = buyers[asset["ISIN"]]
    evaluation = [{"user_id": uid, "history": sorted(history[uid]), "truth": sorted(truth[uid])}
                  for uid in protocol["users"]]
    if any(not user["history"] for user in evaluation) or sum(bool(u["truth"]) for u in evaluation) != 11:
        raise ValueError("Unexpected warm-user history or truth count for this protocol")
    return catalog, evaluation, excluded


def ndcg(ranking, truth, k):
    if not truth:
        return 0.0
    dcg = sum(1 / math.log2(rank + 1) for rank, isin in enumerate(ranking[:k], 1) if isin in truth)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(truth)) + 1))
    return dcg / ideal


def aggregate(records):
    nonempty = [r["ndcg_at_10"] for r in records if r["relevant_count"]]
    return {
        "users": len(records),
        "nonempty_truth_users": len(nonempty),
        "empty_truth_users": len(records) - len(nonempty),
        "ndcg_at_10": math.fsum(r["ndcg_at_10"] for r in records) / len(records),
        "ndcg_at_10_nonempty": math.fsum(nonempty) / len(nonempty),
    }


def validate_baselines(archive, protocol, evaluation):
    """Check saved lists and their metrics; never execute or rerank a baseline."""
    saved = json.loads(archive.read("metrics.json"))
    if saved["protocol_hash"] != PROTOCOL_HASH or set(saved["methods"]) != BASELINES.keys():
        raise ValueError("Baseline metrics do not match this protocol and method set")
    rankings = defaultdict(list)
    for row in rows(archive, "predictions.csv"):
        rankings[row["method"], row["user_id"]].append((int(row["rank"]), row["ISIN"]))
    user_metrics = {}
    for row in rows(archive, "per_user.csv"):
        key = row["method"], row["user_id"]
        if key in user_metrics:
            raise ValueError(f"Duplicate saved per-user metric: {key}")
        user_metrics[key] = int(row["relevant_count"]), float(row["ndcg_at_10"])
    expected_keys = {(method, uid) for method in BASELINES for uid in protocol["users"]}
    if rankings.keys() != expected_keys or user_metrics.keys() != expected_keys:
        raise ValueError("Incomplete baseline coverage")

    allowed, k = set(protocol["eligible_assets"]), protocol["k"]
    for method in BASELINES:
        results = []
        for user in evaluation:
            key = method, user["user_id"]
            ranks, ids = zip(*sorted(rankings[key]))
            if ranks != tuple(range(1, k + 1)) or len(set(ids)) != k or not set(ids) <= allowed:
                raise ValueError(f"Invalid saved baseline ranking: {key}")
            truth = set(user["truth"])
            score = ndcg(ids, truth, k)
            relevant_count, saved_score = user_metrics[key]
            if len(truth) != relevant_count or not math.isclose(score, saved_score, rel_tol=0, abs_tol=1e-14):
                raise ValueError(f"Inconsistent saved baseline per-user metric: {key}")
            results.append({"relevant_count": len(truth), "ndcg_at_10": score})
        for field, value in aggregate(results).items():
            if not math.isclose(saved["methods"][method][field], value, rel_tol=0, abs_tol=1e-14):
                raise ValueError(f"Inconsistent saved baseline aggregate: {method} {field}")
    return saved["methods"], json.loads(archive.read("runtime.json")), archive.read("commit.txt").decode().strip()
