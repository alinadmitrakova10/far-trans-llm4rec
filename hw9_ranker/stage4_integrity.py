"""Verify Colab artifacts and executable notebook before opening June labels."""

import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from pools import ROOT, read_json, sha256, write_json
from stage3_runtime import SETS, read_jsonl


STAGE3 = ROOT / 'outputs' / 'stage3'
RESULTS = STAGE3 / 'colab_results'
STAGE4 = ROOT / 'outputs' / 'stage4'
NOTEBOOK = ROOT / 'notebooks' / 'hw9_ranker_gpu_executed.ipynb'
ARCHIVE_SHA = 'bbf4a6cc13d602efc41ea349067b326eeee7c0f25292c1fb96f8cd2a8d06a7b7'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def verify(notebook, archive=None):
    files = {p.relative_to(RESULTS).as_posix(): sha256(p) for p in sorted(RESULTS.rglob('*')) if p.is_file()}
    if archive is not None:
        require(sha256(archive) == ARCHIVE_SHA, 'Imported archive hash mismatch')
        with ZipFile(archive) as packed:
            require(len(packed.namelist()) == len(files) and set(packed.namelist()) == files.keys() and
                    all(hashlib.sha256(packed.read(name)).hexdigest() == h for name, h in files.items()),
                    'Imported files differ from returned archive')

    identity = read_json(RESULTS / 'run_identity.json')
    with ZipFile(STAGE3 / 'bundle.zip') as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        protocol = json.loads(bundle.read('protocol.json'))
        require(identity['bundle_sha256'] == sha256(STAGE3 / 'bundle.zip') and
                identity['weight_sha256'] == manifest['model_files_sha256'] and
                identity['generation'] == manifest['generation'], 'Colab identity mismatch')
        for name in SETS:
            frozen = [json.loads(line) for line in bundle.read(f'{name}.jsonl').splitlines()]
            replies = read_jsonl(RESULTS / f'{name}.jsonl')
            require(len(frozen) == len(replies) == len({row['id'] for row in replies}) == 100 and
                    all(a['id'] == b['id'] and sha_text(a['prompt']) == b['prompt_sha256']
                        for a, b in zip(frozen, replies, strict=True)), f'Prompt identity mismatch: {name}')
    teacher = read_json(RESULTS / 'teacher' / 'run_manifest.json')
    raw = read_jsonl(RESULTS / 'teacher' / 'raw_generations.jsonl')
    final = read_jsonl(RESULTS / 'teacher' / 'final_responses.jsonl')
    original = read_jsonl(STAGE3 / 'teacher_check_original' / 'ranker_prompts.jsonl')
    users = protocol['users']
    require(len(users) == len(set(users)) == len(raw) == len(final) == len(original) == 100 and
            teacher['users'] == users and teacher['protocol_hash'] == protocol['protocol_hash'] and
            teacher['scored'] is False and teacher['data_sha256'] == protocol['source_sha256'], 'Teacher manifest or cohort mismatch')
    for uid, a, b, c in zip(users, raw, final, original, strict=True):
        require(a['id'] == b['user_id'] == c['user_id'] == uid and a['text'] == b['raw_response'] and
                a['prompt_sha256'] == sha_text(c['prompt']), 'Teacher prompt or response mismatch')

    executed = read_json(notebook)
    template = read_json(ROOT / 'notebooks' / 'hw9_ranker_gpu.ipynb')
    require([''.join(c['source']).rstrip() for c in executed['cells']] ==
            [''.join(c['source']).rstrip() for c in template['cells']], 'Executed notebook code differs')
    cells = [c for c in executed['cells'] if c['cell_type'] == 'code']
    require([c['execution_count'] for c in cells] == list(range(1, 8)) and
            all(o['output_type'] != 'error' for c in cells for o in c['outputs']), 'Notebook execution incomplete')
    outputs = json.dumps([c.get('outputs', []) for c in cells] + [executed['metadata']], ensure_ascii=False)
    for values in (users, protocol['eligible_assets']):
        require(not any(re.search(r'\b' + re.escape(s) + r'\b', outputs) for s in values),
                'User identifiers or ISIN in notebook outputs')
    require(not any(key in outputs for key in ('raw_response', 'candidate_order_first10', 'per_user', 'prompt_sha256', 'user_id')),
            'Ranking or answer fields in notebook outputs')
    require(all(len(reply['text']) < 16 or json.dumps(reply['text'], ensure_ascii=False)[1:-1] not in outputs
                for name in SETS for reply in read_jsonl(RESULTS / f'{name}.jsonl')), 'Model output present in notebook')
    timing = read_jsonl(RESULTS / 'timing.jsonl')
    return {'files_sha256': files, 'notebook_sha256': sha256(notebook),
            'bundle_sha256': identity['bundle_sha256'], 'protocol_hash': protocol['protocol_hash'],
            'archive_sha256': ARCHIVE_SHA if archive is not None else None,
            'identity': identity, 'timing': timing, 'teacher_runtime': teacher['runtime']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook', type=Path, default=NOTEBOOK)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    record = verify(args.notebook, args.archive)
    STAGE4.mkdir(parents=True, exist_ok=True)
    write_json(STAGE4 / 'integrity.json', record)
    print('Verified 400 U1 responses, 100 teacher responses, and safe executed notebook.')
    print('Notebook SHA-256:', record['notebook_sha256'])


if __name__ == '__main__':
    main()
