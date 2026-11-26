"""Select the HW9 candidate rule using only the May validation window."""

import argparse
from collections import Counter
from pathlib import Path
import time

from pools import (ROOT, RULES, SOURCE_NAMES, build_pool, candidate_sources, coverage,
                   load_slice, pool_rows, starter, verified_inputs, write_json)


def may_table(metrics):
    lines = [
        '| Пул | Покрытые пары | Все пары | Покупатели с попаданием | Все покупатели | Потолок nDCG@10, все | Потолок, покупатели | Средний размер | CBF | Recency | Popularity |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for rule, row in metrics.items():
        shares = ' | '.join(f'{row["source_shares"][source]:.4f}' for source in SOURCE_NAMES)
        lines.append(f'| {rule} | {row["covered_pairs"]} | {row["all_pairs"]} | {row["buyers_hit"]} | '
                     f'{row["all_buyers"]} | {row["oracle_all"]:.4f} | {row["oracle_buyers"]:.4f} | '
                     f'{row["mean_size"]:.4f} | {shares} |')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    out = ROOT / 'outputs' / 'stage2' / 'may_selection.json'
    if out.exists():
        raise FileExistsError('May selection has already been saved')
    cfg, shared = verified_inputs(args.data_dir, args.package)
    may = cfg['pool_selection']
    started = time.perf_counter()
    snapshot = load_slice(args.data_dir, may['cutoff'], horizon_days=may['horizon_days'])
    users = starter.select_users(snapshot.profiles, snapshot.history, may['cohort'], may['users'], None)
    if len(users) != may['users']:
        raise ValueError('May cohort size differs from registered protocol')
    rows = {rule: [] for rule in RULES}
    zero_cbf = 0
    for uid, sources, has_cbf_signal in candidate_sources(snapshot, users):
        zero_cbf += not has_cbf_signal
        for rule in rows:
            pool = build_pool(rule, sources, snapshot.assets)
            rows[rule].extend(pool_rows(rule, uid, pool))
    assembly_seconds = time.perf_counter() - started
    metrics = {}
    for rule, items in rows.items():
        stats = coverage(items, users, snapshot.truth)
        counts = Counter(row['source'] for row in items)
        stats['source_shares'] = {source: counts[source] / len(items) if items else 0.0 for source in SOURCE_NAMES}
        metrics[rule] = stats
    priority = may['rule_priority']
    winner = min(may['eligible_pools'], key=lambda rule: (
        -metrics[rule]['covered_pairs'], -metrics[rule]['buyers_hit'], priority.index(rule)))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {'winner': winner, 'shared_protocol_hash': shared['protocol_hash'],
                     'cutoff': may['cutoff'], 'users': len(users), 'metrics': metrics,
                     'assembly_seconds': assembly_seconds, 'users_with_zero_cbf_signal': zero_cbf})
    print(may_table(metrics))
    print(f'Winner: {winner}; assembly: {assembly_seconds:.4f} s; zero CBF signal: {zero_cbf}')


if __name__ == '__main__':
    main()
