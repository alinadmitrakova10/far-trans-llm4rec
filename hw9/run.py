"""HW9 development experiment: saved HW8 vectors or fresh Qwen CUDA inference."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from verify_hw8 import ROOT, EXPECTED_PROTOCOL, load
from protocol import load_starter, verify, digest
from profiles import serialize, structured_vectors, build_profiles, shared_token_limit, model_input
from scorer import recommend
from experiment import save, csv_save, baseline_predictions, manual_check

TFIDF = dict(ngram_range=(1, 2), lowercase=True, token_pattern=r'(?u)\b\w+\b',
             min_df=1, use_idf=True, smooth_idf=True, sublinear_tf=False,
             norm='l2', dtype=np.float32)
GROUPS = ('1', '2-3', '4-10', '11-30', '31+')


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def array_hash(value):
    return hashlib.sha256(value.tobytes(order='C')).hexdigest()


def group_for(count):
    if count < 1:
        raise ValueError('Neighbor must have past buys')
    return GROUPS[next(i for i, upper in enumerate((1, 3, 10, 30, float('inf'))) if count <= upper)]


def permutation(vectors, counts, seed):
    """Return recipient-row -> donor-row; one random cycle per valid group."""
    valid = np.isfinite(vectors).all(axis=1) & (np.linalg.norm(np.nan_to_num(vectors), axis=1) > 0)
    labels = [group_for(int(n)) for n in counts]
    donor = np.arange(len(vectors))
    rng = np.random.default_rng(seed)
    groups = {}
    for label in GROUPS:
        members = np.array([i for i, g in enumerate(labels) if g == label], dtype=int)
        eligible = members[valid[members]]
        cycle = rng.permutation(eligible)
        if len(cycle) > 1:
            donor[cycle] = np.roll(cycle, -1)
        assert sorted(donor[members].tolist()) == members.tolist()
        groups[label] = dict(users=len(members), valid_users=len(eligible),
                             changed_donors=int(np.sum(donor[members] != members)))
    assert np.array_equal(donor[~valid], np.flatnonzero(~valid))
    return donor, labels, groups


def changed_rows(original, shuffled):
    # NaNs in invalid rows left in place are not counted as a change.
    return ~np.all((original == shuffled) | (np.isnan(original) & np.isnan(shuffled)), axis=1)


def version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'hw8/outputs/colab_gpu')
    parser.add_argument('--verification', type=Path,
                        default=ROOT / 'hw9/outputs/hw8_reproduction_20261126/verification.json')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/raw/FAR-Trans/FAR-Trans')
    parser.add_argument('--starter', type=Path, default=ROOT / 'hw8/reference/starter/starter.py')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--fresh-qwen', action='store_true', help='Rebuild shared profiles and infer Qwen on CUDA, batch 8')
    args = parser.parse_args()
    out, enc = args.output_dir, args.source / 'encoders'
    if out.exists():
        raise ValueError('Use a fresh output directory')
    start = time.perf_counter()
    verification = load(args.verification)
    assert verification['protocol_hash'] == EXPECTED_PROTOCOL
    for relative, metadata in verification['inventory'].items():
        assert digest(args.source / relative) == metadata['sha256'], relative
    for method in ('structured_knn', 'qwen_knn'):
        assert verification['methods'][method]['identical_top10_users'] == 100
        assert verification['methods'][method]['identical_per_user_scores'] == 100
    st = load_starter(args.starter)
    protocol, assets, customers, history, truth = verify(st, args.data_dir, args.source / 'baseline')
    assert protocol['protocol_hash'] == EXPECTED_PROTOCOL
    assert load(enc / 'protocol.json') == protocol
    users, neighbors = protocol['users'], load(enc / 'neighbor_users.json')
    assert neighbors == sorted(u for u in customers if history.get(u))
    profiles, truncation = load(enc / 'profiles.json'), load(enc / 'truncation.json')
    assert list(profiles) == list(truncation) == neighbors
    tokenizer_seconds = profile_seconds = 0.0
    if args.fresh_qwen:
        from qwen import tokenizer, embed
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
        begin = time.perf_counter()
        tok = tokenizer()
        tokenizer_seconds = time.perf_counter() - begin
        begin = time.perf_counter()
        original = build_profiles(neighbors, assets, history,
                                  st.scan_recent_events(args.data_dir, protocol['cutoff'], assets), protocol['cutoff'])
        fresh_profiles, fresh_truncation = shared_token_limit(original, tok)
        assert fresh_profiles == profiles and fresh_truncation == truncation
        profiles, truncation = fresh_profiles, fresh_truncation
        profile_seconds = time.perf_counter() - begin
    documents = [serialize(profiles[u]) for u in neighbors]
    counts = np.array([sum(history[u].values()) for u in neighbors], dtype=np.int64)
    histories_hash, truth_hash = object_hash(history), object_hash({u: sorted(t) for u, t in truth.items()})
    pop = st.popularity_scores(history, assets)
    begin = time.perf_counter()
    rebuilt, vocab = structured_vectors(profiles, neighbors)
    structured_seconds = time.perf_counter() - begin
    assert vocab == load(enc / 'structured_knn/vocabulary.json')
    if args.fresh_qwen:
        structured = rebuilt
        qwen = None
    else:
        structured = np.load(enc / 'structured_knn/vectors.npy', allow_pickle=False)
        qwen = np.load(enc / 'qwen_knn/vectors.npy', allow_pickle=False)
        assert np.array_equal(rebuilt, structured)
    del rebuilt
    prep_seconds = time.perf_counter() - start
    out.mkdir(parents=True)
    save(out / 'protocol.json', protocol)
    save(out / 'neighbor_users.json', neighbors)
    save(out / 'profiles.json', profiles)
    save(out / 'truncation.json', truncation)
    save(out / 'truth.json', {u: sorted(truth.get(u, set())) for u in users})
    provenance = (load(ROOT / 'hw9/bundle_manifest.json') if (ROOT / 'hw9/bundle_manifest.json').exists() else
                  dict(git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                       git_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)))
    manifest = dict(status='running', started_utc=datetime.now(timezone.utc).isoformat(),
                    mode='fresh_qwen_cuda' if args.fresh_qwen else 'local_saved_hw8_vectors; no new Qwen inference',
                    provenance=provenance,
                    protocol_hash=EXPECTED_PROTOCOL, source=str(args.source.resolve()),
                    verification_sha256=digest(args.verification), source_archive_sha256=verification['archive_sha256'],
                    input_sha256={p: m['sha256'] for p, m in verification['inventory'].items()},
                    code_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                                 [*Path(__file__).parent.glob('*.py'), *(ROOT / 'hw8/src').glob('*.py')]},
                    command=[sys.executable, *sys.argv], python=sys.version, platform=platform.platform(),
                    libraries={n: version(n) for n in ('numpy', 'scipy', 'scikit-learn', 'torch', 'transformers')},
                    numpy_config=np.show_config(mode='dicts'), device='CPU',
                    qwen_original_manifest=load(enc / 'manifest.json'), qwen_original_inference=load(enc / 'qwen_knn/inference.json'),
                    history_sha256=histories_hash, truth_sha256=truth_hash,
                    shared_preparation_seconds=prep_seconds,
                    shared_preparation_scope='verify input files and source CSVs, load protocol/profiles/vectors, reconstruct structured vectors; no tokenizer/model load',
                    model_load_seconds=None, qwen_inference_seconds=None,
                    tokenizer_load_seconds=tokenizer_seconds, profile_construction_seconds=profile_seconds,
                    seeds=list(range(42, 52)), groups=list(GROUPS),
                    shuffle_policy='sorted input IDs; one default_rng(seed); fixed group order; shuffled cycle assigns next member as donor; invalid/singletons unchanged',
                    neighbor_k=20, tfidf_parameters={**TFIDF, 'dtype': 'float32'},
                    truncated_profiles=sum(a['original_rows'] > a['retained_rows'] for a in truncation.values()))
    save(out / 'manifest.json', manifest)
    qwen_metadata = None
    if args.fresh_qwen:
        qwen, qwen_metadata = embed([model_input(profiles[u]) for u in neighbors], tok, batch_size=8, device='cuda')
        manifest.update(model_load_seconds=qwen_metadata['model_load_seconds'],
                        qwen_inference_seconds=qwen_metadata['inference_seconds'],
                        qwen_fresh_inference=qwen_metadata,
                        shared_preparation_scope='input verification, source loading, tokenizer load, fresh profile scan and shared truncation, structured construction; excludes Qwen load/inference',
                        device='CUDA Qwen inference; CPU recommendation scoring')
        save(out / 'manifest.json', manifest)
    qwen.setflags(write=False)
    qwen_hash = array_hash(qwen)
    results, all_records, all_rankings, all_diagnostics = {}, {}, {}, {}

    def evaluate(method, vectors, encoding_seconds=0.0):
        begin = time.perf_counter()
        rankings, diagnostics = recommend(vectors, neighbors, users, history, assets, pop)
        scoring_seconds = time.perf_counter() - begin
        assert list(rankings) == users
        records, predrows = [], []
        for uid in users:
            st.validate_ranking(rankings[uid], assets)
            relevant = truth.get(uid, set())
            records.append(dict(method=method, user_id=uid, relevant_count=len(relevant),
                                hits_at_10=len(set(rankings[uid]) & relevant),
                                ndcg_at_10=st.ndcg10(rankings[uid], relevant)))
            predrows.extend(dict(method=method, user_id=uid, rank=r, ISIN=i)
                            for r, i in enumerate(rankings[uid], 1))
        metrics = dict(method=method, **st.aggregate(records),
                       relevant_pairs=sum(len(truth.get(u, set())) for u in users),
                       hit_pairs=sum(r['hits_at_10'] for r in records),
                       invalid_embedding_rows=diagnostics['invalid_embedding_rows'],
                       invalid_query_users=sum(d['invalid_query'] for d in diagnostics['users'].values()),
                       fallback_users=sum(d['fallback'] for d in diagnostics['users'].values()),
                       invalid_outputs=0, repairs=0, encoding_seconds=encoding_seconds,
                       scoring_seconds=scoring_seconds)
        target = out / method
        target.mkdir()
        csv_save(target / 'predictions.csv', predrows)
        csv_save(target / 'per_user.csv', records)
        save(target / 'metrics.json', metrics)
        save(target / 'diagnostics.json', diagnostics)
        results[method], all_records[method] = metrics, records
        all_rankings[method], all_diagnostics[method] = rankings, diagnostics
        print(method, json.dumps(metrics), flush=True)

    for method, vectors in (('structured_knn', structured), ('qwen_knn', qwen)):
        seconds = (structured_seconds if method == 'structured_knn' else qwen_metadata['inference_seconds']) if args.fresh_qwen else 0.0
        evaluate(method, vectors, seconds)
        if not args.fresh_qwen:
            assert all_rankings[method] == baseline_predictions(enc / method / 'predictions.csv')[method]
            assert st.aggregate(all_records[method]) == load(enc / method / 'metrics.json')['aggregate']
        if args.fresh_qwen:
            np.save(out / method / 'vectors.npy', vectors)
    if qwen_metadata is not None:
        save(out / 'qwen_knn/inference.json', qwen_metadata)
        save(out / 'structured_knn/vocabulary.json', vocab)
    begin = time.perf_counter()
    vectorizer = TfidfVectorizer(**TFIDF)
    tfidf = vectorizer.fit_transform(documents)
    encoding_seconds = time.perf_counter() - begin
    assert tfidf.shape[0] == len(neighbors) and tfidf.dtype == np.float32
    # HW8 exact scorer accepts dense arrays. Keep it unchanged for all branches.
    begin = time.perf_counter()
    dense = tfidf.toarray()
    densification_seconds = time.perf_counter() - begin
    assert np.allclose(vectorizer.transform(documents).toarray(), dense, atol=0, rtol=0)
    evaluate('tfidf_knn', dense, encoding_seconds)
    sparse.save_npz(out / 'tfidf_knn/vectors.npz', tfidf)
    vocabulary = {k: int(v) for k, v in vectorizer.vocabulary_.items()}
    save(out / 'tfidf_knn/vocabulary.json', vocabulary)
    np.save(out / 'tfidf_knn/idf.npy', vectorizer.idf_)
    save(out / 'tfidf_knn/representation.json', dict(
        parameters=manifest['tfidf_parameters'], shape=list(tfidf.shape), nnz=int(tfidf.nnz),
        vocabulary_sha256=object_hash(vocabulary), idf_sha256=digest(out / 'tfidf_knn/idf.npy'),
        profiles_sha256=digest(enc / 'profiles.json'),
        ordered_documents_sha256=object_hash(list(zip(neighbors, documents))),
        row_users_sha256=digest(out / 'neighbor_users.json'),
        dense_bytes=dense.nbytes, densification_seconds=densification_seconds,
        fit_scope='all 10404 pre-cutoff neighbor profiles, including evaluation users; no labels'))
    del dense
    eval_positions = np.array([neighbors.index(u) for u in users])
    shuffle_rows = []
    for seed in range(42, 52):
        begin = time.perf_counter()
        donor, labels, groups = permutation(qwen, counts, seed)
        assert np.array_equal(donor, permutation(qwen, counts, seed)[0])
        shuffled = qwen[donor]
        changed = changed_rows(qwen, shuffled)
        for label in GROUPS:
            indices = np.array([i for i, g in enumerate(labels) if g == label], dtype=int)
            groups[label]['changed_vectors'] = int(changed[indices].sum())
        metadata = dict(seed=seed, groups=groups, changed_donors=int(np.sum(donor != np.arange(len(qwen)))),
                        changed_vectors=int(changed.sum()),
                        changed_evaluation_donors=int(np.sum(donor[eval_positions] != eval_positions)),
                        changed_evaluation_vectors=int(changed[eval_positions].sum()),
                        reproducible=True, bijective_within_groups=True)
        method = f'qwen_shuffle_{seed}'
        evaluate(method, shuffled, time.perf_counter() - begin)
        csv_save(out / method / 'donors.csv', [dict(user_id=u, donor_id=neighbors[donor[i]],
                 past_buy_events=int(counts[i]), group=labels[i],
                 donor_past_buy_events=int(counts[donor[i]]), vector_changed=bool(changed[i]))
                 for i, u in enumerate(neighbors)])
        save(out / method / 'permutation.json', metadata)
        shuffle_rows.append(dict(seed=seed, **results[method],
                                 **{k: v for k, v in metadata.items() if k not in ('seed', 'groups')}))
        assert array_hash(qwen) == qwen_hash
        assert object_hash(history) == histories_hash
        assert object_hash({u: sorted(t) for u, t in truth.items()}) == truth_hash
    csv_save(out / 'shuffle_summary.csv', shuffle_rows)
    csv_save(out / 'comparison.csv', list(results.values()))
    paired = {}
    for left, right in (('qwen_knn', 'structured_knn'), ('qwen_knn', 'tfidf_knn')):
        differences = [a['ndcg_at_10'] - b['ndcg_at_10']
                       for a, b in zip(all_records[left], all_records[right]) if a['relevant_count']]
        paired[f'{left}_minus_{right}'] = dict(
            delta_all=results[left]['ndcg_at_10'] - results[right]['ndcg_at_10'],
            delta_nonempty=results[left]['ndcg_at_10_nonempty'] - results[right]['ndcg_at_10_nonempty'],
            improved=sum(d > 0 for d in differences), worsened=sum(d < 0 for d in differences),
            tied=sum(d == 0 for d in differences))
    aggregate_shuffle = {}
    for key in ('ndcg_at_10', 'ndcg_at_10_nonempty'):
        values = [r[key] for r in shuffle_rows]
        aggregate_shuffle[key] = dict(mean=float(np.mean(values)), minimum=min(values), maximum=max(values),
                                      original_qwen_minus_mean=results['qwen_knn'][key] - float(np.mean(values)))
    save(out / 'paired_comparisons.json', paired)
    save(out / 'shuffle_aggregate.json', aggregate_shuffle)
    save(out / 'manual_check.json', manual_check(st, all_rankings, truth, users))
    checked_uid = '870E814DB274CFA95600'
    checkdir = out / 'personal_check' / checked_uid
    checkdir.mkdir(parents=True)
    source_buys, seen = [], set()
    for row in st.rows(args.data_dir / 'transactions.csv'):
        key = tuple(sorted(row.items()))
        if key in seen:
            continue
        seen.add(key)
        if (row['customerID'] == checked_uid and row['transactionType'] == 'Buy'
                and int(row['transactionID']) >= 0 and row['ISIN'] in assets
                and protocol['cutoff'] <= row['timestamp'][:10] < protocol['end_exclusive']):
            source_buys.append(row)
    assert {r['ISIN'] for r in source_buys} == truth[checked_uid]
    csv_save(checkdir / 'june_buy_source_rows.csv', source_buys)
    save(checkdir / 'unique_relevant_isins.json', sorted(truth[checked_uid]))
    for method in ('qwen_knn', 'tfidf_knn'):
        csv_save(checkdir / f'{method}_top10.csv', [dict(user_id=checked_uid, rank=r, ISIN=i)
                 for r, i in enumerate(all_rankings[method][checked_uid], 1)])
        csv_save(checkdir / f'{method}_per_user.csv', [r for r in all_records[method] if r['user_id'] == checked_uid])
    # Explain every relevant pair for the 11 nonempty users, including neighbors'
    # binary purchase votes. The targeted HW8 failure is selected in the report.
    cases = []
    for uid in users:
        for isin in sorted(truth.get(uid, set())):
            case = dict(user_id=uid, ISIN=isin, past_buy_events=int(counts[neighbors.index(uid)]),
                        truncation=truncation[uid], methods={})
            for method in ('structured_knn', 'qwen_knn', 'tfidf_knn'):
                ranking, diag = all_rankings[method][uid], all_diagnostics[method]['users'][uid]
                voters = [dict(user_id=u, similarity=w) for u, w in zip(diag['neighbors'], diag['similarities'])
                          if isin in history[u]]
                case['methods'][method] = dict(rank=ranking.index(isin) + 1 if isin in ranking else None,
                    ndcg_at_10=next(r['ndcg_at_10'] for r in all_records[method] if r['user_id'] == uid),
                    neighbors=diag['neighbors'], voters=voters, sum_vote_weights=sum(v['similarity'] for v in voters))
            case['neighbor_overlap'] = {f'{a}_vs_{b}': len(set(case['methods'][a]['neighbors']) &
                                                        set(case['methods'][b]['neighbors']))
                                        for a, b in (('structured_knn', 'qwen_knn'), ('qwen_knn', 'tfidf_knn'))}
            cases.append(case)
    save(out / 'relevant_pair_analysis.json', cases)
    manifest.update(status='completed', completed_utc=datetime.now(timezone.utc).isoformat(),
                    invariants=dict(original_qwen_unchanged=True, history_unchanged=True, truth_unchanged=True,
                                    valid_top10_all_methods=True, reproducible_bijective_permutations=True))
    save(out / 'manifest.json', manifest)
    # Archive all local evidence, including exact runnable source snapshots.
    for path in [*Path(__file__).parent.glob('*.py'), *(ROOT / 'hw8/src').glob('*.py'),
                 ROOT / 'hw9/requirements-colab.txt', ROOT / 'hw8/requirements-colab.txt']:
        snapshot = out / 'code' / path.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(path.read_bytes())
    import shutil
    shutil.make_archive(str(out), 'zip', root_dir=out)
    print('Paired:', json.dumps(paired), flush=True)
    print('Shuffle aggregate:', json.dumps(aggregate_shuffle), flush=True)


if __name__ == '__main__':
    main()
