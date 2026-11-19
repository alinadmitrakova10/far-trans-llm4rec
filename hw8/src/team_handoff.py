"""Audit saved T4 artifacts and package Alina's baseline for Team 5. No inference."""
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import zipfile

from protocol import load_starter, verify, STARTER_SHA256

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'aa32f8d34310da25306acb4e16a508a3b6cd9e89'
RUN = ROOT / 'hw8/outputs/colab_gpu'
ARCHIVE = ROOT / 'hw8/outputs/hw8_t4_encoder_outputs.zip'
TARGET = ROOT / 'hw8/outputs/team5_alina_t4_protocol_check'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def close(a, b):
    assert math.isclose(a, b, rel_tol=0, abs_tol=1e-12), (a, b)


def independent_ndcg(ranking, truth):
    if not truth:
        return 0.0
    return (sum(int(i in truth) / math.log2(r + 1) for r, i in enumerate(ranking[:10], 1))
            / sum(1 / math.log2(r + 1) for r in range(1, min(10, len(truth)) + 1)))


def aggregate(records):
    nonempty = [r for r in records if r['relevant_count']]
    return dict(users=len(records), nonempty_truth_users=len(nonempty),
                empty_truth_users=len(records) - len(nonempty),
                ndcg_at_10=sum(r['ndcg_at_10'] for r in records) / len(records),
                ndcg_at_10_nonempty=sum(r['ndcg_at_10'] for r in nonempty) / len(nonempty))


