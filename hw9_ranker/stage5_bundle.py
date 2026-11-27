"""Freeze the post-hoc G prompts with the original U1 and Stage 3 donor assignments."""

import argparse
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from pools import ROOT, load_slice, sha256, starter, verified_inputs, write_json
from stage3_bundle import (CHANGED, NEW, OLD, PAYLOAD_SHA, POOL_SHA, age, alias, canonical, cbf_scores,
                           donors, llm_ranker, write_jsonl)
from stage3_runtime import SETS
from stage4_integrity import STAGE3, require, sha_text
from stage4c_bundle import MAIN_BUNDLE_SHA, OUT as DIAG, jsonl, prompt
from stage4c_review import BUNDLE_SHA as DIAG_BUNDLE_SHA


OUT = ROOT / 'outputs' / 'stage5'
POSTHOC_SETS = ('main_g', 'ablation_g_seed0', 'ablation_g_seed1', 'ablation_g_seed2')


def verify_frozen_ranks(frozen, u1, cbf_ranks):
    require([item['asset_alias'] for item in frozen['candidates']] == [alias(isin) for isin in u1],
            'Frozen U1 order differs from prompt')
    require([item['source_cbf_rank'] for item in frozen['candidates']] == [cbf_ranks.get(isin) for isin in u1],
            'Frozen recipient ranks differ from shared CBF50')


