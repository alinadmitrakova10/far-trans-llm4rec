"""Verify train protocols and choose a TF-IDF fill rule using the May slice."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path

from pools import ROOT, coverage, load_slice, pool_rows, read_json, sha256, starter, write_json
from prepare_pools import alias


OUT = ROOT / 'outputs'
TRAIN_CUTOFFS = ('2021-01-01', '2021-03-01', '2021-04-01')
MAY = '2021-05-01'
MAY_HASH = '91a91a8784134602b3427119d5f5859cb05509340ae0c33267d0de6d4cd3eb4e'
MAY_SHA = '95172edefe9453b760daaae0630d375405afc09e0521eee2fec56060376952ea'
TFIDF_SHA = 'a3138e5a6e86ee179cb07f19f0121ebcbd3a8956b6d5b708dcce75662374c8a5'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_pool(path, method, eligible):
    grouped = defaultdict(dict)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            rank, isin = int(row['rank']), row['ISIN']
            slots = grouped[row['user_id']]
            require(row['method'] == method and isin in eligible and rank not in slots,
                    f'{path.name}: invalid method, asset or duplicate rank')
            slots[rank] = isin
    pools = {}
    for uid, slots in grouped.items():
        require(0 < len(slots) <= 20 and set(slots) == set(range(1, len(slots) + 1))
                and len(set(slots.values())) == len(slots), f'{path.name}: invalid pool length or order')
        pools[uid] = [slots[rank] for rank in range(1, len(slots) + 1)]
    return pools


def checked_protocol(path, cutoff, source_hashes):
    data = read_json(path)
    expected = {key: value for key, value in data.items() if key != 'protocol_hash'}
    require(hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest() == data['protocol_hash'],
            f'{cutoff}: invalid protocol hash')
    require(data['cutoff'] == cutoff and data['end_exclusive'] ==
            (date.fromisoformat(cutoff) + timedelta(days=30)).isoformat() and
            data['source_sha256'] == source_hashes and data['cohort_selection'] == 'warm' and
            data['candidate_count'] == 50 and data['exclude_seen'] is False and data['k'] == 10 and
            len(data['users']) == len(set(data['users'])) == 1000, f'{cutoff}: unexpected protocol settings')
    return data


def stage2_users(cutoff, eligible, entry, directory):
    pool = directory / f'pools_{cutoff}.csv'
    payloads = directory / f'payloads_{cutoff}.jsonl'
    labels = directory / f'labels_{cutoff}.json'
    for path in (pool, payloads, labels):
        require(sha256(path) == entry['files_sha256'][path.name], f'{path.name}: Stage 2 digest changed')
    u1 = read_pool(pool, 'U1', eligible)
    groups = read_json(labels)
    count = 0
    with payloads.open(encoding='utf-8') as stream:
        for count, (uid, group, mapping, line) in enumerate(
                zip(u1, groups['groups'], groups['mappings'], stream, strict=True), 1):
            key = f'{cutoff}:U{count:04d}'
            payload = json.loads(line)
            aliases = [alias(isin) for isin in u1[uid]]
            require(group['group_key'] == mapping['group_key'] == payload['user_alias'] == key and
                    payload['cutoff'] == cutoff and mapping['pool_isins'] == u1[uid] and
                    group['candidate_aliases'] == [row['asset_alias'] for row in payload['candidates']] == aliases
                    and len(group['labels']) == len(aliases) == 20, f'{cutoff}: Stage 2 group order differs')
    require(count == entry['users'] == entry['groups'] == 1000, f'{cutoff}: Stage 2 group count differs')
    return u1


def build_hybrid(prefix, fill):
    pool = [(isin, 'tfidf') for isin in prefix]
    seen = set(prefix)
    for isin in fill:
        if len(pool) == 20:
            break
        if isin not in seen:
            pool.append((isin, 'fill'))
            seen.add(isin)
    return pool


def summarize(method, pools, users, truth):
    data = coverage((row for uid in users for row in pool_rows(method, uid, pools[uid])), users, truth)
    hits = Counter(source for uid in users for isin, source in pools[uid] if isin in truth.get(uid, ()))
    data['hits_by_source'] = {source: hits[source] for source in ('tfidf', 'fill', 'u1')}
    data['mean_share'] = {
        source: math.fsum(sum(origin == source for _, origin in pool) / len(pool) if pool else 0
                          for pool in pools.values()) / len(users)
        for source in ('tfidf', 'fill', 'u1')
    }
    data['empty_pools'] = sum(not pool for pool in pools.values())
    require(sum(hits.values()) == data['covered_pairs'], 'Source coverage does not sum to total')
    return data


def run(data_dir):
    received = OUT / 'team' / 'alina' / 'may'
    may_path = received / 'protocol.json'
    tfidf_path = received / 'tfidf_top20.csv'
    require(sha256(may_path) == MAY_SHA and sha256(tfidf_path) == TFIDF_SHA and
            may_path.read_bytes() == (OUT / 'may_protocol' / 'protocol.json').read_bytes(),
            'Unexpected May input digest')
    source_hashes = read_json(may_path)['source_sha256']
    require(all(sha256(data_dir / name) == digest for name, digest in source_hashes.items()),
            'FAR-Trans source changed')
    may = checked_protocol(may_path, MAY, source_hashes)
    require(may['protocol_hash'] == MAY_HASH, 'Unexpected May protocol hash')

    pool_dir = OUT / 'stage2' / 'pools'
    train_manifest = read_json(OUT / 'stage2' / 'lambdamart' / 'manifest.json')
    manifest_path = pool_dir / 'manifest.json'
    require(sha256(manifest_path) == train_manifest['pools_manifest_sha256'], 'Stage 2 pools manifest changed')
    entries = {entry['cutoff']: entry for entry in read_json(manifest_path)['slices']}
    require(tuple(cut for cut, info in entries.items() if info['role'] == 'train') == TRAIN_CUTOFFS and
            entries[MAY]['role'] == 'validation', 'Stage 2 split differs')
    protocols = {}
    for cutoff in TRAIN_CUTOFFS:
        path = OUT / 'final_protocols' / cutoff / 'protocol.json'
        protocol = checked_protocol(path, cutoff, source_hashes)
        u1 = stage2_users(cutoff, set(protocol['eligible_assets']), entries[cutoff], pool_dir)
        require(list(u1) == protocol['users'], f'{cutoff}: starter user order differs from LambdaMART')
        protocols[cutoff] = {'protocol_hash': protocol['protocol_hash'], 'sha256': sha256(path), 'users': len(u1)}
    print(json.dumps({'train_protocols': protocols}, indent=2), flush=True)

    users = may['users']
    eligible = set(may['eligible_assets'])
    u1 = stage2_users(MAY, eligible, entries[MAY], pool_dir)
    require(list(u1) == users, 'May U1 order differs from the May protocol')
    tfidf = read_pool(tfidf_path, 'tfidf_knn', eligible)
    require(set(tfidf) <= set(users), 'TF-IDF contains users outside the May protocol')
    snapshot = load_slice(data_dir, MAY, horizon_days=30)
    require(set(snapshot.assets) == eligible and starter.select_users(snapshot.profiles, snapshot.history,
            'warm', 1000, None) == users, 'Rebuilt May cohort or catalog differs')
    truth = snapshot.truth
    popularity = starter.order(starter.popularity_scores(snapshot.history, snapshot.assets))

    pools = {
        'D0': {uid: build_hybrid(tfidf.get(uid, ()), ()) for uid in users},
        'D1': {uid: build_hybrid(tfidf.get(uid, ()), u1[uid]) for uid in users},
        'D2': {uid: build_hybrid(tfidf.get(uid, ()), popularity) for uid in users},
        'U1': {uid: [(isin, 'u1') for isin in u1[uid]] for uid in users},
    }
    require(all(len(pool) == 20 for rule in ('D1', 'D2') for pool in pools[rule].values()),
            'A hybrid pool could not reach size 20')
    metrics = {name: summarize(name, group, users, truth) for name, group in pools.items()}
    require(all(item['all_pairs'] == 366 and item['all_buyers'] == 171 for item in metrics.values()),
            'Unexpected May truth counts')
    selection = read_json(OUT / 'stage2' / 'may_selection.json')['metrics']['U1']
    require(all(metrics['U1'][name] == selection[name] for name in
                ('covered_pairs', 'buyers_hit', 'oracle_all', 'oracle_buyers', 'mean_size')),
            'May U1 does not reproduce Stage 2')
    keys = {rule: (metrics[rule]['covered_pairs'], metrics[rule]['hits_by_source']['tfidf']) for rule in ('D1', 'D2')}
    winner = max(keys, key=keys.get) if keys['D1'] != keys['D2'] else None
    result = {'train_protocols': protocols, 'may': metrics, 'winner': winner}
    write_json(OUT / 'final_protocols' / 'stage6_summary.json', result)
    print(json.dumps({'may': metrics, 'winner': winner}, indent=2))
    require(winner is not None, 'Both registered criteria tied; no winner was selected')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--data-dir', required=True, type=Path)
    run(cli.parse_args().data_dir)