def main():
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert branch == 'hw8/alina-encoder'
    experiment_commit = subprocess.check_output(
        ['git', 'rev-parse', '--verify', f'{COMMIT}^{{commit}}'], cwd=ROOT, text=True).strip()
    assert experiment_commit == COMMIT
    # Later handoff commits may advance HEAD; provenance remains pinned to COMMIT.
    subprocess.run(['git', 'merge-base', '--is-ancestor', COMMIT, head], cwd=ROOT, check=True)
    # Check every archived file against the separate extraction, including vectors.
    archive_hashes = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        assert len(names) == len(set(names))
        assert set(names) == {p.relative_to(RUN).as_posix() for p in RUN.rglob('*') if p.is_file()}
        for name in names:
            assert (RUN / name).resolve().is_relative_to(RUN.resolve())
            archived = archive.read(name)
            assert sha(archived) == sha((RUN / name).read_bytes()), name
            archive_hashes[name] = sha(archived)
    st = load_starter(ROOT / 'hw8/reference/starter/starter.py')
    protocol, assets, customers, history, truth = verify(
        st, ROOT / 'data/raw/FAR-Trans/FAR-Trans', RUN / 'baseline')
    users = protocol['users']
    assert read_json(RUN / 'encoders/protocol.json') == protocol
    baseline = read_json(RUN / 'baseline/metrics.json')
    assert baseline['protocol_hash'] == protocol['protocol_hash']
    assert baseline['custom_failures'] == []
    # Independently rebuild the contexts from retained past inputs, not from labels.
    contexts, _ = st.contexts_for(users, assets, customers, history,
        {i: st.tokens(row) for i, row in assets.items()},
        st.popularity_scores(history, assets), protocol['cutoff'], 50, False)
    saved_contexts = [json.loads(line) for line in (RUN / 'baseline/contexts.jsonl').read_text(encoding='utf-8').splitlines()]
    assert saved_contexts == list(contexts.values())
    scores, aggregates = {}, {}
    comparison = {r['method']: r for r in read_csv(RUN / 'comparison.csv')}
    expected = {'popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell', 'structured_knn', 'qwen_knn'}
    assert set(comparison) == expected
    folders = [RUN / 'baseline', RUN / 'encoders/structured_knn', RUN / 'encoders/qwen_knn']
    rankings = {}
    for folder in folders:
        groups = {}
        for row in read_csv(folder / 'predictions.csv'):
            groups.setdefault((row['method'], row['user_id']), []).append((int(row['rank']), row['ISIN']))
        records = read_csv(folder / 'per_user.csv')
        assert len(records) == len(groups)
        assert len({(r['method'], r['user_id']) for r in records}) == len(records)
        for row in records:
            method, uid = row['method'], row['user_id']
            assert uid in users and method in expected
            pairs = sorted(groups[(method, uid)])
            assert [r for r, _ in pairs] == list(range(1, 11))
            top = [i for _, i in pairs]
            assert len(set(top)) == 10 and set(top) <= set(assets)
            value = independent_ndcg(top, truth.get(uid, set()))
            close(value, float(row['ndcg_at_10']))
            close(value, st.ndcg10(top, truth.get(uid, set())))
            assert int(row['relevant_count']) == len(truth.get(uid, set()))
            scores.setdefault(method, {})[uid] = dict(ndcg_at_10=value, relevant_count=len(truth.get(uid, set())))
            rankings[(method, uid)] = top
    assert set(scores) == expected
    for method, per_user in scores.items():
        assert set(per_user) == set(users)
        computed = aggregate([per_user[u] for u in users])
        saved = (baseline['methods'][method] if method in baseline['methods'] else
                 read_json(RUN / 'encoders' / method / 'metrics.json')['aggregate'])
        for key, value in computed.items():
            close(value, saved[key])
            close(value, float(comparison[method][key]))
        assert computed['users'] == 100 and computed['nonempty_truth_users'] == 11
        assert comparison[method]['failures'] == comparison[method]['invalid_outputs'] == '0'
        aggregates[method] = computed
    inference = read_json(RUN / 'encoders/qwen_knn/inference.json')
    manifest = read_json(RUN / 'encoders/manifest.json')
    runtime = read_json(RUN / 'baseline/runtime.json')
    assert runtime['starter_sha256'] == STARTER_SHA256
    for method in baseline['methods']:
        close(runtime['seconds'], float(comparison[method]['runtime_seconds']))
    assert inference['model_id'] == manifest['model_id'] == 'Qwen/Qwen3-Embedding-0.6B'
    assert inference['revision'] == manifest['revision'] == '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'
    assert inference['hardware'] == 'Tesla T4' and inference['frozen'] is True
    assert inference['failures'] == []
    close(inference['inference_seconds'], read_json(RUN / 'encoders/qwen_knn/metrics.json')['encoding_seconds'])
    code_hash_checks = {}
    for name, expected_hash in manifest['source_sha256'].items():
        blob = subprocess.check_output(['git', 'show', f'{COMMIT}:hw8/src/{name}'], cwd=ROOT)
        assert sha(blob) == expected_hash, name
        code_hash_checks[name] = expected_hash
    req = subprocess.check_output(['git', 'show', f'{COMMIT}:hw8/requirements-colab.txt'], cwd=ROOT)
    assert sha(req) == manifest['requirements_sha256']
    import numpy as np
    neighbors = read_json(RUN / 'encoders/neighbor_users.json')
    assert neighbors == sorted(u for u in customers if history.get(u))
    for method in ('structured_knn', 'qwen_knn'):
        folder = RUN / 'encoders' / method
        metrics, diagnostics = read_json(folder / 'metrics.json'), read_json(folder / 'diagnostics.json')
        assert metrics['protocol_hash'] == protocol['protocol_hash']
        for key in ('failed_query_users', 'invalid_outputs_before_fallback', 'failed_unique_profiles', 'fallback_users'):
            assert metrics[key] == 0
        assert diagnostics['invalid_embedding_rows'] == 0
        assert set(diagnostics['users']) == set(users)
        assert all(not r['fallback'] and not r['invalid_query'] for r in diagnostics['users'].values())
        vectors = np.load(folder / 'vectors.npy', mmap_mode='r', allow_pickle=False)
        assert vectors.shape[0] == len(neighbors) and np.isfinite(vectors).all()
        assert (np.linalg.norm(vectors, axis=1) > 0).all()
        if method == 'qwen_knn':
            assert vectors.shape[1] == 1024
        close(metrics['encoding_seconds'] + metrics['scoring_seconds'], float(comparison[method]['runtime_seconds']))
    nonempty = [u for u in users if truth.get(u)]
    delta = {u: scores['qwen_knn'][u]['ndcg_at_10'] - scores['structured_knn'][u]['ndcg_at_10'] for u in users}
    paired = dict(all_users=sum(delta.values()) / len(users),
                  nonempty=sum(delta[u] for u in nonempty) / len(nonempty),
                  wins=sum(delta[u] > 1e-12 for u in nonempty),
                  losses=sum(delta[u] < -1e-12 for u in nonempty),
                  ties=sum(abs(delta[u]) <= 1e-12 for u in nonempty))
    # Verify saved single-user calculations for all six methods without calling inference.
    manual = read_json(RUN / 'manual_check.json')
    uid = manual['user_id']
    assert manual['relevant_ids'] == sorted(truth[uid])
    for method, check in manual['methods'].items():
        assert check['top10_ids'] == rankings[(method, uid)]
        close(check['independent_ndcg'], scores[method][uid]['ndcg_at_10'])
        close(check['evaluator_ndcg'], scores[method][uid]['ndcg_at_10'])
    prior_baseline_equal = {}
    for name in ('protocol.json', 'metrics.json', 'contexts.jsonl', 'predictions.csv', 'per_user.csv'):
        prior_baseline_equal[name] = (RUN / 'baseline' / name).read_bytes() == (ROOT / 'hw8/outputs/colab/baseline' / name).read_bytes()
        assert prior_baseline_equal[name], name
    result = dict(status='verified saved artifacts; no inference or parameter tuning',
        owner='Alina; NOT yet a shared Team 5 run', code_commit=COMMIT,
        protocol_hash=protocol['protocol_hash'], archive_sha256=sha(ARCHIVE.read_bytes()),
        archive_files_checked=len(archive_hashes), archive_file_sha256=archive_hashes,
        source_code_commit_hashes_verified=code_hash_checks, neighbor_users=len(neighbors),
        aggregates=aggregates, qwen_minus_structured=paired,
        runtime=dict(baseline_all_four_seconds=runtime['seconds'],
                     structured_encoding_scoring_seconds=float(comparison['structured_knn']['runtime_seconds']),
                     qwen_encoding_scoring_seconds=float(comparison['qwen_knn']['runtime_seconds']),
                     shared_preparation_seconds=manifest['shared_preparation_seconds'],
                     qwen_model_load_seconds=inference['model_load_seconds'],
                     qwen_inference_seconds=inference['inference_seconds'],
                     scope='Baseline: whole subprocess; encoder branches: encoding + scoring, excluding shared preparation/model load'),
        previous_cpu_colab_baseline_byte_identical=prior_baseline_equal,
        attribution='Author uploaded/downloaded; Codex ran T4 cells; OpenCode audited saved artifacts. Author personal manual check: Popularity only.',
        team_status='Awaiting Ulyana artifacts and protocol confirmation; no claim of agreed method or transfer to Daria.')
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in ('protocol.json', 'metrics.json', 'contexts.jsonl', 'predictions.csv', 'per_user.csv', 'runtime.json'):
        shutil.copyfile(RUN / 'baseline' / name, TARGET / name)
    (TARGET / 'commit.txt').write_text(COMMIT + '\n', encoding='utf-8')
    (TARGET / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'hw8/TEAM5_PROTOCOL_CHECK.md', TARGET / 'HANDOFF.md')
    package_hashes = {p.name: sha(p.read_bytes()) for p in sorted(TARGET.iterdir()) if p.is_file() and p.name != 'SHA256.json'}
    (TARGET / 'SHA256.json').write_text(json.dumps(package_hashes, indent=2) + '\n', encoding='utf-8')
    output_zip = TARGET.with_suffix('.zip')
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(TARGET.iterdir()):
            archive.write(path, path.name)
    with zipfile.ZipFile(output_zip) as archive:
        assert archive.testzip() is None
        for name, expected_hash in package_hashes.items():
            assert sha(archive.read(name)) == expected_hash
    print(json.dumps(dict(aggregates=aggregates, paired=paired, files_checked=len(archive_hashes)), indent=2))
    print('Verified package:', output_zip)


if __name__ == '__main__':
    main()
