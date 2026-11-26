"""Verify the handoff and journal raw model responses without ranking or scoring."""

import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile


SETS = ('main', 'ablation_seed0', 'ablation_seed1', 'ablation_seed2')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_bundle(archive_path, target):
    with ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        names = list(manifest['file_sha256']) + ['manifest.json']
        if (sorted(archive.namelist()) != sorted(names)
                or any(Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name for name in names)):
            raise ValueError('Unexpected bundle members')
        for name, expected in manifest['file_sha256'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f'Bundle file SHA-256 mismatch: {name}')
        archive.extractall(target)
    return manifest


def read_jsonl(path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError(f'Incomplete JSONL row in {path.name}; preserve it and inspect before resuming')
    return [json.loads(line) for line in raw.splitlines()]


def append(path, row):
    line = json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n'
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())


def check_identity(path, identity):
    if path.exists():
        if json.loads(path.read_bytes()) != identity:
            raise ValueError('Run settings or input changed; refusing to resume')
        return
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(identity, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def run_set(records, path, backend, *, max_new_tokens=None):
    expected = [row['id'] for row in records]
    saved = read_jsonl(path)
    present = [row['id'] for row in saved]
    if len(set(expected)) != len(expected) or present != expected[:len(present)]:
        raise ValueError('Response journal is not a prefix of the frozen input IDs')
    new = 0
    for row, result in zip(records, saved):
        if result['prompt_sha256'] != hashlib.sha256(row['prompt'].encode()).hexdigest():
            raise ValueError('Previously completed prompt differs')
    for row in records[len(present):]:
        kwargs = {} if max_new_tokens is None else {'max_new_tokens': max_new_tokens}
        result = backend.generate(row['prompt'], **kwargs)
        append(path, {'id': row['id'], 'prompt_sha256': hashlib.sha256(row['prompt'].encode()).hexdigest(),
                      **{key: result[key] for key in ('text', 'input_tokens', 'output_tokens', 'seconds')}})
        new += 1
    return {'skipped': len(present), 'new': new,
            'generation_seconds': sum(row['seconds'] for row in read_jsonl(path))}


def dry_run(bundle, out):
    class Fake:
        calls = 0

        def generate(self, prompt):
            self.calls += 1
            return {'text': 'synthetic response', 'input_tokens': len(prompt.split()), 'output_tokens': 2, 'seconds': 0.0}

    records = read_jsonl(bundle / 'main.jsonl')[:2]
    assert len(records) == 2
    out.mkdir(parents=True, exist_ok=True)
    journal = out / 'main.jsonl'
    fake = Fake()
    first = run_set(records[:1], journal, fake)
    second = run_set(records, journal, fake)
    third = run_set(records, journal, fake)
    assert [(item['skipped'], item['new']) for item in (first, second, third)] == [(0, 1), (1, 1), (2, 0)]
    assert fake.calls == 2 and [item['id'] for item in read_jsonl(journal)] == [item['id'] for item in records]
    return {'calls': fake.calls, 'resumed': second, 'reopened': third}
