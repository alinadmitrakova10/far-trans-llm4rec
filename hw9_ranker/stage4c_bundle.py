"""Freeze the 100 label-free prompts for the Stage 4c format diagnostic."""

import argparse
import difflib
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from pools import ROOT, load_slice, sha256, verified_inputs, write_json
from stage3_bundle import HW8, NEW, OLD, PAYLOAD_SHA, alias, canonical, common_payload, llm_ranker, write_jsonl
from stage4_integrity import STAGE3, require, sha_text


OUT = ROOT / 'outputs' / 'stage4c'
CONDITIONS = ('A', 'B', 'F', 'G', 'H')
HISTORIC_SHA = '2de6665467541d1e46eac651e65f1438ad412e572ab63aac144606cf394531b1'
MAIN_BUNDLE_SHA = 'f3806321f4c3d36f69783be8d0a61934b7ec68f1062993de26be8aec1e5e3fc1'


def jsonl(archive, name):
    return list(map(json.loads, archive.read(name).splitlines()))


def prompt(instruction, table):
    return instruction + '\n' + canonical(table).decode('utf-8')


def comparison_failure(saved, rebuilt, ordinal):
    def pretty(text):
        instruction, body = text.split('\n', 1)
        return [instruction] + json.dumps(json.loads(body), ensure_ascii=False, indent=2).splitlines()
    lines = list(difflib.unified_diff(pretty(saved), pretty(rebuilt), fromfile='HW8', tofile='H', lineterm=''))
    if not lines:
        lines = list(difflib.unified_diff([repr(saved)], [repr(rebuilt)], fromfile='HW8 bytes', tofile='H bytes', lineterm=''))
    path = OUT / 'h_first_diff.txt'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    raise ValueError(f'H first differs at protocol ordinal {ordinal}: {path}')


