"""Evaluate completed Stage 4 rankings against the frozen June development truth."""

import argparse
from collections import defaultdict
import csv
import math
from pathlib import Path
import time

from pools import ROOT, coverage, read_json, sha256, starter, verified_inputs, write_json
from stage3_bundle import POOL_SHA
from stage3_runtime import read_jsonl
from stage4_integrity import STAGE4, require
from stage4_prepare import HW8, csv_rows, ordered_pools, position_overlap
from verify_hw8 import rankings


METHODS = ('popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell', 'u1_order', 'lambdamart_u1',
           'llm_u1', 'llm_u1_valid', 'llmrank', 'candidate_order_first10', 'hw8_cbf20',
           'hw8_lambdamart', 'hw8_llm_original', 'hw8_llm_permuted')
ABLATIONS = ('ablation_seed0', 'ablation_seed1', 'ablation_seed2')
PAIRWISE = (('llm_u1', 'u1_order'), ('llm_u1', 'lambdamart_u1'), ('lambdamart_u1', 'u1_order'),
            ('llm_u1', 'latest_buy'), ('lambdamart_u1', 'latest_buy'))
MANUAL_METHODS = ('u1_order', 'lambdamart_u1', 'llm_u1', 'latest_buy')
TEAM = {'tfidf_knn': ('tfidf_top20.csv', '5bd3fc0b581fd48b88be1f088d0eb6b66d4b94a3c11546cd765c3f89a3797382'),
        'qwen_knn': ('qwen_top20.csv', 'e2bcd9c690b4990884330a59267c790434aa1f8443e22822c1c6ec274550c6c5')}


def mean(values):
    return math.fsum(values) / len(values) if values else None


def score_summary(ranking, truth):
    per_user = {uid: starter.ndcg10(items, truth[uid]) for uid, items in ranking.items()}
    active = [value for uid, value in per_user.items() if truth[uid]]
    hits = sum(bool(set(items) & truth[uid]) for uid, items in ranking.items())
    return per_user, {'users': len(per_user), 'buyers': len(active), 'all': mean(list(per_user.values())),
                      'buyers_ndcg': mean(active), 'buyers_hit': hits, 'users_hit': hits}


def compare(left, right, buyers):
    deltas = [left[uid] - right[uid] for uid in buyers]
    better = sum(delta > 1e-12 for delta in deltas)
    worse = sum(delta < -1e-12 for delta in deltas)
    return {'better': better, 'worse': worse, 'same': len(deltas) - better - worse}


def coverage_for(method, pools, users, truth):
    return coverage(({'method': method, 'user_id': uid, 'rank': rank, 'ISIN': isin}
                     for uid, pool in pools.items() for rank, isin in enumerate(pool, 1)), users, truth)


def team_diagnostics(cbf50, p0, u1, users, truth, eligible):
    result = {}
    for method, (filename, expected) in TEAM.items():
        path = ROOT / 'outputs' / 'team' / 'alina' / filename
        require(sha256(path) == expected, f'External pool changed: {method}')
        rows = csv_rows(path)
        require({row['method'] for row in rows} == {method}, f'External pool method mismatch: {method}')
        pool = ordered_pools(rows)
        require(set(pool) <= set(users) and all(len(items) <= 20 and set(items) <= eligible for items in pool.values()),
                f'External pool has noneligible candidates: {method}')
        result[method] = coverage(rows, users, truth)
        matched = {uid: cbf50[uid][:len(pool.get(uid, ()))] for uid in users}
        result[f'cbf_matched_{method}'] = coverage_for(f'cbf_matched_{method}', matched, users, truth)
    result['p0'] = coverage_for('p0', p0, users, truth)
    result['u1'] = coverage_for('u1', u1, users, truth)
    return result


def write_per_user(users, buyers, truth, pools, by_method, scores):
    with (STAGE4 / 'per_user.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['method', 'user_id', 'relevant_count', 'ndcg_at_10'])
        for method, values in scores.items():
            writer.writerows((method, uid, len(truth[uid]), repr(values[uid])) for uid in users if uid in values)
    with (STAGE4 / 'buyers_detail.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['user_id', 'relevant_count', 'relevant_in_U1',
                        *[f'{method}_hit_positions' for method in MANUAL_METHODS],
                        *[f'{method}_ndcg' for method in MANUAL_METHODS]])
        for uid in buyers:
            hits = [', '.join(f'{isin}:{rank}' for rank, isin in enumerate(by_method[method][uid], 1) if isin in truth[uid])
                    for method in MANUAL_METHODS]
            writer.writerow([uid, len(truth[uid]), len(set(pools[uid]) & truth[uid]), *hits,
                             *[f'{scores[method][uid]:.4f}' for method in MANUAL_METHODS]])


