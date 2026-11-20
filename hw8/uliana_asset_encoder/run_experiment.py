#!/usr/bin/env python3
"""Compare two frozen-catalog retrieval encoders on the Team 5 teaching protocol."""

import argparse
import csv
import json
import os
import platform
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

import numpy as np

from protocol import (BASELINES, FIELDS, MISSING, aggregate, file_hash, load_data,
                      ndcg, read_bundle, validate_baselines)


MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
MODEL_FILES = {
    "config.json": "b5bf1f51fc45be473a54718cef92448d90a1be001bf9b9a44b8c7f10a19feaa9",
    "tokenizer.json": "def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a",
    "tokenizer_config.json": "253153d0738ceb4c668d2eff957714dd2bea0b56de772a9fdccd96cbf517e6a0",
    "model.safetensors": "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd",
}
QWEN = {"model": MODEL, "revision": REVISION, "device": "cpu", "dtype": "float32",
        "attention_implementation": "sdpa", "padding_side": "left", "batch_size": 16,
        "max_input_tokens": 128, "torch_threads": 4, "pooling": "last non-padding token",
        "cache": False, "prompt": None, "generation": None, "finetuning": False,
        "add_special_tokens": True, "truncation": False, "deduplicate_identical_texts": True}
TFIDF = {"analyzer": "one complete field=value line per token", "smooth_idf": True,
         "sublinear_tf": False, "dtype": "float64", "fit_on_all_catalog_rows": True}
METHODS = {"tfidf": "TF-IDF (парный контроль)", "qwen": "Qwen3-Embedding-0.6B"}
SCORE_DECIMALS = 12


