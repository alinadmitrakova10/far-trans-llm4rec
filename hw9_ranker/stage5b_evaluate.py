"""Parse the frozen Stage 5 journals, then score them against the Stage 4 protocol."""

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from zipfile import ZipFile

from pools import ROOT, read_json, sha256, starter, verified_inputs, write_json
from stage3_bundle import POOL_SHA, llm_ranker
from stage3_runtime import read_jsonl
from stage4_integrity import STAGE3, STAGE4, require, sha_text
from stage4_prepare import csv_rows, diagnostics, ordered_pools, position_overlap
from stage4_score import compare, mean, score_summary
from verify_hw8 import rankings


OUT = ROOT / 'outputs' / 'stage5'
SETS = ('main_g', 'ablation_g_seed0', 'ablation_g_seed1', 'ablation_g_seed2')
BUNDLE_SHA = 'fcd96954ae85ae2b53bec2bff92e9b5750751a3425e1a2c760c1cfeea6a25ee2'
RESULT_SHA = '4168e1fb87f7cd403f035259625012edfb0cb72bec6aabad4e08fc3fa9c59a06'
STAGE4_SHA = {
    'predictions.csv': '78de037f9f3ed4ba3146f2d7f367ebe3bdae39442e32b4ac1b471818a40126fa',
    'buyers_detail.csv': '95ce833f3efd96168b2f4a0ff63d655fe1a867bab315d1eb0c894af79cd55cbe',
}
REFERENCES = ('u1_order', 'lambdamart_u1', 'latest_buy', 'llm_u1', 'popularity')


def verify_notebook(path, protocol, replies):
    """Inspect the exported notebook and leave its persisted outputs untouched."""
    doc = read_json(path)
    cells = [c for c in doc['cells'] if c['cell_type'] == 'code']
    require(len(cells) == 5 and all(c.get('execution_count') is not None for c in cells),
            'Expected five executed Kaggle code cells')
    outputs = [o for c in cells for o in c.get('outputs', [])]
    text = json.dumps([outputs, doc['metadata']], ensure_ascii=False)
    for value in (*protocol['users'], *protocol['eligible_assets'], *(r['id'] for r in replies)):
        require(not re.search(r'\b' + re.escape(value) + r'\b', text), 'User or asset identifier in notebook output')
    for key in ('user_id', 'candidate_rows', 'ranked_aliases', 'raw_response', 'prompt_sha256'):
        require(not re.search(r'(?<!\w)' + key + r'(?!\w)', text), 'Potential per-user data in notebook output')
    require(all(len(r['text']) < 16 or json.dumps(r['text'], ensure_ascii=False)[1:-1] not in text
                for r in replies), 'A model response appears in notebook output')
    require('400 frozen prompts' in text and 'Download from Output: hw9_posthoc_colab_results.zip' in text
            and all(f"{name} {{'skipped': 0, 'new': 100" in text for name in SETS),
            'Notebook outputs do not attest to this completed run')
    errors = [{'cell': i, 'type': out['ename'], 'message': out['evalue']}
              for i, cell in enumerate(cells, 1) for out in cell.get('outputs', []) if out['output_type'] == 'error']
    return {'sha256': sha256(path), 'execution_counts': [c['execution_count'] for c in cells], 'errors': errors}


