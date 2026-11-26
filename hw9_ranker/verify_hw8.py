"""Reconcile saved HW8 rankings against the shared FAR-Trans protocol."""

import argparse
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor' / 'far-trans'))
from starter import load_data


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rankings(rows, user_column):
    by_user = {}
    for row in rows:
        by_user.setdefault(row[user_column], []).append((int(row['rank']), row['ISIN']))
    result = {}
    for user, rows in by_user.items():
        ordered = sorted(rows)
        require([rank for rank, _ in ordered] == list(range(1, 11)), 'Invalid Top-10 ranks')
        result[user] = [asset for _, asset in ordered]
    return result


def score(ranking, truth):
    if not truth:
        return 0.0
    discounts = [1 / math.log2(rank + 2) for rank in range(10)]
    gain = sum(discount for discount, asset in zip(discounts, ranking) if asset in truth)
    return gain / sum(discounts[:len(truth)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hw8', type=Path, default=ROOT.parent / 'hw8' / 'daria_babikova')
    parser.add_argument('--hw8-data', type=Path, required=True, help='Original local data/hw2 directory')
    parser.add_argument('--stage0', type=Path, default=ROOT / 'outputs' / 'stage0_baselines')
    args = parser.parse_args()
    outputs = args.hw8 / 'results'
    pool_dir = args.hw8_data / 'cbf20'
    with ZipFile(args.hw8_data / 'inputs' / 'team5_alina_t4_protocol_check.zip') as archive:
        protocol = json.loads(archive.read('protocol.json'))
        contexts_raw = archive.read('contexts.jsonl')
    manifest = read_json(args.hw8 / 'hw2' / 'CANDIDATES.json')
    require(manifest['source_protocol_hash'] == protocol['protocol_hash'] ==
            read_json(args.stage0 / 'protocol.json')['protocol_hash'], 'Protocol hash mismatch')
    require(hashlib.sha256(contexts_raw).hexdigest() == manifest['source_contexts_sha256'],
            'Saved CBF50 contexts hash mismatch')
    for filename, expected in manifest['files_sha256'].items():
        require(hashlib.sha256((pool_dir / filename).read_bytes()).hexdigest() == expected,
                f'Saved CBF20 artifact hash mismatch: {filename}')

    users = protocol['users']
    contexts = [json.loads(line) for line in contexts_raw.splitlines()]
    saved20 = [json.loads(line) for line in (pool_dir / 'candidates.jsonl').read_bytes().splitlines()]
    require([row['user_id'] for row in contexts] == [row['user_id'] for row in saved20] == users,
            'Candidate cohorts differ')
    pools50 = {row['user_id']: [asset['id'] for asset in row['candidate_assets']] for row in contexts}
    pools20 = {row['user_id']: row['candidate_ids'] for row in saved20}
    require(all(len(set(pools50[user])) == len(pools50[user]) == 50 and
                pools50[user][:20] == pools20[user] for user in users), 'CBF20 is not the CBF50 prefix')
    cutoff = date.fromisoformat(protocol['cutoff'])
    horizon = (date.fromisoformat(protocol['end_exclusive']) - cutoff).days
    _, _, _, purchases, _, _ = load_data(args.hw8_data / 'stage1_verification' / 'data', cutoff.isoformat(), horizon)
    eligible = set(protocol['eligible_assets'])
    truth = {user: purchases[user] & eligible for user in users}
    active = [user for user in users if truth[user]]
    total_pairs = sum(map(len, truth.values()))
    require((len(users), len(active), total_pairs) == (100, 11, 18), 'Unexpected evaluation counts')

    groups = read_json(outputs / 'evaluation_groups.json')
    mappings = read_json(outputs / 'evaluation_mappings.json')
    require(len(groups) == len(mappings) == len(users), 'HW8 evaluation cohort size mismatch')
    aliases = {}
    for user, group, mapping in zip(users, groups, mappings):
        alias = mapping['group_key']
        require(alias == group['group_key'] and alias not in aliases and
                mapping['pool_isins'] == pools20[user] and group['full_truth_count'] == len(truth[user]) and
                group['labels'] == [int(asset in truth[user]) for asset in pools20[user]],
                'HW8 evaluation mapping or labels differ')
        aliases[alias] = user

    reference = rankings(read_csv(pool_dir / 'reference_predictions.csv'), 'user_id')
    require(reference == {user: pool[:10] for user, pool in pools20.items()}, 'CBF20 reference differs')
    llm = read_csv(outputs / 'llm_top10.csv')
    saved = {
        'lambdamart': rankings(read_csv(outputs / 'lambdamart_top10.csv'), 'group_key'),
        'original': rankings((row for row in llm if row['branch'] == 'original'), 'user_alias'),
        'permuted': rankings((row for row in llm if row['branch'] == 'permuted'), 'user_alias'),
    }
    require({row['branch'] for row in llm} == {'original', 'permuted'}, 'Unexpected LLM branch')
    by_method = {'cbf20': reference}
    for method, lists in saved.items():
        require(lists.keys() == aliases.keys(), f'{method} cohort mismatch')
        by_method[method] = {aliases[alias]: ranking for alias, ranking in lists.items()}
    scores = {}
    expected_metrics = {'cbf20': '0.0201', 'lambdamart': '0.0251', 'original': '0.0184', 'permuted': '0.0170'}
    for method, lists in by_method.items():
        require(all(len(set(ranking)) == 10 and set(ranking) <= set(pools20[user])
                    for user, ranking in lists.items()), f'{method} ranking outside CBF20 or duplicated')
        scores[method] = {user: score(lists[user], truth[user]) for user in users}
        all_users = math.fsum(scores[method].values()) / len(users)
        nonempty = math.fsum(scores[method][user] for user in active) / len(active)
        require(f'{all_users:.4f}' == expected_metrics[method], f'{method} nDCG mismatch: {all_users}')
        print(f'{method}: nDCG@10 {all_users:.4f} / {nonempty:.4f}')

    for name, pool in [('CBF20', pools20), ('CBF50', pools50)]:
        hits = [len(truth[user].intersection(pool[user])) for user in active]
        if name == 'CBF20':
            require(sum(hits) == 5 and sum(count > 0 for count in hits) == 5, 'CBF20 coverage mismatch')
        print(f'{name}: {sum(hits)}/{total_pairs} pairs, {sum(count > 0 for count in hits)}/{len(active)} users')

    for method, reference_method in [('original', 'cbf20'), ('permuted', 'cbf20'),
                                     ('lambdamart', 'cbf20'), ('original', 'lambdamart')]:
        differences = [scores[method][user] - scores[reference_method][user] for user in active]
        better = sum(delta > 1e-12 for delta in differences)
        worse = sum(delta < -1e-12 for delta in differences)
        print(f'{method} vs {reference_method}: {better} better / {worse} worse / {len(active) - better - worse} tie')


if __name__ == '__main__':
    main()