def json_file(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def csv_file(path, fields, records):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def tfidf_vectors(texts, details):
    from sklearn.feature_extraction.text import TfidfVectorizer

    start = perf_counter()
    vectorizer = TfidfVectorizer(analyzer=str.splitlines, norm=None, smooth_idf=True,
                                 sublinear_tf=False, dtype=np.float64)
    matrix = vectorizer.fit_transform(texts).toarray()
    details["fit_transform_seconds"] = perf_counter() - start
    return matrix


def qwen_vectors(texts, details, args):
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(QWEN["torch_threads"])
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    start = perf_counter()
    model_dir = args.model_dir
    if model_dir is None:
        from huggingface_hub import snapshot_download

        model_dir = Path(snapshot_download(MODEL, revision=REVISION, allow_patterns=list(MODEL_FILES),
                                           local_files_only=not args.allow_download, token=False))
    details["resolve_files_seconds"] = perf_counter() - start
    start = perf_counter()
    hashes = {name: file_hash(model_dir / name) for name in MODEL_FILES}
    if hashes != MODEL_FILES:
        raise ValueError("Model file SHA256 does not match the pinned Qwen revision")
    details["model_files_sha256"] = hashes
    details["verify_model_files_seconds"] = perf_counter() - start

    start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, padding_side="left", use_fast=True,
                                              local_files_only=True, trust_remote_code=False)
    model, loading_info = AutoModel.from_pretrained(
        model_dir, dtype=torch.float32, attn_implementation="sdpa", use_safetensors=True,
        local_files_only=True, trust_remote_code=False, output_loading_info=True,
    )
    for key in ("missing_keys", "mismatched_keys", "error_msgs"):
        if loading_info.get(key):
            raise ValueError(f"Model weights failed to load cleanly: {key}: {loading_info[key]}")
    model.eval().requires_grad_(False)
    details.update({"load_model_and_tokenizer_seconds": perf_counter() - start,
                    "unexpected_checkpoint_keys": loading_info.get("unexpected_keys", []),
                    "loaded_model_class": type(model).__name__, "loaded_dtype": str(model.dtype),
                    "loaded_device": str(model.device), "tokenizer_class": type(tokenizer).__name__,
                    "pad_token_id": tokenizer.pad_token_id, "torch_interop_threads": 1,
                    "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()})

    distinct = list(dict.fromkeys(texts))
    indices = {text: index for index, text in enumerate(distinct)}
    vectors, lengths = [], []
    tokenize_seconds = forward_seconds = 0.0
    batch_size = QWEN["batch_size"]
    with torch.inference_mode():
        for offset in range(0, len(distinct), batch_size):
            start = perf_counter()
            batch = tokenizer(distinct[offset:offset + batch_size], padding=True, truncation=False,
                              add_special_tokens=True, return_tensors="pt")
            lengths.extend(batch["attention_mask"].sum(dim=1).tolist())
            if batch["input_ids"].shape[1] > QWEN["max_input_tokens"]:
                raise ValueError("Asset text exceeds input limit. No input is silently truncated.")
            if not bool(batch["attention_mask"][:, -1].all()):
                raise ValueError("Expected left padding and a real final token")
            tokenize_seconds += perf_counter() - start

            start = perf_counter()
            hidden = model(**batch, use_cache=False).last_hidden_state
            vectors.append(hidden[:, -1, :].contiguous().numpy())
            forward_seconds += perf_counter() - start
            print(f"qwen {len(lengths)}/{len(distinct)} unique descriptions", flush=True)

    details.update({"distinct_texts_encoded": len(distinct), "input_tokens_min": min(lengths),
                    "input_tokens_max": max(lengths), "tokenization_seconds": tokenize_seconds,
                    "forward_and_pool_seconds": forward_seconds})
    return np.concatenate(vectors)[[indices[text] for text in texts]]


def rank_users(matrix, catalog, evaluation, k):
    ids = [asset["ISIN"] for asset in catalog]
    positions = {isin: index for index, isin in enumerate(ids)}
    popularity = [asset["historical_buyers"] for asset in catalog]
    predictions, metrics = [], []
    for user in evaluation:
        profile = matrix[[positions[isin] for isin in user["history"]]].mean(axis=0)
        norm = np.linalg.norm(profile)
        if not np.isfinite(norm) or norm == 0:
            raise ValueError(f"Invalid profile norm for {user['user_id']}")
        cosine = np.clip(np.einsum("ij,j->i", matrix, profile / norm), -1.0, 1.0)
        keys = [round(float(score), SCORE_DECIMALS) for score in cosine]
        top = sorted(range(len(ids)), key=lambda i: (-keys[i], -popularity[i], ids[i]))[:k]
        ranking = [ids[i] for i in top]
        if len(set(ranking)) != k or not np.all(np.isfinite(cosine)):
            raise ValueError(f"Invalid recommendation list for {user['user_id']}")
        truth = set(user["truth"])
        for rank, index in enumerate(top, 1):
            predictions.append({"user_id": user["user_id"], "rank": rank, "ISIN": ids[index],
                                "cosine": float(cosine[index]), "rank_score": float(keys[index])})
        metrics.append({"user_id": user["user_id"], "relevant_count": len(truth),
                        "ndcg_at_10": ndcg(ranking, truth, k)})
    return predictions, metrics


def run_method(method, args, catalog, evaluation, k, details):
    start = perf_counter()
    details["stage"] = "vectorization"
    texts = [asset["text"] for asset in catalog]
    raw = tfidf_vectors(texts, details) if method == "tfidf" else qwen_vectors(texts, details, args)
    details["stage"] = "normalization_scoring_evaluation"
    scoring_start = perf_counter()
    matrix = np.asarray(raw, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if matrix.shape[0] != len(catalog) or not np.all(np.isfinite(norms)) or np.any(norms == 0):
        raise ValueError("Missing, zero, or non-finite asset vector")
    matrix = matrix / norms
    predictions, metrics = rank_users(matrix, catalog, evaluation, k)
    summary = aggregate(metrics)
    details["normalization_scoring_evaluation_seconds"] = perf_counter() - scoring_start
    details["method_seconds_excluding_output_io"] = perf_counter() - start

    details["stage"] = "output_write"
    start = perf_counter()
    dst = args.output_dir / method
    dst.mkdir()
    np.save(dst / "asset_vectors.npy", matrix, allow_pickle=False)
    csv_file(dst / "top10.csv", ("user_id", "rank", "ISIN", "cosine", "rank_score"), predictions)
    csv_file(dst / "per_user.csv", ("user_id", "relevant_count", "ndcg_at_10"), metrics)
    details.update({"status": "complete", "stage": "complete", "vector_shape": list(matrix.shape),
                    "output_io_seconds": perf_counter() - start, "failed_cases": 0, "metrics": summary})
    return metrics


def comparison(args, manifest, records):
    baseline = manifest["baseline"]
    lines = ["# HW8 · результаты парного эксперимента", "",
             "| Метод | Источник | Пользователи | Непустая truth | nDCG@10 · все | nDCG@10 · непустая truth | Время, с | Ошибки |",
             "|---|---|---:|---:|---:|---:|---:|---|" ]

    def result_line(label, source, summary, elapsed):
        return (f"| {label} | {source} | {summary['users']} | {summary['nonempty_truth_users']} | "
                f"{summary['ndcg_at_10']:.4f} | {summary['ndcg_at_10_nonempty']:.4f} | {elapsed} | 0 |")

    for method, label in BASELINES.items():
        lines.append(result_line(label, "Архив Алины", baseline["metrics"][method], "—¹"))
    for method, label in METHODS.items():
        details = manifest["methods"][method]
        if details["status"] == "complete":
            elapsed = details["method_seconds_excluding_output_io"]
            lines.append(result_line(label, "Этот эксперимент", details["metrics"], f"{elapsed:.4f}²"))
        else:
            status = {"failed": "Сбой ветки", "not_requested": "Ветка вне этого запуска"}[details["status"]]
            lines.append(f"| {label} | Этот эксперимент | — | — | — | — | — | {status} |")
    shared_seconds = baseline["runtime"]["seconds"]
    lines += ["", f"¹ {shared_seconds:.4f} с за один запуск всех четырёх baseline в Colab/Linux, включая загрузку данных, оценку и запись файлов. Ошибки в таблице обозначают число невалидных сохранённых Top‑10.",
              "", "² Время ветки от начала векторизации до расчёта средних, включая импорты. Для Qwen включает поиск и проверку файлов модели, загрузку, токенизацию и forward. Подготовка общего набора, запись артефактов и отдельная загрузка весов в показатель не входят. Настройки и интервалы сохранены в `run_manifest.json`."]
    if records.keys() == METHODS.keys():
        control = manifest["methods"]["tfidf"]["metrics"]
        embedding = manifest["methods"]["qwen"]["metrics"]
        deltas = [b["ndcg_at_10"] - a["ndcg_at_10"] for a, b in zip(records["tfidf"], records["qwen"])]
        paired = {
            "delta_all": embedding["ndcg_at_10"] - control["ndcg_at_10"],
            "delta_nonempty": embedding["ndcg_at_10_nonempty"] - control["ndcg_at_10_nonempty"],
            "users_improved": sum(delta > 0 for delta in deltas),
            "users_declined": sum(delta < 0 for delta in deltas),
            "users_unchanged": deltas.count(0),
        }
        manifest["paired_qwen_minus_tfidf"] = paired
        lines += ["", f"Qwen минус TF-IDF составляет {paired['delta_all']:+.4f} по всем 100 и "
                  f"{paired['delta_nonempty']:+.4f} по 11 пользователям с непустой truth. "
                  f"Улучшение у {paired['users_improved']}, снижение у {paired['users_declined']}, "
                  f"тот же nDCG@10 у {paired['users_unchanged']} из 100."]
    (args.output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alina-zip", type=Path, required=True)
    parser.add_argument("--far-trans-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="Fresh directory for this run")
    parser.add_argument("--method", choices=("both", *METHODS), default="both")
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument("--model-dir", type=Path, help="Local copy of the four pinned model files")
    model_group.add_argument("--allow-download", action="store_true", help="Fetch the pinned snapshot if missing")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    manifest = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "started", "command": [sys.executable, *sys.argv], "errors": [],
        "hardware_and_software": {"platform": platform.platform(), "architecture": platform.machine(),
                                  "logical_cpus": os.cpu_count(), "python": sys.version,
                                  "packages": {p: version(p) for p in ("numpy", "scikit-learn", "scipy", "torch",
                                                                      "transformers", "huggingface-hub",
                                                                      "tokenizers", "safetensors")}},
        "scoring": {"fields": FIELDS, "missing_value": MISSING, "normalization": "asset L2 in float64",
                    "profile": "mean of normalized vectors for unique eligible pre-cutoff buys",
                    "ranking": "descending cosine rounded to 12 decimal places, descending historical "
                               "distinct buyer count, ascending ISIN",
                    "candidates": "full eligible catalog in each arm", "reranking": False,
                    "exclude_seen": False, "invalid_policy": "fail branch, no fallback or partial metrics"},
        "methods": {"tfidf": {"status": "not_requested", "settings": TFIDF},
                    "qwen": {"status": "not_requested", "settings": QWEN}},
        "code_sha256": {name: file_hash(Path(__file__).with_name(name))
                        for name in ("run_experiment.py", "protocol.py", "requirements.txt")},
    }
    try:
        preparation = perf_counter()
        with ZipFile(args.alina_zip) as bundle, ZipFile(args.far_trans_zip) as far:
            protocol, bundle_members = read_bundle(bundle)
            catalog, evaluation, excluded = load_data(far, protocol)
            baseline, runtime, commit = validate_baselines(bundle, protocol, evaluation)
        manifest["input_preparation_and_baseline_validation_seconds"] = perf_counter() - preparation
        manifest["inputs"] = {"alina_zip_sha256": file_hash(args.alina_zip),
                              "far_trans_zip_sha256": file_hash(args.far_trans_zip),
                              "baseline_members_sha256": bundle_members, "source_csv_sha256": protocol["source_sha256"],
                              "protocol_hash": protocol["protocol_hash"], "excluded_rows": excluded,
                              "catalog_assets": len(catalog), "users": len(evaluation),
                              "distinct_catalog_texts": len({a["text"] for a in catalog}),
                              "missing_values_by_field": {field: sum(a["fields"][field] == MISSING for a in catalog)
                                                          for field in FIELDS},
                              "conflicting_values_by_field": dict(Counter(f for a in catalog for f in a["conflicting_fields"]))}
        manifest["baseline"] = {"source": args.alina_zip.name, "package_commit": commit,
                                "metrics": baseline, "runtime": runtime, "invalid_saved_top10": 0,
                                "saved_top10_checked": len(BASELINES) * len(evaluation)}
        json_file(args.output_dir / "protocol.json", protocol)
        json_file(args.output_dir / "catalog_inputs.json", catalog)
        json_file(args.output_dir / "evaluation.json", evaluation)
        records = {}
        for method in METHODS if args.method == "both" else (args.method,):
            details = manifest["methods"][method]
            try:
                records[method] = run_method(method, args, catalog, evaluation, protocol["k"], details)
            except Exception as error:
                details["status"] = "failed"
                manifest["errors"].append({"method": method, "stage": details["stage"],
                                           "type": type(error).__name__, "message": str(error)})
                traceback.print_exc()
            json_file(args.output_dir / "run_manifest.json", manifest)
        comparison(args, manifest, records)
        manifest["status"] = "partial" if manifest["errors"] else "complete"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["errors"].append({"stage": "experiment", "type": type(error).__name__, "message": str(error)})
        traceback.print_exc()
    finally:
        manifest["run_wall_seconds_before_final_manifest_write"] = perf_counter() - start
        json_file(args.output_dir / "run_manifest.json", manifest)
    return bool(manifest["errors"])


if __name__ == "__main__":
    sys.exit(main())
