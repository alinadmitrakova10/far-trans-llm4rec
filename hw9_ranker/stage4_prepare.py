"""Build Stage 4 rankings and parser diagnostics without June labels."""

import argparse
from collections import Counter
import csv
import json
import math
import re
import sys
import time
from pathlib import Path
from zipfile import ZipFile

from pools import ROOT, load_slice, read_json, sha256, starter, verified_inputs, write_json
from stage3_bundle import POOL_SHA, PAYLOAD_SHA
from stage3_runtime import SETS, read_jsonl
from stage4_integrity import NOTEBOOK, RESULTS, STAGE3, STAGE4, require
from prepare_pools import HW8, alias
from verify_hw8 import rankings
import llm_ranker


SETS_METHODS = dict(zip(SETS, ('llm_u1', 'ablation_seed0', 'ablation_seed1', 'ablation_seed2'), strict=True))
HW8_RESULTS = HW8.parent / 'results'
MODEL_SHA = 'eaf2141152b2e22d19f0f360b3bacd58ffb3e726394ab345f0862933c2ec9c6a'
MATRIX_SHA = '41888f40fca6443b784aaf69f0c4e2dfe98641f7ae63e050748fb0e49ee46372'


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def ordered_pools(rows):
    groups = {}
    for row in rows:
        pool = groups.setdefault(row['user_id'], [])
        require(int(row['rank']) == len(pool) + 1 and row['ISIN'] not in pool, 'Pool row order or uniqueness mismatch')
        pool.append(row['ISIN'])
    return groups


def diagnostics(raw, allowed, error, capped):
    """Label error symptoms without altering, repairing or accepting a response."""
    classes = []
    text = raw.strip()
    fenced = '```' in text
    if fenced:
        classes.append('markdown')
    try:
        value = json.loads(text)
    except ValueError:
        match = re.search(r'\[', text)
        value = None
        if match:
            try:
                value, length = json.JSONDecoder().raw_decode(text[match.start():])
            except ValueError:
                pass
            else:
                decoration = text[:match.start()] + text[match.start() + length:]
                if re.sub(r'```(?:json)?', '', decoration, flags=re.IGNORECASE).strip():
                    classes.append('explanatory_text')
        if not isinstance(value, list):
            classes.append('invalid_json')
    if isinstance(value, list):
        if len(value) != 10:
            classes.append('wrong_length')
        strings = [item for item in value if type(item) is str]
        if len(set(strings)) != len(strings):
            classes.append('duplicates')
        if any(item not in allowed for item in strings):
            classes.append('outside_aliases')
        if len(strings) != len(value):
            classes.append('other_structure')
    if capped:
        classes.append('token_cap')
    return classes or ['other_structure' if error != 'Not strict JSON' else 'invalid_json']


def parse_sets(users, pools):
    rankings_by_set, stats, valid, examples = {}, {}, {}, {}
    with ZipFile(STAGE3 / 'bundle.zip') as bundle:
        dictionaries = {row['id']: row for row in map(json.loads, bundle.read('aliases.jsonl').splitlines())}
        for name, method in SETS_METHODS.items():
            source = list(map(json.loads, bundle.read(f'{name}.jsonl').splitlines()))
            replies = read_jsonl(RESULTS / f'{name}.jsonl')
            ranking, accepted = {}, []
            counters, invalid, capped = Counter(), 0, 0
            for ordinal, (frozen, reply, uid) in enumerate(zip(source, replies, users, strict=True), 1):
                mapping = dictionaries[reply['id']]
                table = json.loads(frozen['prompt'].split('\n', 1)[1])
                candidates = [row[0] for row in table['candidate_rows']]
                keys = mapping['candidate_alias_to_isin']
                require(mapping['user_id'] == uid and set(keys) == set(candidates) and
                        [keys[key] for key in candidates] == pools[uid], 'Response candidate mapping differs from frozen pool')
                # Reconstruct the prompt's wire namespace as an identity mapping for the unchanged HW8 parser.
                wire = set(mapping['wire_to_asset_alias'])
                payload = {'candidates': [{'asset_alias': key} for key in candidates],
                           'history': [{'asset_alias': key} for key in sorted(wire - keys.keys())]}
                require(all(key == value for key, value in llm_ranker.wire_aliases(payload).items()), 'Noncanonical wire namespace')
                parsed = llm_ranker.parse_or_fallback(reply['text'], payload)
                ranking[uid] = [keys[key] for key in parsed['ranked_aliases']]
                cap = reply['output_tokens'] == 256
                capped += cap
                if parsed['invalid']:
                    invalid += 1
                    require(parsed['fallback'] and ranking[uid] == pools[uid][:10], 'Fallback changed from U1 top-10')
                    for category in diagnostics(reply['text'], keys, parsed['error'], cap):
                        counters[category] += 1
                        saved = examples.setdefault(category, [])
                        if len(saved) < 3:
                            saved.append({'example': len(saved) + 1, 'set': name, 'ordinal': ordinal,
                                          'output_tokens': reply['output_tokens'], 'raw_excerpt': reply['text'][:300]})
                else:
                    accepted.append(uid)
            rankings_by_set[method] = ranking
            valid[method] = accepted
            stats[method] = {'valid': len(accepted), 'invalid': invalid, 'fallback': invalid, 'repairs': 0,
                             'capped': capped, 'classes': dict(counters)}
    return rankings_by_set, stats, valid, examples