def archived_inputs(notebook):
    path = OUT / 'bundle_posthoc.zip'
    archive = OUT / 'hw9_posthoc_colab_results.zip'
    require(sha256(path) == BUNDLE_SHA and sha256(archive) == RESULT_SHA, 'Archive digest changed')
    with ZipFile(STAGE3 / 'bundle.zip') as original:
        protocol = json.loads(original.read('protocol.json'))
    result_dir = OUT / 'colab_results'
    with ZipFile(archive) as result:
        files = {file.name: sha256(file) for file in result_dir.iterdir() if file.is_file()}
        require(len(result.namelist()) == len(files) == 7 and
                set(result.namelist()) == files.keys() and result.testzip() is None and
                all(hashlib.sha256(result.read(name)).hexdigest() == digest for name, digest in files.items()),
                'Local results differ from their archive')
    replies = {name: read_jsonl(result_dir / f'{name}.jsonl') for name in SETS}
    timing = read_jsonl(result_dir / 'timing.jsonl')
    identity = read_json(result_dir / 'run_identity.json')
    with ZipFile(path) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        require(protocol['protocol_hash'] == manifest['protocol_hash'] and manifest['pool_sha256'] == POOL_SHA,
                'Frozen pool or protocol mismatch')
        require(identity['bundle_sha256'] == BUNDLE_SHA and identity['generation'] == manifest['generation'] and
                identity['weight_sha256'] == manifest['model_files_sha256'] and
                identity['revision'] == manifest['generation']['revision'] and identity['gpu'] == 'Tesla T4',
                'Run identity mismatch')
        prompts = {name: [json.loads(line) for line in bundle.read(f'{name}.jsonl').splitlines()] for name in SETS}
        aliases = [json.loads(line) for line in bundle.read('aliases.jsonl').splitlines()]
    mapping = {row['id']: row for row in aliases}
    require(len(mapping) == len(aliases) == len(manifest['prompt_sha256']) == 400, 'Unexpected input counts')
    for name in SETS:
        require(len(prompts[name]) == len(replies[name]) == manifest['prompt_counts'][name] == 100,
                'Incomplete results')
        for i, (prompt, reply) in enumerate(zip(prompts[name], replies[name], strict=True), 1):
            key = f'{name}:U{i:03d}'
            require(prompt['id'] == reply['id'] == key and key in mapping and
                    reply['prompt_sha256'] == prompt['prompt_sha256'] == manifest['prompt_sha256'][key] ==
                    sha_text(prompt['prompt']), 'Frozen prompt or journal order differs')
        end = [row for row in timing if row['stage'] == name and row.get('event') == 'end']
        require(len(end) == 1 and end[0]['completed'] == end[0]['new'] == 100 and
                math.isclose(end[0]['new_generation_seconds'], math.fsum(r['seconds'] for r in replies[name]),
                             abs_tol=1e-9), 'Timing does not account for the saved generations')
    info = {'files_sha256': files, 'archive_sha256': RESULT_SHA, 'identity': identity, 'timing': timing,
            'notebook': verify_notebook(notebook, protocol, [r for rows in replies.values() for r in rows])
            if notebook is not None else None}
    return protocol, prompts, replies, mapping, info


def references(protocol):
    require(all(sha256(STAGE4 / name) == digest for name, digest in STAGE4_SHA.items()), 'Stage 4 results changed')
    path = ROOT / 'outputs' / 'stage2' / 'pools' / f'pools_{protocol["cutoff"]}.csv'
    require(sha256(path) == POOL_SHA, 'Frozen U1 changed')
    pools = ordered_pools(csv_rows(path))
    users = protocol['users']
    require(list(pools) == users and all(len(pool) == 20 for pool in pools.values()), 'U1 cohort differs')
    rows = csv_rows(STAGE4 / 'predictions.csv')
    fixed = {method: rankings([row for row in rows if row['method'] == method], 'user_id') for method in REFERENCES}
    require(all(list(groups) == users for groups in fixed.values()) and
            all(fixed['u1_order'][uid] == pools[uid][:10] for uid in users), 'Stage 4 reference ranks differ')
    return users, pools, fixed


