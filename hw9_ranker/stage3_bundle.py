"""Build the label-free, immutable Stage 3 handoff."""

import argparse
import csv
import difflib
import json
from pathlib import Path
import random
import re
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from pools import ROOT, load_slice, read_json, sha256, verified_inputs, write_json


HW8 = ROOT.parent / 'hw8' / 'daria_babikova' / 'hw2'
sys.path.insert(0, str(HW8 / 'scripts'))
import llm_ranker
from input_contract import age, alias, canonical, cbf_scores, common_payload


OLD = 'Ages are days before the cutoff; source_cbf_rank is the ORIGINAL retrieval rank, not the row position in this presentation.'
NEW = 'Ages are days before the cutoff.'
CHANGED = ('source_cbf_score', 'past_buy_count', 'last_buy_age_days')
POOL_SHA = 'a6795dfeb8865d4bd00b589efb30e2f3ae7503151407982f30dcb0146bbfb36e'
PAYLOAD_SHA = '2c8b82d1f14b8a1a1be25291b93b81482a996880588cc5adba90f10b28dbe1bd'


def donors(blocks, seed):
    rng = random.Random(seed)
    assignment = {}
    for block in blocks:
        shuffled = list(block)
        while True:
            rng.shuffle(shuffled)
            if all(left != right for left, right in zip(block, shuffled, strict=True)):
                break
            shuffled = list(block)
        assignment.update(zip(block, shuffled, strict=True))
    return assignment


def write_jsonl(path, rows):
    path.write_bytes(b''.join(canonical(row) + b'\n' for row in rows))