def score_lambdamart(pools, users, cutoff):
    import lightgbm as lgb
    from scipy import sparse

    stage = ROOT / 'outputs' / 'stage2'
    lm = stage / 'lambdamart'
    require(sha256(lm / 'model.txt') == MODEL_SHA and sha256(lm / 'development_X.npz') == MATRIX_SHA,
            'Frozen LambdaMART model/matrix digest differs')
    path = stage / 'pools' / f'payloads_{cutoff}.jsonl'
    require(sha256(path) == PAYLOAD_SHA, 'Frozen June payload digest differs')
    payloads = read_jsonl(path)
    for index, (payload, uid) in enumerate(zip(payloads, users, strict=True), 1):
        require(payload['user_alias'] == f'U{index:03d}' and
                [item['asset_alias'] for item in payload['candidates']] == [alias(isin) for isin in pools[uid]],
                'Matrix/candidate alignment differs')
    started = time.perf_counter()
    matrix = sparse.load_npz(lm / 'development_X.npz')
    model = lgb.Booster(model_file=str(lm / 'model.txt'))
    scores = model.predict(matrix, num_threads=4)
    require(len(scores) == sum(len(pool) for pool in pools.values()) and all(map(math.isfinite, scores)),
            'Unexpected LambdaMART score shape')
    result, offset = {}, 0
    for uid in users:
        pool = pools[uid]
        positions = sorted(range(len(pool)), key=lambda i: (-scores[offset+i], pool[i]))
        result[uid] = [pool[i] for i in positions[:10]]
        offset += len(pool)
    return result, time.perf_counter() - started


def hw8_rankings(users, p0):
    transfer = read_json(HW8.parent / 'TRANSFER_MANIFEST.json')['files_sha256']
    for name in ('evaluation_mappings.json', 'lambdamart_top10.csv', 'llm_top10.csv'):
        require(sha256(HW8_RESULTS / name) == transfer[f'results/{name}'], f'HW8 file changed: {name}')
    mappings = read_json(HW8_RESULTS / 'evaluation_mappings.json')
    require(len(mappings) == len(users), 'HW8 mapping size differs')
    keys = {}
    for index, (entry, uid) in enumerate(zip(mappings, users, strict=True), 1):
        require(entry['group_key'] == f'U{index:03d}' and entry['pool_isins'] == p0[uid], 'HW8 pool differs')
        keys[entry['group_key']] = uid
    llm = csv_rows(HW8_RESULTS / 'llm_top10.csv')
    reads = {'hw8_lambdamart': rankings(csv_rows(HW8_RESULTS / 'lambdamart_top10.csv'), 'group_key')}
    for branch in ('original', 'permuted'):
        reads[f'hw8_llm_{branch}'] = rankings([row for row in llm if row['branch'] == branch], 'user_alias')
    result = {method: {keys[key]: value for key, value in records.items()} for method, records in reads.items()}
    result['hw8_cbf20'] = {uid: p0[uid][:10] for uid in users}
    require(all(set(groups) == set(users) and all(set(ranking) <= set(p0[uid]) for uid, ranking in groups.items())
                for groups in result.values()), 'HW8 ranking has wrong cohort or candidates')
    return result