def parse(notebook):
    protocol, prompts, replies, aliases, integrity = archived_inputs(notebook)
    users, pools, fixed = references(protocol)
    parsed_sets, stats, valid = {}, {}, {}
    for name in SETS:
        parsed_sets[name], valid[name] = {}, []
        classes = Counter()
        fallbacks = 0
        for uid, frozen, reply in zip(users, prompts[name], replies[name], strict=True):
            mapping = aliases[reply['id']]
            table = json.loads(frozen['prompt'].split('\n', 1)[1])
            candidates = [row[0] for row in table['candidate_rows']]
            keys = mapping['candidate_alias_to_isin']
            require(mapping['user_id'] == uid and set(keys) == set(candidates) and
                    [keys[key] for key in candidates] == pools[uid], 'Candidate mapping differs from frozen U1')
            wire = set(mapping['wire_to_asset_alias'])
            payload = {'candidates': [{'asset_alias': key} for key in candidates],
                       'history': [{'asset_alias': key} for key in sorted(wire - keys.keys())]}
            require(all(k == v for k, v in llm_ranker.wire_aliases(payload).items()), 'Noncanonical wire namespace')
            parsed = llm_ranker.parse_or_fallback(reply['text'], payload)
            items = [keys[key] for key in parsed['ranked_aliases']]
            require(len(items) == len(set(items)) == 10 and parsed['invalid'] == parsed['fallback'],
                    'Unexpected parser result')
            parsed_sets[name][uid] = items
            if parsed['fallback']:
                require(items == pools[uid][:10], 'Fallback differs from U1')
                fallbacks += 1
                classes.update(diagnostics(reply['text'], keys, parsed['error'], reply['output_tokens'] == 256))
            else:
                valid[name].append(uid)
        ranking = parsed_sets[name]
        tokens = [reply['output_tokens'] for reply in replies[name]]
        stats[name] = {'valid': len(valid[name]), 'invalid': 100 - len(valid[name]), 'fallback': fallbacks,
                       'classes': dict(classes), 'capped': tokens.count(256), 'median_output_tokens': median(tokens),
                       'changed_vs_u1': sum(ranking[uid] != fixed['u1_order'][uid] for uid in users),
                       'popularity_overlap': mean([position_overlap(ranking[uid], fixed['popularity'][uid])
                                                   for uid in users])}
    result = {'protocol_hash': protocol['protocol_hash'], 'integrity': integrity,
              'stats': stats, 'valid': valid, 'rankings': parsed_sets}
    write_json(OUT / 'prelabels_stage5b.json', result)
    print(json.dumps({'stats': stats, 'integrity': integrity}, ensure_ascii=False, indent=2))


def extend_buyer_details(buyers, truth, main, main_scores):
    previous = csv_rows(STAGE4 / 'buyers_detail.csv')
    require([row['user_id'] for row in previous] == buyers, 'Stage 4 buyer cohort differs')
    path = OUT / 'buyers_detail.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=[*previous[0], 'llm_posthoc_hit_positions', 'llm_posthoc_ndcg'],
                                lineterminator='\n')
        writer.writeheader()
        for uid, row in zip(buyers, previous, strict=True):
            hits = ', '.join(f'{asset}:{rank}' for rank, asset in enumerate(main[uid], 1) if asset in truth[uid])
            writer.writerow(dict(row, llm_posthoc_hit_positions=hits, llm_posthoc_ndcg=f'{main_scores[uid]:.4f}'))
    return sha256(path)