def build(args, target):
    config, protocol = verified_inputs(args.data_dir, args.package)
    require(sha256(STAGE3 / 'bundle.zip') == MAIN_BUNDLE_SHA, 'Frozen A bundle mismatch')
    freeze = ROOT / 'outputs' / 'stage2' / 'pools' / 'payloads_2021-06-01.jsonl'
    require(sha256(freeze) == PAYLOAD_SHA, 'Frozen U1 candidate features mismatch')
    frozen_payloads = list(map(json.loads, freeze.read_bytes().splitlines()))[:20]
    historic_path = HW8.parent / 'results' / 'ranker_results.zip'
    require(sha256(historic_path) == HISTORIC_SHA, 'Historic prompt archive mismatch')

    with ZipFile(STAGE3 / 'bundle.zip') as old:
        main = jsonl(old, 'main.jsonl')[:20]
        mappings = {row['id']: row for row in jsonl(old, 'aliases.jsonl') if row['id'].startswith('main:')}
        main_manifest = json.loads(old.read('manifest.json'))
        runtime_files = {name: old.read(name) for name in ('gpu_llm.py', 'stage3_runtime.py')}
    require(main_manifest['generation'] == config['methods']['llm']['generation'], 'Generation settings mismatch')

    snapshot = load_slice(args.data_dir, protocol['cutoff'])
    require(snapshot.truth is None and set(snapshot.assets) == set(protocol['eligible_assets']), 'Expected only past data')
    with ZipFile(args.package) as source:
        cbf = jsonl(source, 'contexts.jsonl')[:20]
    historical_mappings = json.loads((HW8.parent / 'results' / 'evaluation_mappings.json').read_bytes())[:20]
    old_instruction = llm_ranker.INSTRUCTION
    require(old_instruction.count(OLD) == 1, 'Historic instruction mismatch')
    short_instruction = old_instruction.replace(OLD, NEW)

    # First verify all H prompts before writing any run inputs.
    checked = []
    differences = []
    with ZipFile(historic_path) as historic:
        for index, (uid, context, historical) in enumerate(zip(protocol['users'][:20], cbf, historical_mappings, strict=True), 1):
            user_alias = f'U{index:03d}'
            cbf_ids = [row['id'] for row in context['candidate_assets']]
            require(context['user_id'] == uid and len(cbf_ids) == len(set(cbf_ids)) == 50 and
                    historical['group_key'] == user_alias and historical['pool_isins'] == cbf_ids[:20], 'Historic CBF20 differs')
            payload = common_payload(user_alias, protocol['cutoff'], snapshot.assets, snapshot.profiles[uid],
                                     snapshot.history[uid], snapshot.last_buy[uid], cbf_ids[:20])
            rebuilt = llm_ranker.build_prompt(payload)
            rows = jsonl(historic, f'results/{user_alias}_calls.jsonl')
            saved = [row for row in rows if row['branch'] == 'original']
            require(len(saved) == 3 and all(sha_text(row['prompt']) == row['prompt_sha256'] for row in saved),
                    'Historic original prompt integrity mismatch')
            if any(rebuilt.encode() != row['prompt'].encode() for row in saved):
                differences.append((index, next(row['prompt'] for row in saved if rebuilt != row['prompt']), rebuilt))
            checked.append((uid, payload, rebuilt, cbf_ids))
    print(f'H exact byte matches: {20 - len(differences)}/20', flush=True)
    if differences:
        comparison_failure(differences[0][1], differences[0][2], differences[0][0])

    requests, aliases, orders = [], [], {}
    recoded_users = 0
    rng = random.Random(2026)
    for (uid, historical, h, cbf_ids), row, frozen in zip(checked, main, frozen_payloads, strict=True):
        user_alias = historical['user_alias']
        a = row['prompt']
        prefix, json_body = a.split('\n', 1)
        a_table = json.loads(json_body)
        mapping = mappings[row['id']]
        require(row['id'] == f'main:{user_alias}' and mapping['user_id'] == uid and prefix == short_instruction
                and frozen['user_alias'] == user_alias and prompt(short_instruction, a_table).encode() == a.encode(),
                'A is not the frozen main prompt')
        a_wire = {asset: key for key, asset in mapping['wire_to_asset_alias'].items()}
        h_wire = llm_ranker.wire_aliases(historical)
        recoded_users += any(a_wire[asset] != h_wire[asset] for asset in a_wire.keys() & h_wire.keys()
                             if asset in {candidate['asset_alias'] for candidate in historical['candidates']}
                             and a_wire[asset] in mapping['candidate_alias_to_isin'])
        b_wire = dict(a_wire)
        for asset in sorted(set(h_wire) - b_wire.keys()):
            b_wire[asset] = f'A{len(b_wire) + 1:02d}'
        candidate_columns = a_table['candidate_columns']
        b_table = dict(a_table, candidate_rows=[llm_ranker.table_row(item, candidate_columns, b_wire)
                                                for item in historical['candidates']])
        # The saved U1 payload holds the true CBF50 position or null, not the U1 pool position.
        u1_ids = [mapping['candidate_alias_to_isin'][row[0]] for row in a_table['candidate_rows']]
        cbf_ranks = {isin: rank for rank, isin in enumerate(cbf_ids, 1)}
        require([item['asset_alias'] for item in frozen['candidates']] == [alias(isin) for isin in u1_ids]
                and [item['source_cbf_rank'] for item in frozen['candidates']] == [cbf_ranks.get(isin) for isin in u1_ids],
                'Frozen U1 ranks differ from CBF50')
        restored = dict(a_table, candidate_columns=llm_ranker.CANDIDATE_COLUMNS,
                        candidate_rows=[llm_ranker.table_row(item, llm_ranker.CANDIDATE_COLUMNS, a_wire)
                                        for item in frozen['candidates']])
        rank_column = restored['candidate_columns'].index('source_cbf_rank')
        require([item[:rank_column] + item[rank_column+1:] for item in restored['candidate_rows']]
                == a_table['candidate_rows'], 'Restoring rank altered unrelated U1 fields')
        h_table = json.loads(h.split('\n', 1)[1])
        require(all(h_table[key] == a_table[key] for key in ('profile', 'history_summary', 'cutoff', 'history_columns')),
                'Historic profile or history summary differs')
        a_inverse = {key: value for value, key in a_wire.items()}
        h_inverse = {key: value for value, key in h_wire.items()}
        require([[a_inverse[item[0]], *item[1:]] for item in a_table['history_rows']] ==
                [[h_inverse[item[0]], *item[1:]] for item in h_table['history_rows']], 'Historic history content differs')
        variants = {'A': (a, a_wire, u1_ids), 'B': (prompt(short_instruction, b_table), b_wire, cbf_ids[:20]),
                    'F': (prompt(short_instruction, restored), a_wire, u1_ids),
                    'G': (prompt(old_instruction, restored), a_wire, u1_ids), 'H': (h, h_wire, cbf_ids[:20])}
        sequence = list(CONDITIONS)
        rng.shuffle(sequence)
        orders[user_alias] = sequence
        for condition in sequence:
            text, wire, ids = variants[condition]
            key = f'{user_alias}:{condition}'
            requests.append({'id': key, 'condition': condition, 'prompt_sha256': sha_text(text), 'prompt': text})
            aliases.append({'id': key, 'candidate_alias_to_isin': {wire[alias(isin)]: isin for isin in ids},
                            'wire_to_asset_alias': {short: asset for asset, short in wire.items()}})

    require(len(requests) == len({row['id'] for row in requests}) == 100, 'Diagnostic call count differs')
    write_jsonl(target / 'prompts.jsonl', requests)
    write_jsonl(target / 'aliases.jsonl', aliases)
    for name, content in runtime_files.items():
        (target / name).write_bytes(content)
    manifest = {'protocol_hash': protocol['protocol_hash'], 'generation': main_manifest['generation'],
                'model_files_sha256': main_manifest['model_files_sha256'], 'seed': 2026, 'calls': len(requests),
                'h_exact_matches': len(checked), 'shared_candidate_recoding_users': recoded_users,
                'order_by_user_alias': orders, 'prompt_sha256': {row['id']: row['prompt_sha256'] for row in requests},
                'file_sha256': {path.name: sha256(path) for path in sorted(target.iterdir())}}
    write_json(target / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'bundle_diag.zip'
    if destination.exists():
        raise FileExistsError('Frozen diagnostic bundle already exists')
    with TemporaryDirectory(dir=OUT, prefix='diag-') as temp:
        files = Path(temp) / 'files'
        files.mkdir()
        manifest = build(args, files)
        archive = Path(temp) / 'bundle_diag.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as packed:
            for path in sorted(files.iterdir()):
                packed.write(path, path.name)
        archive.rename(destination)
    print('Archive SHA-256:', sha256(destination))
    print('Users with a shared candidate recoded in H:', manifest['shared_candidate_recoding_users'])


if __name__ == '__main__':
    main()