def position_overlap(left, right):
    return sum(a == b for a, b in zip(left, right)) / 10


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    integrity = read_json(STAGE4 / 'integrity.json')
    require(sha256(NOTEBOOK) == integrity['notebook_sha256'] and all(sha256(RESULTS / path) == expected
            for path, expected in integrity['files_sha256'].items()) and
            sha256(STAGE3 / 'bundle.zip') == integrity['bundle_sha256'], 'Artifacts changed since integrity phase')
    require(not (STAGE4 / 'prelabels.json').exists(), 'Pre-label ranking artifacts already exist')
    _, protocol = verified_inputs(args.data_dir, args.package)
    users, cutoff = protocol['users'], protocol['cutoff']
    pool_path = ROOT / 'outputs' / 'stage2' / 'pools' / f'pools_{cutoff}.csv'
    require(sha256(pool_path) == POOL_SHA, 'Frozen U1 pool changed')
    pools = ordered_pools(csv_rows(pool_path))
    require(list(pools) == users and all(len(pool) == 20 for pool in pools.values()), 'Unexpected frozen U1 pool')
    started = time.perf_counter()
    by_method, stats, valid, examples = parse_sets(users, pools)
    teacher_dir = RESULTS / 'teacher'
    teacher = read_json(teacher_dir / 'run_manifest.json')
    final = read_jsonl(teacher_dir / 'final_responses.jsonl')
    invalid = sum(row['error'] is not None for row in final)
    repairs = sum(row['parse_repaired'] for row in final)
    fallback = sum(row['fallback'] for row in final)
    require(invalid == teacher['runtime']['raw_invalid_count'] and repairs == teacher['runtime']['parse_repair_count']
            and fallback == len(teacher['failures']) and len(final) == 100, 'Teacher parser counters differ')
    stats['llmrank'] = {'valid': 100-invalid, 'invalid': invalid, 'fallback': fallback, 'repairs': repairs}
    parse_seconds = time.perf_counter() - started

    snapshot = load_slice(args.data_dir, cutoff)
    require(snapshot.truth is None and set(snapshot.assets) == set(protocol['eligible_assets']), 'Expected past only')
    require(starter.select_users(snapshot.profiles, snapshot.history, 'warm', 100, None) == users, 'Cohort differs')
    pop = starter.popularity_scores(snapshot.history, snapshot.assets)
    features = {isin: starter.tokens(row) for isin, row in snapshot.assets.items()}
    ctx, baseline = starter.contexts_for(users, snapshot.assets, snapshot.profiles, snapshot.history,
                                         features, pop, cutoff, 50, False)
    recent = starter.recency_rankings(ctx, pop, starter.scan_recent_events(args.data_dir, cutoff, snapshot.assets))
    for method in ('popularity', 'cbf', 'latest_buy', 'latest_buy_or_sell'):
        by_method[method] = {uid: (baseline[uid] | recent[uid])[method] for uid in users}
    contexts_path = ROOT / 'outputs' / 'stage0_baselines' / 'contexts.jsonl'
    cbf50 = {row['user_id']: [item['id'] for item in row['candidate_assets']] for row in read_jsonl(contexts_path)}
    require(list(cbf50) == users and all(len(pool) == len(set(pool)) == 50 for pool in cbf50.values()), 'Frozen CBF50 differs')
    p0 = {uid: cbf50[uid][:20] for uid in users}
    by_method.update(hw8_rankings(users, p0))
    teacher_rows = csv_rows(teacher_dir / 'predictions.csv')
    for method in ('llmrank', 'candidate_order_first10'):
        by_method[method] = rankings([row for row in teacher_rows if row['method'] == method], 'user_id')
        require(list(by_method[method]) == users, 'Teacher ranking order differs')
    by_method['u1_order'] = {uid: pools[uid][:10] for uid in users}
    by_method['lambdamart_u1'], lm_seconds = score_lambdamart(pools, users, cutoff)
    by_method['llm_u1_valid'] = {uid: by_method['llm_u1'][uid] for uid in valid['llm_u1']}
    differences = sum(by_method['llm_u1'][uid] != by_method['u1_order'][uid] for uid in users)
    overlap = {method: sum(position_overlap(by_method[method][uid], by_method['popularity'][uid]) for uid in users) / len(users)
               for method in ('llm_u1', 'u1_order', 'lambdamart_u1')}

    path = STAGE4 / 'predictions.csv'
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['method', 'user_id', 'rank', 'ISIN'])
        for method, records in by_method.items():
            for uid in users:
                writer.writerows((method, uid, rank, asset) for rank, asset in enumerate(records.get(uid, ()), 1))
    write_json(STAGE4 / 'invalid_examples.json', examples)
    write_json(STAGE4 / 'prelabels.json', {'protocol_hash': protocol['protocol_hash'], 'predictions_sha256': sha256(path),
               'stats': stats, 'valid': valid, 'change_vs_u1': differences, 'popularity_overlap': overlap,
               'parse_seconds': parse_seconds, 'lambdamart_score_seconds': lm_seconds})
    print(json.dumps({'stats': stats, 'llm_changed': differences, 'popularity_overlap': overlap}, ensure_ascii=False))


if __name__ == '__main__':
    main()