def build(args, out):
    cfg, protocol = verified_inputs(args.data_dir, args.package)
    cutoff, users = protocol['cutoff'], protocol['users']
    stage2 = ROOT / 'outputs' / 'stage2' / 'pools'
    payload_path = stage2 / f'payloads_{cutoff}.jsonl'
    original_bundle = STAGE3 / 'bundle.zip'
    diag_bundle = DIAG / 'bundle_diag.zip'
    require(sha256(payload_path) == PAYLOAD_SHA and sha256(stage2 / f'pools_{cutoff}.csv') == POOL_SHA and
            sha256(original_bundle) == MAIN_BUNDLE_SHA and sha256(diag_bundle) == DIAG_BUNDLE_SHA,
            'A frozen source artifact changed')
    analysis = json.loads((DIAG / 'analysis.json').read_bytes())
    require(analysis['conditions']['G']['valid'] > analysis['conditions']['A']['valid'],
            'Diagnostic result does not support the recorded post-hoc condition')
    frozen_payloads = list(map(json.loads, payload_path.read_bytes().splitlines()))
    with ZipFile(original_bundle) as source, ZipFile(diag_bundle) as diagnostic:
        old_sets = {name: jsonl(source, f'{name}.jsonl') for name in SETS}
        dictionaries = {row['id']: row for row in jsonl(source, 'aliases.jsonl')}
        stage3_manifest = json.loads(source.read('manifest.json'))
        diag_g = {row['id'].split(':')[0]: row['prompt'] for row in jsonl(diagnostic, 'prompts.jsonl') if row['condition'] == 'G'}
        runtime_files = {name: source.read(name) for name in ('gpu_llm.py', 'stage3_runtime.py')}
    require(len(users) == len(frozen_payloads) == 100 and len(diag_g) == 20 and
            stage3_manifest['generation'] == cfg['methods']['llm']['generation'], 'Unexpected cohort or generation settings')

    snapshot = load_slice(args.data_dir, cutoff)
    require(snapshot.truth is None and set(snapshot.assets) == set(protocol['eligible_assets']), 'Expected only past data')
    with ZipFile(args.package) as archive:
        contexts = jsonl(archive, 'contexts.jsonl')
    require([context['user_id'] for context in contexts] == users, 'Frozen CBF50 users differ')
    cbf50 = {context['user_id']: [asset['id'] for asset in context['candidate_assets']] for context in contexts}
    features = {isin: starter.tokens(asset) for isin, asset in snapshot.assets.items()}
    donor_scores = {}
    donor_ranks = {}
    for uid in users:
        scores = starter.content_scores(snapshot.history[uid], features)
        ranked = starter.order(scores)[:50]
        old = cbf50[uid]
        # Keep the registered CBF50 order at floating-point ties after checking all scores by position.
        require(len(old) == len(set(old)) == 50 and any(scores.values()) and all(math.isclose(
                    scores[a], scores[b], rel_tol=0, abs_tol=1e-12) for a, b in zip(ranked, old, strict=True)),
                'Recomputed donor CBF50 differs beyond rounding')
        donor_ranks[uid] = {isin: rank for rank, isin in enumerate(old, 1)}
        donor_scores[uid] = cbf_scores(snapshot.history[uid], snapshot.assets)

    ordered = sorted(users, key=lambda uid: (sum(snapshot.history[uid].values()), uid))
    blocks = [ordered[i:i+5] for i in range(0, len(ordered), 5)]
    require(len(blocks) == 20 and all(len(block) == 5 for block in blocks), 'Stage 3 block count differs')
    assignments = {seed: donors(blocks, seed) for seed in cfg['ablation']['seeds']}
    by_user = dict(zip(users, frozen_payloads, strict=True))
    old_instruction = llm_ranker.INSTRUCTION
    require(old_instruction.count(OLD) == 1, 'HW8 instruction differs')
    new_instruction = old_instruction.replace(OLD, NEW)
    rank_column = llm_ranker.CANDIDATE_COLUMNS.index('source_cbf_rank')
    dates = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
    isins = re.compile(r'\b[A-Z]{2}[A-Z0-9]{9}\d\b')
    transformed = {name: [] for name in POSTHOC_SETS}
    aliases = []
    matches = 0
    null_donor_ranks = 0

    for index, uid in enumerate(users):
        key = f'U{index+1:03d}'
        frozen = by_user[uid]
        require(frozen['user_alias'] == key, 'Frozen payload user alias differs')
        stable_main = None
        for set_index, (source_name, target_name) in enumerate(zip(SETS, POSTHOC_SETS, strict=True)):
            row = old_sets[source_name][index]
            mapping = dictionaries[row['id']]
            instruction, content = row['prompt'].split('\n', 1)
            body = json.loads(content)
            require(row['id'] == f'{source_name}:{key}' and mapping['user_id'] == uid and
                    instruction == new_instruction and body['cutoff'] == cutoff, 'Frozen prompt differs')
            candidates = body['candidate_rows']
            columns = body['candidate_columns']
            u1 = [mapping['candidate_alias_to_isin'][item[0]] for item in candidates]
            verify_frozen_ranks(frozen, u1, donor_ranks[uid])
            donor = uid if set_index == 0 else assignments[set_index-1][uid]
            if set_index:
                require(donor != uid and any(uid in block and donor in block for block in blocks), 'Invalid Stage 3 donor')
                donor_payload = by_user[donor]
                history = [[mapping['wire_to_asset_alias'][item[0]], *item[1:]] for item in body['history_rows']]
                expected_history = [llm_ranker.table_row(item, llm_ranker.HISTORY_COLUMNS,
                                    {item['asset_alias']: item['asset_alias']}) for item in donor_payload['history']]
                require(canonical(history) == canonical(expected_history) and
                        canonical(body['history_summary']) == canonical(donor_payload['history_summary']),
                        'Stage 3 ablation history is not from the recorded donor')
                for item, isin in zip(candidates, u1, strict=True):
                    latest = snapshot.last_buy[donor].get(isin)
                    require(math.isclose(item[columns.index('source_cbf_score')], donor_scores[donor][isin],
                                         rel_tol=0, abs_tol=1e-12) and
                            item[columns.index('past_buy_count')] == snapshot.history[donor].get(isin, 0) and
                            item[columns.index('last_buy_age_days')] == (age(cutoff, latest) if latest else None),
                            'Existing donor candidate fields differ after recomputation')
            stable = canonical([[value for name, value in zip(columns, item, strict=True) if name not in CHANGED]
                               for item in candidates])
            if set_index == 0:
                stable_main = stable
            else:
                require(stable == stable_main, 'Ablation changed fixed candidate fields')

            ranks = [donor_ranks[donor].get(isin) for isin in u1]
            null_donor_ranks += sum(value is None for value in ranks) if set_index else 0
            body['candidate_columns'] = llm_ranker.CANDIDATE_COLUMNS
            body['candidate_rows'] = [item[:rank_column] + [rank] + item[rank_column:]
                                      for item, rank in zip(candidates, ranks, strict=True)]
            text = prompt(old_instruction, body)
            require(not isins.search(text) and all(value <= cutoff for value in dates.findall(text)),
                    'Prompt contains an ISIN or a future date')
            if not set_index and key in diag_g:
                require(text.encode() == diag_g[key].encode(), f'G differs at ordinal {index+1}')
                matches += 1
            run_id = f'{target_name}:{key}'
            transformed[target_name].append({'id': run_id, 'prompt': text, 'prompt_sha256': sha_text(text)})
            aliases.append(dict(mapping, id=run_id))

    require(matches == 20 and all(len(rows) == 100 for rows in transformed.values()), 'Post-hoc call counts differ')
    for name, rows in transformed.items():
        write_jsonl(out / f'{name}.jsonl', rows)
    write_jsonl(out / 'aliases.jsonl', aliases)
    for name, content in runtime_files.items():
        (out / name).write_bytes(content)
    manifest = {'protocol_hash': protocol['protocol_hash'], 'pool_sha256': POOL_SHA,
                'generation': stage3_manifest['generation'], 'model_files_sha256': stage3_manifest['model_files_sha256'],
                'prompt_counts': {name: len(rows) for name, rows in transformed.items()},
                'g_exact_matches': matches, 'donor_self_assignments': 0, 'fixed_candidate_matches': 300,
                'null_donor_ranks': null_donor_ranks,
                'prompt_sha256': {row['id']: row['prompt_sha256'] for rows in transformed.values() for row in rows},
                'file_sha256': {path.name: sha256(path) for path in sorted(out.iterdir())}}
    write_json(out / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'bundle_posthoc.zip'
    if destination.exists():
        raise FileExistsError('Frozen post-hoc bundle already exists')
    with TemporaryDirectory(dir=OUT, prefix='posthoc-') as tmp:
        staging = Path(tmp) / 'files'
        staging.mkdir()
        manifest = build(args, staging)
        archive = Path(tmp) / 'bundle_posthoc.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as packed:
            for path in sorted(staging.iterdir()):
                packed.write(path, path.name)
        archive.rename(destination)
    print(f'G exact byte matches: {manifest["g_exact_matches"]}/20; fixed candidate matches: 300/300; self assignments: 0')
    print('Archive SHA-256:', sha256(destination))


if __name__ == '__main__':
    main()
