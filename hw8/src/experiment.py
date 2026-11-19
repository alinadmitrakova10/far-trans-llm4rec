"""CLI: baseline, local-check (no model), or explicitly authorized encoder pair."""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time

from protocol import load_starter, verify, digest
from profiles import build_profiles, structured_vectors, shared_token_limit, model_input, INSTRUCTION
from scorer import recommend, NEIGHBOR_K

ROOT = Path(__file__).resolve().parents[2]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def csv_save(path, records):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def manual_check(st, predictions, truth, users):
    uid = next(u for u in users if truth.get(u))
    result = dict(user_id=uid, relevant_ids=sorted(truth[uid]), methods={})
    for method, rankings in predictions.items():
        top = rankings[uid]
        terms = [int(isin in truth[uid]) / math.log2(rank + 1)
                 for rank, isin in enumerate(top, 1)]
        dcg = sum(terms)
        idcg = sum(1 / math.log2(rank + 1) for rank in range(1, min(10, len(truth[uid])) + 1))
        independent = dcg / idcg
        evaluator = st.ndcg10(top, truth[uid])
        assert math.isclose(independent, evaluator, abs_tol=1e-12)
        result['methods'][method] = dict(top10_ids=top, relevance=[int(i in truth[uid]) for i in top],
                                          discounted_gains=terms, dcg=dcg, idcg=idcg,
                                          independent_ndcg=independent, evaluator_ndcg=evaluator)
    return result


def baseline(starter, data, out):
    target = out / 'baseline'
    command = [sys.executable, str(starter), 'run', '--data-dir', str(data), '--output-dir', str(target)]
    start = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True)
    seconds = time.perf_counter() - start
    target.mkdir(parents=True, exist_ok=True)
    (target / 'run.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    save(target / 'runtime.json', dict(seconds=seconds,
         scope='entire starter subprocess: loading, all FOUR methods, evaluation and output I/O; NOT per-method',
         command=command, python=sys.version, platform=platform.platform(), processor=platform.processor(),
         starter_sha256=digest(starter)))
    print(proc.stdout)


def baseline_predictions(path):
    predictions = {}
    for row in read_csv(path):
        predictions.setdefault(row['method'], {}).setdefault(row['user_id'], []).append(row['ISIN'])
    return predictions