def evaluate(data_dir, package):
    pre = read_json(OUT / 'prelabels_stage5b.json')
    config, protocol = verified_inputs(data_dir, package)
    require(pre['protocol_hash'] == protocol['protocol_hash'], 'Pre-label protocol differs')
    users, pools, fixed = references(protocol)
    horizon = config['development']['horizon_days']
    assets, profiles, history, truth_map, end, _ = starter.load_data(data_dir, protocol['cutoff'], horizon)
    require(set(assets) == set(protocol['eligible_assets']) and end == protocol['end_exclusive'] and
            starter.select_users(profiles, history, 'warm', 100, None) == users, 'June protocol mismatch')
    eligible = set(assets)
    truth = {uid: truth_map.get(uid, set()) & eligible for uid in users}
    buyers = [uid for uid in users if truth[uid]]
    require(len(buyers) == 11 and sum(map(len, truth.values())) == 18, 'June truth counts differ')
    post = pre['rankings']
    main = post['main_g']
    valid = {uid: main[uid] for uid in pre['valid']['main_g']}
    scores, metrics = {}, {}
    for method, ranking in (fixed | post | {'main_g_valid': valid}).items():
        scores[method], metrics[method] = score_summary(ranking, truth)
    prior = read_json(STAGE4 / 'summary.json')['metrics']
    require(all(metrics[method] == prior[method] for method in fixed), 'Stage 4 reference metrics differ')
    main_scores = scores['main_g']
    pairwise = {method: compare(main_scores, scores[method], buyers) for method in REFERENCES if method != 'popularity'}
    ablation = {}
    for name in SETS[1:]:
        ablation[name] = metrics[name] | {
            'invalid': pre['stats'][name]['invalid'], 'fallback': pre['stats'][name]['fallback'],
            'changed': sum(post[name][uid] != main[uid] for uid in users),
            'overlap': mean([position_overlap(post[name][uid], main[uid]) for uid in users]),
            'comparison': compare(scores[name], main_scores, buyers)}
    seed_rows = list(ablation.values())
    averaged = {uid: mean([scores[name][uid] for name in SETS[1:]]) for uid in users}
    ablation['mean'] = {field: mean([row[field] for row in seed_rows])
                        for field in ('all', 'buyers_ndcg', 'invalid', 'fallback', 'changed', 'overlap')}
    ablation['mean']['comparison'] = compare(averaged, main_scores, buyers)
    fallback_users = len(set(users) - set.intersection(*(set(pre['valid'][name]) for name in SETS[1:])))

    movement_counts = Counter()
    transitions = Counter()
    examples = []
    for uid in buyers:
        # The parser returns ten ranks. A candidate outside that list has no observed rank in the reranking.
        ranks = {asset: i for i, asset in enumerate(main[uid], 1)}
        moves = [{'u1': i, 'posthoc': ranks.get(asset)} for i, asset in enumerate(pools[uid], 1) if asset in truth[uid]]
        up = any(m['posthoc'] is not None and m['posthoc'] < m['u1'] for m in moves)
        down = any((m['posthoc'] or 11) > min(m['u1'], 11) for m in moves)
        transitions.update((m['u1'], m['posthoc']) for m in moves
                           if m['posthoc'] != m['u1'] and (m['posthoc'] is not None or m['u1'] <= 10))
        movement_counts.update({'up': up, 'down': down, 'both': up and down, 'neither': not up and not down})
        examples.append({'alias': f'U{users.index(uid)+1:03d}', 'moves': moves, 'outside_u1': len(truth[uid]) - len(moves),
                         'u1': scores['u1_order'][uid], 'posthoc': main_scores[uid], 'primary': scores['llm_u1'][uid]})
    u030 = next(row for row in examples if row['alias'] == 'U030')
    require(round(u030['u1'], 4) == 0.8772 and round(u030['primary'], 4) == 0.6131, 'U030 reference differs')
    example = max((row for row in examples if row['alias'] != 'U030'),
                  key=lambda row: abs(row['posthoc'] - row['u1']))
    overlap = {name: mean([position_overlap(fixed[name][uid], fixed['popularity'][uid]) for uid in users])
               for name in ('u1_order', 'lambdamart_u1')}
    overlap['main_g'] = pre['stats']['main_g']['popularity_overlap']
    result = {'metrics': {name: metrics[name] for name in ('main_g', 'main_g_valid')},
              'pairwise': pairwise, 'ablation': ablation, 'fallback_users': fallback_users,
              'movement': dict(movement_counts),
              'transitions': [{'u1': source, 'posthoc': target, 'count': count}
                              for (source, target), count in transitions.items()],
              'example': example, 'u030': u030, 'popularity_overlap': overlap,
              'buyers_detail_sha256': extend_buyer_details(buyers, truth, main, main_scores)}
    write_json(OUT / 'summary_stage5b.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='phase', required=True)
    sub.add_parser('parse').add_argument('--notebook', type=Path)
    evaluate_parser = sub.add_parser('evaluate')
    evaluate_parser.add_argument('--data-dir', type=Path, required=True)
    evaluate_parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    if args.phase == 'parse':
        parse(args.notebook)
    else:
        evaluate(args.data_dir, args.package)


if __name__ == '__main__':
    main()