def prepare(args, out):
    cfg, protocol = verified_inputs(args.data_dir, args.package)
    cutoff, users = protocol['cutoff'], protocol['users']
    stage2 = ROOT / 'outputs' / 'stage2' / 'pools'
    pool_path, payload_path = stage2 / f'pools_{cutoff}.csv', stage2 / f'payloads_{cutoff}.jsonl'
    if sha256(pool_path) != POOL_SHA or sha256(payload_path) != PAYLOAD_SHA:
        raise ValueError('Frozen Stage 2 input changed')
    snapshot = load_slice(args.data_dir, cutoff)
    if snapshot.truth is not None or set(snapshot.assets) != set(protocol['eligible_assets']):
        raise ValueError('Expected only history and the frozen eligible catalog')
    pool_by_user = {}
    with pool_path.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            pool = pool_by_user.setdefault(row['user_id'], [])
            if row['method'] != 'U1' or int(row['rank']) != len(pool) + 1:
                raise ValueError('Frozen pool order mismatch')
            pool.append(row['ISIN'])
    if list(pool_by_user) != users or any(len(set(pool)) != 20 for pool in pool_by_user.values()):
        raise ValueError('Frozen pool cohort or membership mismatch')

    payloads = dict(zip(users, (json.loads(line) for line in payload_path.read_bytes().splitlines()), strict=True))
    isins = {alias(isin): isin for isin in snapshot.assets}
    if len(isins) != len(snapshot.assets) or llm_ranker.INSTRUCTION.count(OLD) != 1:
        raise ValueError('Unexpected asset alias collision or HW8 instruction')
    instruction = llm_ranker.INSTRUCTION.replace(OLD, NEW)
    dates = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
    isin_pattern = re.compile(r'\b[A-Z]{2}[A-Z0-9]{9}\d\b|\b(?:' + '|'.join(map(re.escape, sorted(snapshot.assets))) + r')\b')

    def checked_prompt(body):
        prompt = instruction + '\n' + canonical(body).decode('utf-8')
        if (body['cutoff'] != cutoff or 'source_cbf_rank' in prompt or isin_pattern.search(prompt)
                or any(value > cutoff for value in dates.findall(prompt))
                or set(body) != set(main_keys)):
            raise ValueError('Prompt contains excluded fields, identifiers or dates')
        return prompt

    main_keys = ('user_alias', 'cutoff', 'repeat_purchases_allowed', 'profile', 'history_summary',
                 'history_columns', 'history_rows', 'candidate_columns', 'candidate_rows')
    buy_counts = {uid: sum(snapshot.history[uid].values()) for uid in users}
    sorted_users = sorted(users, key=lambda uid: (buy_counts[uid], uid))
    blocks = [sorted_users[i:i + 5] for i in range(0, len(users), 5)]
    if len(blocks[-1]) == 1:
        blocks[-2].extend(blocks.pop())
    seeds = cfg['ablation']['seeds']
    assignments = {seed: donors(blocks, seed) for seed in seeds}
    donor_scores = {uid: cbf_scores(snapshot.history[uid], snapshot.assets) for uid in users}
    rows = {'main': []} | {f'ablation_seed{seed}': [] for seed in seeds}
    dictionaries = []
    for index, uid in enumerate(users, 1):
        payload = payloads[uid]
        pool = pool_by_user[uid]
        if payload['user_alias'] != f'U{index:03d}' or [isins[c['asset_alias']] for c in payload['candidates']] != pool:
            raise ValueError('Frozen payload order mismatch')
        rebuilt = common_payload(payload['user_alias'], cutoff, snapshot.assets, snapshot.profiles[uid],
                                 snapshot.history[uid], snapshot.last_buy[uid], pool)
        for item, frozen in zip(rebuilt['candidates'], payload['candidates'], strict=True):
            item['source_cbf_rank'] = frozen['source_cbf_rank']
        if canonical(rebuilt) != canonical(payload):
            # CBF sums can differ by machine rounding. Frozen values are kept for main.
            for item, frozen in zip(rebuilt['candidates'], payload['candidates'], strict=True):
                if abs(item['source_cbf_score'] - frozen['source_cbf_score']) > 1e-12:
                    raise ValueError('Frozen CBF score differs beyond rounding')
                item['source_cbf_score'] = frozen['source_cbf_score']
            if canonical(rebuilt) != canonical(payload):
                raise ValueError('Frozen payload does not match independently recomputed history')
        base = llm_ranker.prompt_data(payload)
        index_to_remove = base['candidate_columns'].index('source_cbf_rank')
        base['candidate_columns'] = [name for name in base['candidate_columns'] if name != 'source_cbf_rank']
        base['candidate_rows'] = [row[:index_to_remove] + row[index_to_remove + 1:] for row in base['candidate_rows']]
        wire = llm_ranker.wire_aliases(payload)
        if [row[0] for row in base['candidate_rows']] != [wire[alias(isin)] for isin in pool]:
            raise ValueError('Candidate rows differ from original U1 order')
        stable = [i for i, col in enumerate(base['candidate_columns']) if col not in CHANGED]

        def emit(name, body, mapping):
            key = f'{name}:{payload["user_alias"]}'
            rows[name].append({'id': key, 'prompt': checked_prompt(body)})
            dictionaries.append({'id': key, 'user_id': uid, 'candidate_alias_to_isin':
                                 {mapping[alias(isin)]: isin for isin in pool},
                                 'wire_to_asset_alias': {short: asset for asset, short in mapping.items()}})

        emit('main', base, wire)
        for seed, assignment in assignments.items():
            donor = assignment[uid]
            if uid == donor or not any(uid in block and donor in block for block in blocks):
                raise ValueError('Invalid donor assignment')
            foreign = payloads[donor]
            mapping = dict(wire)
            extras = sorted({item['asset_alias'] for item in foreign['history']} - mapping.keys())
            for asset in extras:
                mapping[asset] = f'A{len(mapping) + 1:02d}'
            body = dict(base, history_summary=foreign['history_summary'], history_rows=[
                llm_ranker.table_row(item, llm_ranker.HISTORY_COLUMNS, mapping) for item in foreign['history']],
                candidate_rows=[list(row) for row in base['candidate_rows']])
            for row, isin in zip(body['candidate_rows'], pool, strict=True):
                latest = snapshot.last_buy[donor].get(isin)
                values = (donor_scores[donor][isin], snapshot.history[donor].get(isin, 0),
                          age(cutoff, latest) if latest else None)
                for field, value in zip(CHANGED, values, strict=True):
                    row[body['candidate_columns'].index(field)] = value
            project = lambda data: canonical([[row[i] for i in stable] for row in data['candidate_rows']])
            if project(body) != project(base) or any(body[key] != base[key] for key in main_keys
                    if key not in ('history_summary', 'history_rows', 'candidate_rows')):
                raise ValueError('Ablation mutated fixed prompt fields')
            emit(f'ablation_seed{seed}', body, mapping)

    block_lines = ['| Блок | Получатели (число Buy) | Доноры seed 0 | Доноры seed 1 | Доноры seed 2 |',
                   '| ---: | --- | --- | --- | --- |']
    for index, block in enumerate(blocks, 1):
        show = lambda ids: ', '.join(f'{uid} ({buy_counts[uid]})' for uid in ids)
        columns = [str(index), show(block)] + [show([assignments[seed][uid] for uid in block]) for seed in seeds]
        block_lines.append('| ' + ' | '.join(columns) + ' |')
    (out.parent / 'ablation_blocks.md').write_text('\n'.join(block_lines) + '\n', encoding='utf-8')
    diff = list(difflib.unified_diff([OLD + '\n'], [NEW + '\n'], fromfile='HW8', tofile='HW9'))
    print(''.join(diff), end='')
    for name, records in rows.items():
        if len(records) != cfg['development']['users']:
            raise ValueError('Unexpected prompt count')
        write_jsonl(out / f'{name}.jsonl', records)
    write_jsonl(out / 'aliases.jsonl', dictionaries)
    with ZipFile(args.package) as archive:
        (out / 'protocol.json').write_bytes(archive.read('protocol.json'))
    for name in ('gpu_llm.py', 'llm_ranker.py', 'input_contract.py'):
        text = (HW8 / 'scripts' / name).read_bytes()
        if name == 'llm_ranker.py':
            text, count = re.subn(rb"Ages are days before the cutoff; source_cbf_rank '\r?\n    '"
                                  rb"is the ORIGINAL retrieval rank, not the row position in this presentation\. ",
                                  b'Ages are days before the cutoff. ', text)
            text = text.replace(b"'source_cbf_rank',", b'')
            if count != 1 or b'source_cbf_rank' in text:
                raise ValueError('Could not adapt bundled HW8 serializer')
        (out / name).write_bytes(text)
    for name in ('stage3_runtime.py', 'stage3_teacher.py', 'pools.py'):
        (out / name).write_bytes((ROOT / name).read_bytes())
    for name in ('far-trans', 'far-trans-llm'):
        for path in (ROOT / 'vendor' / name).glob('*.py'):
            target = out / 'vendor' / name / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    manifest = {'protocol_hash': protocol['protocol_hash'], 'frozen_pool_sha256': POOL_SHA,
                'generation': cfg['methods']['llm']['generation'], 'prompt_counts': {k: len(v) for k, v in rows.items()},
                'model_files_sha256': read_json(HW8 / 'LLM_MODEL.json')['files_sha256'],
                'file_sha256': {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write_json(out / 'manifest.json', manifest)
    print('Checks passed: 100 main, 300 ablation, 0 self assignments, 20 blocks.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--package', required=True, type=Path)
    args = parser.parse_args()
    stage = ROOT / 'outputs' / 'stage3'
    stage.mkdir(parents=True, exist_ok=True)
    final = stage / 'bundle.zip'
    if final.exists():
        raise FileExistsError('Frozen Stage 3 bundle already exists')
    with TemporaryDirectory(dir=stage) as temp:
        path = Path(temp) / 'bundle'
        path.mkdir()
        prepare(args, path)
        with ZipFile(Path(temp) / 'bundle.zip', 'w', ZIP_DEFLATED) as archive:
            for file in sorted(path.rglob('*')):
                if file.is_file():
                    archive.write(file, file.relative_to(path).as_posix())
        (Path(temp) / 'ablation_blocks.md').rename(stage / 'ablation_blocks.md')
        (Path(temp) / 'bundle.zip').rename(final)
    print('Bundle SHA-256:', sha256(final))


if __name__ == '__main__':
    main()