def report(out):
    metrics = json.loads((out / 'baseline/metrics.json').read_text(encoding='utf-8'))
    elapsed = json.loads((out / 'baseline/runtime.json').read_text(encoding='utf-8'))['seconds']
    rows = []
    methods = ['popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell', 'structured_knn', 'qwen_knn']
    for method in methods:
        row = dict(method=method, status='not run', users=None, nonempty_truth_users=None,
                   ndcg_at_10=None, ndcg_at_10_nonempty=None, failures=None, invalid_outputs=None,
                   runtime_seconds=None, runtime_scope='not measured')
        if method in metrics['methods']:
            row.update(metrics['methods'][method], status='executed', failures=0, invalid_outputs=0,
                       runtime_seconds=elapsed, runtime_scope='shared entire four-baseline subprocess; do not sum rows')
        elif (out / 'encoders' / method / 'metrics.json').exists():
            enc = json.loads((out / 'encoders' / method / 'metrics.json').read_text(encoding='utf-8'))
            assert enc['protocol_hash'] == metrics['protocol_hash']
            row.update(enc['aggregate'], status='executed', failures=enc['failed_query_users'],
                       invalid_outputs=enc['invalid_outputs_before_fallback'],
                       runtime_seconds=enc['encoding_seconds'] + enc['scoring_seconds'],
                       runtime_scope='branch encoding + scoring only; shared prep and model loading separate in manifest')
        rows.append(row)
    # Fields must be uniform even while the encoder rows are still unexecuted.
    keys = list(dict.fromkeys(k for row in rows for k in row))
    rows = [{k: row.get(k) for k in keys} for row in rows]
    csv_save(out / 'comparison.csv', rows)
    header = '| Method | Status | Users | Nonempty | nDCG@10 all | nDCG@10 nonempty | Failures / invalid | Runtime (s) | Scope |'
    lines = [header, '|' + '---|' * 9]
    def fmt(value):
        return '—' if value is None else f'{value:.4f}'
    for r in rows:
        lines.append(f"| {r['method']} | {r['status']} | {r['users']} | {r['nonempty_truth_users']} | "
                     f"{fmt(r['ndcg_at_10'])} | {fmt(r['ndcg_at_10_nonempty'])} | "
                     f"{r['failures']} / {r['invalid_outputs']} | {fmt(r['runtime_seconds'])} | {r['runtime_scope']} |")
    (out / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['baseline', 'local-check', 'encoders', 'report'])
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/raw/FAR-Trans/FAR-Trans')
    parser.add_argument('--starter', type=Path, default=ROOT / 'hw8/reference/starter/starter.py')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'hw8/outputs/local')
    parser.add_argument('--allow-qwen-inference', action='store_true')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--batch-size', type=int, default=8)
    args = parser.parse_args()
    if args.action == 'encoders' and not args.allow_qwen_inference:
        parser.error('Qwen inference requires explicit --allow-qwen-inference after user approval')
    if args.batch_size < 1:
        parser.error('Batch size must be positive')
    out, data = args.output_dir.resolve(), args.data_dir.resolve()
    st = load_starter(args.starter)
    if args.action == 'baseline':
        baseline(args.starter, data, out)
    if args.action == 'report':
        report(out)
        return
    protocol, assets, customers, history, truth = verify(st, data, out / 'baseline')
    users = protocol['users']
    predictions = baseline_predictions(out / 'baseline/predictions.csv')
    for method, rankings in predictions.items():
        assert list(rankings) == users
        for uid in users:
            st.validate_ranking(rankings[uid], assets)
    baseline_scores = read_csv(out / 'baseline/per_user.csv')
    assert set(predictions) == {'popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell'}
    assert len(baseline_scores) == 4 * len(users)
    for row in baseline_scores:
        uid, method = row['user_id'], row['method']
        assert int(row['relevant_count']) == len(truth.get(uid, set()))
        assert math.isclose(float(row['ndcg_at_10']), st.ndcg10(predictions[method][uid], truth.get(uid, set())), abs_tol=1e-12)
    saved_metrics = json.loads((out / 'baseline/metrics.json').read_text(encoding='utf-8'))
    assert saved_metrics['protocol_hash'] == protocol['protocol_hash']
    for method in predictions:
        records = [dict(ndcg_at_10=float(r['ndcg_at_10']), relevant_count=int(r['relevant_count']))
                   for r in baseline_scores if r['method'] == method]
        assert saved_metrics['methods'][method] == st.aggregate(records)
    save(out / 'manual_check.json', manual_check(st, predictions, truth, users))
    checked_uid = next(u for u in users if truth.get(u))
    source_buys = []
    seen_rows = set()
    for row in st.rows(data / 'transactions.csv'):
        key = tuple(sorted(row.items()))
        if key in seen_rows:
            continue
        seen_rows.add(key)
        if (row['customerID'] == checked_uid and row['transactionType'] == 'Buy'
                and int(row['transactionID']) >= 0 and row['ISIN'] in assets
                and protocol['cutoff'] <= row['timestamp'][:10] < protocol['end_exclusive']):
            source_buys.append({k: row[k] for k in ('customerID', 'ISIN', 'transactionID', 'timestamp')})
    assert {r['ISIN'] for r in source_buys} == truth[checked_uid]
    save(out / 'manual_truth_source_rows.json', source_buys)
    if args.action == 'baseline':
        report(out)
        return
    start = time.perf_counter()
    # All as-of-known warm users, not merely the 100 evaluation users.
    neighbors = sorted(uid for uid in customers if history.get(uid))
    events = st.scan_recent_events(data, protocol['cutoff'], assets)
    profiles = build_profiles(neighbors, assets, history, events, protocol['cutoff'])
    pop = st.popularity_scores(history, assets)
    if args.action == 'local-check':
        # Explicitly a smoke check BEFORE shared token limiting, not the final S result.
        vectors, vocab = structured_vectors(profiles, neighbors)
        first, diagnostics = recommend(vectors, neighbors, users, history, assets, pop)
        second, _ = recommend(vectors, neighbors, users, history, assets, pop)
        assert first == second
        for ranking in first.values():
            st.validate_ranking(ranking, assets)
        save(out / 'local_check.json', dict(status='passed; untruncated structured smoke only, NOT final Encoder results',
             protocol_hash=protocol['protocol_hash'], neighbor_users=len(neighbors), features=len(vocab),
             profiles_sha256=hashlib.sha256(json.dumps(profiles, sort_keys=True).encode()).hexdigest(),
             same_predictions_on_repeat=True, manual_check=manual_check(st, {'structured_smoke': first}, truth, users),
             elapsed_seconds=time.perf_counter() - start))
        print('Local profile/history, protocol, Top-10, deterministic scorer and independent nDCG checks passed.')
        return
    from qwen import tokenizer, embed, MODEL_ID, REVISION
    tok = tokenizer()
    profiles, truncation = shared_token_limit(profiles, tok)
    prep_seconds = time.perf_counter() - start
    encdir = out / 'encoders'
    if encdir.exists():
        raise ValueError('Encoder directory already exists; use a fresh output directory to avoid mixing runs')
    encdir.mkdir(parents=True, exist_ok=True)
    environment = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, check=True)
    (encdir / 'environment.txt').write_text(environment.stdout, encoding='utf-8')
    shutil.copyfile(out / 'baseline/protocol.json', encdir / 'protocol.json')
    assert digest(encdir / 'protocol.json') == digest(out / 'baseline/protocol.json')
    save(encdir / 'profiles.json', profiles)
    save(encdir / 'truncation.json', truncation)
    save(encdir / 'neighbor_users.json', neighbors)
    manifest = dict(protocol_hash=protocol['protocol_hash'], model_id=MODEL_ID, revision=REVISION,
                    instruction=INSTRUCTION, input_template='Instruct: {instruction}\nQuery: {profile}',
                    neighbor_k=NEIGHBOR_K, neighbor_policy='all as-of-known users with retained buys; exclude self',
                    scorer='sum max(cosine,0)*binary historical purchase matrix',
                    neighbor_ties='user ID ascending', item_ties='ISIN ascending',
                    repeat_purchases=True, fallback='starter historical popularity when no positive item score',
                    parameters='a priori; k=20 and recency 30/180 days; no test tuning',
                    metadata_conflicts='starter latest_before: first CSV row at latest timestamp wins',
                    truncation='lexicographic complete-row prefix; <=512 pinned-tokenizer tokens including instruction; shared S/L',
                    shared_preparation_seconds=prep_seconds, python=sys.version, platform=platform.platform(),
                    source_sha256={p.name: digest(p) for p in Path(__file__).parent.glob('*.py')},
                    requirements_sha256=digest(ROOT / 'hw8/requirements-colab.txt'))
    save(encdir / 'manifest.json', manifest)
    for method in ('structured_knn', 'qwen_knn'):
        target = encdir / method
        target.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        if method == 'structured_knn':
            vectors, vocab = structured_vectors(profiles, neighbors)
            save(target / 'vocabulary.json', vocab)
            metadata = dict(failures=[], encoder='count-weighted one-hot marginals, joint tuple, joint tuple+recency')
        else:
            # Model download/load excluded from branch encoding time and reported separately.
            os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
            vectors, metadata = embed([model_input(profiles[u]) for u in neighbors], tok,
                                      args.batch_size, args.device)
        encoding_seconds = (time.perf_counter() - start if method == 'structured_knn'
                            else metadata['inference_seconds'])
        import numpy as np
        np.save(target / 'vectors.npy', vectors)
        save(target / 'inference.json', metadata)
        start = time.perf_counter()
        rankings, diagnostics = recommend(vectors, neighbors, users, history, assets, pop)
        scoring_seconds = time.perf_counter() - start
        records, predrows, invalid = [], [], []
        for uid in users:
            try:
                st.validate_ranking(rankings[uid], assets)
            except ValueError as error:
                invalid.append(dict(user_id=uid, error=str(error)))
                rankings[uid] = st.order(pop)[:10]
            records.append(dict(user_id=uid, method=method, relevant_count=len(truth.get(uid, set())),
                                ndcg_at_10=st.ndcg10(rankings[uid], truth.get(uid, set()))))
            predrows.extend(dict(method=method, user_id=uid, rank=r, ISIN=i)
                            for r, i in enumerate(rankings[uid], 1))
        csv_save(target / 'predictions.csv', predrows)
        csv_save(target / 'per_user.csv', records)
        save(target / 'diagnostics.json', diagnostics)
        save(target / 'metrics.json', dict(protocol_hash=protocol['protocol_hash'], aggregate=st.aggregate(records),
             encoding_seconds=encoding_seconds, scoring_seconds=scoring_seconds,
             failed_query_users=sum(d['invalid_query'] for d in diagnostics['users'].values()),
             invalid_outputs_before_fallback=len(invalid), invalid_output_details=invalid,
             failed_unique_profiles=len(metadata['failures']),
             fallback_users=sum(d['fallback'] for d in diagnostics['users'].values())))
        predictions[method] = rankings
        save(out / 'manual_check.json', manual_check(st, predictions, truth, users))
        report(out)
    manifest['qwen_status'] = 'executed; see inference.json for actual failures and runtime'
    save(encdir / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
