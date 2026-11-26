"""Audit HW8 artifacts and rescore saved vectors without model inference."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hw8/src'))
from protocol import digest, load_starter, verify
from profiles import build_profiles, structured_vectors
from scorer import recommend
from experiment import baseline_predictions, csv_save, read_csv, save

EXPECTED_PROTOCOL = '50efd4aeb415ba6f0c66dd0793a7c2033cdc32a42b86b58eebbca3e81eaf3417'
SOURCE_COMMIT = 'aa32f8d34310da25306acb4e16a508a3b6cd9e89'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'hw8/outputs/colab_gpu')
    parser.add_argument('--archive', type=Path, default=ROOT / 'hw8/outputs/hw8_t4_encoder_outputs.zip')
    parser.add_argument('--starter', type=Path, default=ROOT / 'hw8/reference/starter/starter.py')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/raw/FAR-Trans/FAR-Trans')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError('Use a fresh output directory')
    st = load_starter(args.starter)
    source, enc = args.source, args.source / 'encoders'
    protocol, assets, customers, history, truth = verify(st, args.data_dir, source / 'baseline')
    assert protocol['protocol_hash'] == EXPECTED_PROTOCOL
    assert load(enc / 'protocol.json') == protocol
    users = protocol['users']
    neighbors = load(enc / 'neighbor_users.json')
    assert neighbors == sorted(u for u in customers if history.get(u))
    assert len(neighbors) == 10404 and len(assets) == 767
    assert sum(bool(truth.get(u)) for u in users) == 11
    # Reconstruct every saved profile as the audited prefix of the original history.
    profiles, truncation = load(enc / 'profiles.json'), load(enc / 'truncation.json')
    assert list(profiles) == neighbors and list(truncation) == neighbors
    original = build_profiles(neighbors, assets, history,
                              st.scan_recent_events(args.data_dir, protocol['cutoff'], assets),
                              protocol['cutoff'])
    for uid in neighbors:
        audit = truncation[uid]
        assert audit['original_rows'] == len(original[uid])
        assert profiles[uid] == original[uid][:audit['retained_rows']]
        assert len(profiles[uid]) == audit['retained_rows']
        assert audit['retained_tokens'] <= 512
    manifest = load(enc / 'manifest.json')
    assert manifest['protocol_hash'] == EXPECTED_PROTOCOL and manifest['neighbor_k'] == 20
    # The original commit is independently available in local Git. Normalize LF
    # only for source files, because the Windows checkout may use CRLF.
    code = {}
    for name, expected in manifest['source_sha256'].items():
        archived = subprocess.run(['git', 'show', f'{SOURCE_COMMIT}:hw8/src/{name}'],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        assert hashlib.sha256(archived).hexdigest() == expected
        current = (ROOT / 'hw8/src' / name).read_bytes().replace(b'\r\n', b'\n')
        code[name] = dict(source_commit_matches=True,
                          current_lf_matches=hashlib.sha256(current).hexdigest() == expected)
    assert all(code[n]['current_lf_matches'] for n in ('scorer.py', 'profiles.py', 'protocol.py'))
    # Match the extracted files to the original T4 ZIP, allowing its root prefix.
    inventory = {}
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            matches = [n for n in archive.namelist() if n == relative or n.endswith('/' + relative)]
            entry = dict(bytes=path.stat().st_size, sha256=digest(path), archive_member=None)
            if matches:
                assert len(matches) == 1
                assert hashlib.sha256(archive.read(matches[0])).hexdigest() == entry['sha256']
                entry['archive_member'] = matches[0]
            inventory[relative] = entry
    required = [p for p in inventory if p.startswith(('encoders/', 'baseline/'))]
    assert all(inventory[p]['archive_member'] for p in required)
    args.output_dir.mkdir(parents=True)
    save(args.output_dir / 'protocol.json', protocol)
    summary = dict(protocol_hash=EXPECTED_PROTOCOL, users=len(users), nonempty_truth_users=11,
                   catalog=len(assets), neighbors=len(neighbors), source_commit=SOURCE_COMMIT,
                   archive_sha256=digest(args.archive), inventory=inventory, source_code=code,
                   truncated_profiles=sum(a['retained_rows'] < a['original_rows'] for a in truncation.values()),
                   python=sys.version, numpy=np.__version__, platform=platform.platform(),
                   numpy_config=str(np.show_config(mode='dicts')),
                   command=[sys.executable, *sys.argv], methods={})
    # Baseline predictions and per-user scores are checked against source CSV truth.
    base_predictions = baseline_predictions(source / 'baseline/predictions.csv')
    base_metrics = load(source / 'baseline/metrics.json')
    assert set(base_predictions) == {'popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell'}
    for method, rankings in base_predictions.items():
        records = [r for r in read_csv(source / 'baseline/per_user.csv') if r['method'] == method]
        assert list(rankings) == users and [r['user_id'] for r in records] == users
        for r in records:
            uid = r['user_id']
            st.validate_ranking(rankings[uid], assets)
            assert int(r['relevant_count']) == len(truth.get(uid, set()))
            assert float(r['ndcg_at_10']) == st.ndcg10(rankings[uid], truth.get(uid, set()))
        aggregate = st.aggregate([dict(ndcg_at_10=float(r['ndcg_at_10']),
                                      relevant_count=int(r['relevant_count'])) for r in records])
        assert aggregate == base_metrics['methods'][method]
        summary['methods'][method] = dict(saved_rankings_and_metrics_verified=True, aggregate=aggregate)
    pop = st.popularity_scores(history, assets)
    rebuilt, vocabulary = structured_vectors(profiles, neighbors)
    for method in ('structured_knn', 'qwen_knn'):
        target = enc / method
        vectors = np.load(target / 'vectors.npy', allow_pickle=False)
        assert vectors.dtype == np.float32 and vectors.shape[0] == len(neighbors)
        if method == 'structured_knn':
            assert vocabulary == load(target / 'vocabulary.json')
            assert np.array_equal(vectors, rebuilt)
        else:
            assert vectors.shape[1] == 1024
        rankings, diagnostics = recommend(vectors, neighbors, users, history, assets, pop)
        saved = baseline_predictions(target / 'predictions.csv')[method]
        saved_records = read_csv(target / 'per_user.csv')
        assert list(saved) == users and [r['user_id'] for r in saved_records] == users
        records, predictions, differences = [], [], []
        for uid, old in zip(users, saved_records):
            st.validate_ranking(rankings[uid], assets)
            score = st.ndcg10(rankings[uid], truth.get(uid, set()))
            assert int(old['relevant_count']) == len(truth.get(uid, set()))
            assert float(old['ndcg_at_10']) == st.ndcg10(saved[uid], truth.get(uid, set()))
            records.append(dict(user_id=uid, method=method, relevant_count=len(truth.get(uid, set())), ndcg_at_10=score))
            predictions.extend(dict(method=method, user_id=uid, rank=r, ISIN=i)
                               for r, i in enumerate(rankings[uid], 1))
            if rankings[uid] != saved[uid]:
                differences.append(dict(user_id=uid, saved=saved[uid], rescored=rankings[uid],
                                        saved_ndcg=float(old['ndcg_at_10']), rescored_ndcg=score))
        aggregate = st.aggregate(records)
        result = dict(shape=list(vectors.shape), dtype=str(vectors.dtype), aggregate=aggregate,
                      saved_aggregate=load(target / 'metrics.json')['aggregate'],
                      identical_top10_users=len(users) - len(differences), differences=differences,
                      identical_per_user_scores=sum(float(o['ndcg_at_10']) == r['ndcg_at_10']
                                                    for o, r in zip(saved_records, records)),
                      invalid_embedding_rows=diagnostics['invalid_embedding_rows'],
                      fallback_users=sum(d['fallback'] for d in diagnostics['users'].values()))
        out = args.output_dir / method
        out.mkdir()
        csv_save(out / 'predictions.csv', predictions)
        csv_save(out / 'per_user.csv', records)
        save(out / 'diagnostics.json', diagnostics)
        save(out / 'comparison.json', result)
        summary['methods'][method] = result
        print(method, json.dumps(result, ensure_ascii=False))
    save(args.output_dir / 'verification.json', summary)


if __name__ == '__main__':
    main()
