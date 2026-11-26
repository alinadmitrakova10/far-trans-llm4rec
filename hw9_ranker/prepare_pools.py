"""Freeze the selected pool and past-only feature payloads for all HW9 cutoffs."""

import argparse
from collections import Counter
import csv
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

from pools import (ROOT, build_pool, candidate_sources, coverage, load_slice, pool_rows,
                   read_json, sha256, starter, verified_inputs, write_json)


HW8 = ROOT.parent / 'hw8' / 'daria_babikova' / 'hw2'
sys.path.insert(0, str(HW8 / 'scripts'))
from input_contract import alias, canonical, common_payload


def prepare_slice(out, data_dir, cutoff, role, cfg, shared, selection):
    started = time.perf_counter()
    is_development = role == 'development'
    horizon = None if is_development else cfg['methods']['lambdamart']['label_horizon_days']
    snapshot = load_slice(data_dir, cutoff, horizon_days=horizon)
    cohort = cfg['development'] if is_development else cfg['pool_selection']
    users = starter.select_users(snapshot.profiles, snapshot.history, cohort['cohort'], cohort['users'], None)
    if len(users) != cohort['users']:
        raise ValueError(f'Unexpected cohort size at {cutoff}')
    if is_development and (snapshot.truth is not None or users != shared['users'] or
                           set(snapshot.assets) != set(shared['eligible_assets'])):
        raise ValueError('Development must match shared cohort/catalog and have no labels')
    rule = selection['winner']
    rows, groups, mappings = [], [], []
    payload_sources = []
    lengths, source_counts = Counter(), Counter()
    zero_cbf = 0
    for uid, sources, has_cbf_signal in candidate_sources(snapshot, users):
        zero_cbf += not has_cbf_signal
        pool = build_pool(rule, sources, snapshot.assets)
        lengths[len(pool)] += 1
        source_counts.update(source for _, source in pool)
        rows.extend(pool_rows(rule, uid, pool))
        payload_sources.append((uid, [isin for isin, _ in pool], sources['cbf']))

    pool_path = out / f'pools_{cutoff}.csv'
    with pool_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['method', 'user_id', 'rank', 'ISIN', 'source'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    assembly_seconds = time.perf_counter() - started
    if role == 'validation':
        actual = coverage(rows, users, snapshot.truth)
        if any(value != selection['metrics'][rule][name] for name, value in actual.items()):
            raise ValueError('Rebuilt May pools disagree with the committed selection run')

    started = time.perf_counter()
    payload_path = out / f'payloads_{cutoff}.jsonl'
    with payload_path.open('wb') as stream:
        for index, (uid, isins, cbf) in enumerate(payload_sources, 1):
            key = f'U{index:03d}' if is_development else f'{cutoff}:U{index:04d}'
            payload = common_payload(key, cutoff, snapshot.assets, snapshot.profiles[uid],
                                     snapshot.history[uid], snapshot.last_buy[uid], isins)
            cbf_ranks = {isin: rank for rank, isin in enumerate(cbf, 1)}
            for item, isin in zip(payload['candidates'], isins, strict=True):
                item['source_cbf_rank'] = cbf_ranks.get(isin)
            stream.write(canonical(payload) + b'\n')
            if snapshot.truth is not None:
                relevant = snapshot.truth.get(uid, set())
                groups.append({'group_key': key, 'candidate_aliases': [alias(isin) for isin in isins],
                               'labels': [int(isin in relevant) for isin in isins],
                               'full_truth_count': len(relevant)})
                mappings.append({'group_key': key, 'pool_isins': isins})
    payload_seconds = time.perf_counter() - started
    files = [pool_path, payload_path]
    if snapshot.truth is not None:
        labels_path = out / f'labels_{cutoff}.json'
        write_json(labels_path, {'groups': groups, 'mappings': mappings})
        files.append(labels_path)
    return {'role': role, 'cutoff': cutoff, 'users': len(users), 'groups': len(payload_sources),
            'pool_lengths': dict(sorted(lengths.items())), 'source_counts': dict(source_counts),
            'zero_cbf_signal_users': zero_cbf, 'assembly_seconds': assembly_seconds,
            'payload_seconds': payload_seconds, 'files_sha256': {p.name: sha256(p) for p in files}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    stage = ROOT / 'outputs' / 'stage2'
    final = stage / 'pools'
    if final.exists():
        raise FileExistsError('Candidate pools are frozen and will not be overwritten')
    cfg, shared = verified_inputs(args.data_dir, args.package)
    selection_path = stage / 'may_selection.json'
    selection = read_json(selection_path)
    winner = selection['winner']
    decisions = (ROOT / 'DECISIONS.md').read_text(encoding='utf-8')
    if (winner not in cfg['pool_selection']['eligible_pools'] or f'выбран `{winner}`' not in decisions
            or selection['shared_protocol_hash'] != shared['protocol_hash']
            or selection['cutoff'] != cfg['pool_selection']['cutoff']):
        raise ValueError('Candidate construction requires the recorded May decision')

    lm = cfg['methods']['lambdamart']
    cuts = [(cut, 'train') for cut in lm['train_cutoffs']]
    cuts += [(lm['validation_cutoff'], 'validation'), (cfg['development']['cutoff'], 'development')]
    with TemporaryDirectory(dir=stage, prefix='prepare-') as scratch:
        prepared = Path(scratch) / 'pools'
        prepared.mkdir()
        slices = []
        for cutoff, role in cuts:
            result = prepare_slice(prepared, args.data_dir, cutoff, role, cfg, shared, selection)
            slices.append(result)
            print(f'{cutoff} {role}: users={result["users"]}, groups={result["groups"]}, '
                  f'pool_lengths={result["pool_lengths"]}, sources={result["source_counts"]}, '
                  f'pool_sha256={result["files_sha256"][f"pools_{cutoff}.csv"]}, '
                  f'assembly={result["assembly_seconds"]:.4f} s', flush=True)
        write_json(prepared / 'manifest.json', {'rule': winner, 'protocol_hash': shared['protocol_hash'],
                   'may_selection_sha256': sha256(selection_path), 'slices': slices})
        prepared.rename(final)


if __name__ == '__main__':
    main()
