"""Verify and summarize the diagnostic run without evaluation labels."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
from statistics import median
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from pools import ROOT, read_json, sha256, write_json
from stage3_bundle import llm_ranker
from stage3_runtime import read_jsonl
from stage4_integrity import STAGE3, require, sha_text
from stage4c_bundle import CONDITIONS, OUT, jsonl


BUNDLE_SHA = '43807c6ffd69d67778eb7f2841a52ba7275aed694d42d185aeb30acab4392dd4'
PAIRS = ('AB', 'AG', 'GH', 'AF', 'FG')
FILES = {'nvidia-smi.log', 'responses.jsonl', 'run_identity.json', 'timing.jsonl'}


def has_nested_array(text):
    """Detect a nested root-list item, even if the response was cut mid-item."""
    value = text.strip()
    if not value.startswith('['):
        return False
    decoder, i = json.JSONDecoder(), 1
    while i < len(value):
        while i < len(value) and value[i].isspace():
            i += 1
        if i == len(value) or value[i] == ']':
            break
        if value[i] == '[':
            return True
        try:
            _, i = decoder.raw_decode(value, i)
        except ValueError:
            return False
        while i < len(value) and value[i].isspace():
            i += 1
        if i == len(value) or value[i] != ',':
            break
        i += 1
    return False


def verify_notebook(notebook, replies):
    executed = read_json(notebook)
    template = read_json(ROOT / 'notebooks' / 'hw9_format_diag.ipynb')
    source = lambda doc: [''.join(cell['source']).rstrip() for cell in doc['cells']]
    require(source(executed) == source(template), 'Executed notebook source differs')
    cells = [c for c in executed['cells'] if c['cell_type'] == 'code']
    require(len(cells) == 5 and all(c['execution_count'] is not None and c.get('outputs') for c in cells),
            'Executed notebook incomplete')
    outputs = json.dumps([c['outputs'] for c in cells] + [executed['metadata']], ensure_ascii=False)
    with ZipFile(STAGE3 / 'bundle.zip') as source_bundle:
        protocol = json.loads(source_bundle.read('protocol.json'))
    identifiers = [*protocol['users'], *protocol['eligible_assets'], *(row['id'] for row in replies)]
    require(not any(re.search(r'\b' + re.escape(item) + r'\b', outputs) for item in identifiers),
            'User, candidate or call identifier found in notebook outputs')
    require(not any(field in outputs for field in ('candidate_alias_to_isin', 'candidate_rows', 'raw_response', 'prompt_sha256')),
            'Potential user-level output fields in executed notebook')
    require(all(len(row['text']) < 16 or json.dumps(row['text'], ensure_ascii=False)[1:-1] not in outputs
                for row in replies), 'Model response present in notebook outputs')
    return [{'cell': i, 'type': o['ename'], 'message': o['evalue']} for i, c in enumerate(cells, 1)
            for o in c['outputs'] if o['output_type'] == 'error']


def analyze(results, notebook):
    bundle_path = OUT / 'bundle_diag.zip'
    require(sha256(bundle_path) == BUNDLE_SHA, 'Diagnostic bundle changed')
    with ZipFile(bundle_path) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        prompts = jsonl(bundle, 'prompts.jsonl')
        mappings = {row['id']: row for row in jsonl(bundle, 'aliases.jsonl')}
    replies = read_jsonl(results / 'responses.jsonl')
    require(len(prompts) == len(mappings) == len(replies) == len({row['id'] for row in replies}) == 100,
            'Incomplete or duplicate diagnostic responses')
    identity = read_json(results / 'run_identity.json')
    require(identity['bundle_sha256'] == BUNDLE_SHA and identity['generation'] == manifest['generation'] and
            identity['weight_sha256'] == manifest['model_files_sha256'] and
            identity['revision'] == manifest['generation']['revision'] and 'T4' in identity['gpu'],
            'Diagnostic checkpoint or runtime mismatch')
    timing = read_jsonl(results / 'timing.jsonl')
    finished = [row for row in timing if row.get('stage') == 'generation' and row.get('event') == 'end']
    require(finished and finished[-1]['completed'] == 100 and sum(row['new'] for row in finished) == 100,
            'Diagnostic timing does not account for 100 calls')
    notebook_errors = verify_notebook(notebook, replies) if notebook is not None else None

    outcomes = {key: {} for key in CONDITIONS}
    for frozen, reply in zip(prompts, replies, strict=True):
        key = frozen['id']
        require(reply['id'] == key and reply['prompt_sha256'] == frozen['prompt_sha256'] ==
                manifest['prompt_sha256'][key] == sha_text(frozen['prompt']), 'Response prompt hash or order mismatch')
        user, condition = key.split(':')
        text = reply['text']
        tokens = reply['output_tokens']
        require(condition == frozen['condition'] and isinstance(text, str) and type(tokens) is int and 0 <= tokens <= 256
                and math.isfinite(reply['seconds']) and reply['seconds'] >= 0, 'Invalid journal record')
        table = json.loads(frozen['prompt'].split('\n', 1)[1])
        candidates = [record[0] for record in table['candidate_rows']]
        mapping = mappings[key]
        keys = set(mapping['candidate_alias_to_isin'])
        namespace = set(mapping['wire_to_asset_alias'])
        require(len(candidates) == len(keys) == 20 and set(candidates) == keys <= namespace and table['user_alias'] == user,
                'Candidate aliases differ from condition')
        carrier = {'candidates': [{'asset_alias': item} for item in candidates],
                   'history': [{'asset_alias': item} for item in sorted(namespace - keys)]}
        require(all(a == b for a, b in llm_ranker.wire_aliases(carrier).items()), 'Noncanonical short alias namespace')
        parsed = llm_ranker.parse_or_fallback(text, carrier)
        outcomes[condition][user] = {'valid': not parsed['invalid'], 'nested': has_nested_array(text),
                                     'cap': tokens == 256, 'tokens': tokens}

    users = {f'U{i:03d}' for i in range(1, 21)}
    require(all(records.keys() == users for records in outcomes.values()), 'Diagnostic cohort differs')
    conditions = {name: {**{key: sum(item[key] for item in records.values()) for key in ('valid', 'nested', 'cap')},
                         'median_tokens': median(item['tokens'] for item in records.values())}
                  for name, records in outcomes.items()}
    transitions = {}
    for source, target in PAIRS:
        counts = Counter((outcomes[source][uid]['valid'], outcomes[target][uid]['valid']) for uid in users)
        transitions[source + target] = dict(vv=counts[True, True], vi=counts[True, False],
                                            iv=counts[False, True], ii=counts[False, False])
    return {'conditions': conditions, 'transitions': transitions,
            'gpu': identity['gpu'], 'torch': identity['torch'], 'transformers': identity['transformers'],
            'notebook_sha256': sha256(notebook) if notebook is not None else None, 'notebook_errors': notebook_errors,
            'files_sha256': {name: sha256(results / name) for name in sorted(FILES)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook', type=Path, help='Executed notebook to verify when available')
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    results = OUT / 'diag_results'
    if args.archive is not None:
        with ZipFile(args.archive) as archive, TemporaryDirectory(dir=OUT, prefix='diag-import-') as tmp:
            require(set(archive.namelist()) == FILES and len(archive.namelist()) == len(FILES) and
                    archive.testzip() is None, 'Unexpected diagnostic archive contents')
            extracted = Path(tmp) / 'diag_results'
            archive.extractall(extracted)
            result = analyze(extracted, args.notebook)
            if results.exists():
                require(all(sha256(results / name) == digest for name, digest in result['files_sha256'].items()),
                        'Local diagnostic results differ from the supplied archive')
            else:
                extracted.rename(results)
            result['archive_sha256'] = sha256(args.archive)
    else:
        result = analyze(results, args.notebook)
    write_json(OUT / 'analysis.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