def hand_packet(uid, protocol, by_method):
    path = STAGE4 / 'hand_check_packet.md'
    if uid is None:
        return None
    rows = ['# Ручная проверка Дарьи', '', f'Пользователь: `{uid}`. Зафиксированный `protocol_hash`: `{protocol["protocol_hash"]}`.', '',
            'В `transactions.csv` оставь строки, удовлетворяющие всем условиям:', '',
            f'- `customerID == {uid}`', '- `transactionType == Buy`',
            '- `2021-06-01 <= timestamp[:10] < 2021-07-01`', '- `int(transactionID) >= 0`',
            '- `ISIN` входит в `eligible_assets` замороженного `protocol.json` из `outputs/stage3/bundle.zip`.', '',
            'Удали точные дубликаты строк и используй множество различных ISIN из оставшихся Buy-строк.', '',
            '| Ранг | LLM U1 | Исходный порядок U1 |', '| ---: | --- | --- |']
    rows.extend(f'| {i} | `{a}` | `{b}` |' for i, (a, b) in enumerate(
        zip(by_method['llm_u1'][uid], by_method['u1_order'][uid], strict=True), 1))
    rows.extend(['', 'Для каждой выдачи рассчитай `DCG@10 = Σ_r rel(r) / log2(r + 1)`, где `r` от 1 до 10.',
                 '`IDCG@10 = Σ_{r=1}^{min(10, |truth|)} 1 / log2(r + 1)`, включая все eligible покупки вне пула.',
                 '`nDCG@10 = DCG@10 / IDCG@10` (0 при `IDCG = 0`). Готовые значения для сверки находятся в `per_user.csv`.'])
    path.write_text('\n'.join(rows) + '\n', encoding='utf-8', newline='\n')
    return sha256(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    pre = read_json(STAGE4 / 'prelabels.json')
    path = STAGE4 / 'predictions.csv'
    require(sha256(path) == pre['predictions_sha256'], 'Pre-label predictions changed')
    cfg, protocol = verified_inputs(args.data_dir, args.package)
    require(protocol['protocol_hash'] == pre['protocol_hash'], 'Pre-label protocol mismatch')
    users = protocol['users']
    cutoff = protocol['cutoff']
    pool_path = ROOT / 'outputs' / 'stage2' / 'pools' / f'pools_{cutoff}.csv'
    require(sha256(pool_path) == POOL_SHA, 'U1 pool changed')
    pools = ordered_pools(csv_rows(pool_path))
    contexts = read_jsonl(ROOT / 'outputs' / 'stage0_baselines' / 'contexts.jsonl')
    cbf50 = {row['user_id']: [item['id'] for item in row['candidate_assets']] for row in contexts}
    p0 = {uid: pool[:20] for uid, pool in cbf50.items()}
    grouped = defaultdict(list)
    for row in csv_rows(path):
        grouped[row['method']].append(row)
    by_method = {method: rankings(rows, 'user_id') for method, rows in grouped.items()}
    by_method.setdefault('llm_u1_valid', {})
    require(by_method.keys() == set(METHODS) | set(ABLATIONS), 'Prediction methods differ')
    require(all(list(by_method[m]) == users for m in by_method if m != 'llm_u1_valid') and
            list(by_method['llm_u1_valid']) == pre['valid']['llm_u1'], 'Prediction cohort order differs')

    start = time.perf_counter()
    assets, profiles, history, truth_map, end, _ = starter.load_data(args.data_dir, cutoff, cfg['development']['horizon_days'])
    eligible = set(assets)
    require(set(protocol['eligible_assets']) == eligible and end == protocol['end_exclusive'] and
            starter.select_users(profiles, history, 'warm', 100, None) == users, 'June label protocol mismatch')
    truth = {uid: truth_map.get(uid, set()) & eligible for uid in users}
    buyers = [uid for uid in users if truth[uid]]
    require(len(buyers) == 11 and sum(map(len, truth.values())) == 18, 'June buying cohort or pair count differs')
    load_seconds = time.perf_counter() - start
    start = time.perf_counter()
    scores, metrics = {}, {}
    for method, ranking in by_method.items():
        require(all(set(items) <= eligible for items in ranking.values()), f'Ineligible ranking item: {method}')
        scores[method], metrics[method] = score_summary(ranking, truth)

    expected = read_json(ROOT / 'outputs' / 'stage0_baselines' / 'metrics.json')
    require(expected['protocol_hash'] == protocol['protocol_hash'], 'Stage 0 protocol mismatch')
    baseline_differences = [m for m in METHODS[:4] if not all(math.isclose(metrics[m][key], expected['methods'][m][old],
                            rel_tol=0, abs_tol=1e-14) for key, old in [('all','ndcg_at_10'), ('buyers_ndcg','ndcg_at_10_nonempty')])]
    historical = read_json(HW8 / 'JUNE_RESULTS.json')
    historic = {'hw8_cbf20': historical['cbf20_reference'], 'hw8_lambdamart': historical['primary_lambdamart'],
                'hw8_llm_original': historical['llm_metrics']['original'],
                'hw8_llm_permuted': historical['llm_metrics']['permuted']}
    require(all(math.isclose(metrics[m]['all'], record['ndcg_at_10'], abs_tol=1e-14)
                for m, record in historic.items()), 'Saved HW8 metrics differ')

    pairwise = {f'{a} vs {b}': compare(scores[a], scores[b], buyers) for a, b in PAIRWISE}
    ablation = {}
    for method in ABLATIONS:
        accepted = pre['valid'][method]
        _, valid_metrics = score_summary({uid: by_method[method][uid] for uid in accepted}, truth)
        ablation[method] = {'changed': sum(by_method[method][uid] != by_method['llm_u1'][uid] for uid in users),
                            'overlap': mean([position_overlap(by_method[method][uid], by_method['llm_u1'][uid]) for uid in users]),
                            'comparison': compare(scores[method], scores['llm_u1'], buyers), 'valid_metrics': valid_metrics}
    averaged = {uid: mean([scores[m][uid] for m in ABLATIONS]) for uid in users}
    ablation['mean'] = {'all': mean(list(averaged.values())), 'buyers_ndcg': mean([averaged[uid] for uid in buyers]),
                        'comparison': compare(averaged, scores['llm_u1'], buyers),
                        'changed': mean([ablation[m]['changed'] for m in ABLATIONS]),
                        'overlap': mean([ablation[m]['overlap'] for m in ABLATIONS]),
                        'fallback_total': sum(pre['stats'][m]['fallback'] for m in ABLATIONS),
                        'fallback_users': len(set(users) - set.intersection(*(set(pre['valid'][m]) for m in ABLATIONS)))}

    team = team_diagnostics(cbf50, p0, pools, users, truth, eligible)
    changed_buyers = [uid for uid in buyers if by_method['llm_u1'][uid] != by_method['u1_order'][uid]]
    selected = changed_buyers[0] if changed_buyers else None
    detailed_example = None
    for uid in sorted(changed_buyers, key=lambda item: item == selected):
        if abs(scores['llm_u1'][uid] - scores['u1_order'][uid]) <= 1e-12:
            continue
        movements = []
        for asset in sorted(truth[uid] & set(pools[uid])):
            origin = pools[uid].index(asset) + 1
            prediction = by_method['llm_u1'][uid]
            movements.append({'pool_rank': origin, 'llm_rank': prediction.index(asset) + 1 if asset in prediction else None})
        detailed_example = {'moves': movements, 'u1_ndcg': scores['u1_order'][uid],
                            'llm_ndcg': scores['llm_u1'][uid], 'same_as_hand_check': uid == selected}
        break
    metrics_seconds = time.perf_counter() - start
    write_per_user(users, buyers, truth, pools, by_method, scores)
    packet_sha = hand_packet(selected, protocol, by_method)
    example_path = STAGE4 / 'buyer_example_after_hand_check.md'
    if detailed_example is not None:
        text = ['# Подробный пример после ручной проверки', '',
                'Открывай после самостоятельной сверки, если этот пример совпал с проверочным случаем.', '',
                f'Этот пример совпадает с проверочным случаем: {"да" if detailed_example["same_as_hand_check"] else "нет"}.',
                '', '| Позиция купленного актива в U1 | Позиция в top-10 LLM |', '| ---: | ---: |']
        text.extend(f'| {row["pool_rank"]} | {row["llm_rank"] or "вне top-10"} |' for row in detailed_example['moves'])
        text += ['', f'nDCG@10 исходного U1: {detailed_example["u1_ndcg"]:.4f}. '
                    f'nDCG@10 LLM: {detailed_example["llm_ndcg"]:.4f}.']
        example_path.write_text('\n'.join(text) + '\n', encoding='utf-8', newline='\n')
    write_json(STAGE4 / 'summary.json', {'metrics': metrics, 'baseline_differences': baseline_differences,
               'pairwise': pairwise, 'ablation': ablation, 'team': team, 'unchanged_users': len(users)-pre['change_vs_u1'],
               'unchanged_buyers': len(buyers)-len(changed_buyers),
               'example_sha256': sha256(example_path) if detailed_example else None,
               'packet_sha256': packet_sha, 'label_load_seconds': load_seconds, 'metrics_seconds': metrics_seconds})
    print('June development score complete. Aggregate summary saved. Stage 0 differences:', baseline_differences)


if __name__ == '__main__':
    main()
