"""Run the unchanged teacher ranker with past-only inputs and evaluation deferred."""

from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

from pools import ROOT, load_slice, starter
from stage3_runtime import append, check_identity, read_jsonl, sha256

sys.path.insert(0, str(ROOT / 'vendor' / 'far-trans-llm'))
import data_adapter
import ranker
import runtime


class TeacherGenerationFailed(Exception):
    """Infrastructure errors must not be counted as invalid model answers."""


def past_bundle(args, protocol):
    if (args.cutoff != protocol['cutoff'] or args.max_users != 100 or args.candidate_count != 50
            or args.device != 'cuda' or args.on_invalid != 'fallback'):
        raise ValueError('Use the frozen teacher comparator settings')
    for filename, expected in protocol['source_sha256'].items():
        if sha256(args.data_dir / filename) != expected:
            raise ValueError(f'CSV SHA-256 mismatch: {filename}')
    snapshot = load_slice(args.data_dir, args.cutoff)
    users = starter.select_users(snapshot.profiles, snapshot.history, 'warm', args.max_users, None)
    if snapshot.truth is not None or users != protocol['users'] or set(snapshot.assets) != set(protocol['eligible_assets']):
        raise ValueError('Teacher cohort, eligible assets or no-label condition mismatch')
    features = {isin: starter.tokens(asset) for isin, asset in snapshot.assets.items()}
    pop = starter.popularity_scores(snapshot.history, snapshot.assets)
    contexts, baseline = starter.contexts_for(users, snapshot.assets, snapshot.profiles, snapshot.history,
                                             features, pop, args.cutoff, args.candidate_count, False)
    events, seen = defaultdict(list), set()
    cohort = set(users)
    for row in starter.rows(args.data_dir / 'transactions.csv'):
        day = row['timestamp'][:10]
        if (day >= args.cutoff or row['customerID'] not in cohort or row['transactionType'] != 'Buy'
                or row['ISIN'] not in snapshot.assets or int(row['transactionID']) < 0):
            continue
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            events[row['customerID']].append((day, row['ISIN'], 'Buy'))
    manifest = {'users': users, 'protocol_hash': protocol['protocol_hash'], 'cutoff': args.cutoff,
                'candidate_count': args.candidate_count, 'repeat_allowed': True, 'scored': False,
                'data_sha256': protocol['source_sha256']}
    return starter, snapshot.assets, snapshot.history, None, contexts, baseline, events, pop, manifest


def export_unscored(args, bundle, predictions, failures, method, metadata):
    manifest = bundle[-1]
    path = args.output_dir / 'predictions.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['method', 'user_id', 'rank', 'ISIN'])
        for uid in manifest['users']:
            for name, ranking in predictions[uid].items():
                writer.writerows((name, uid, i, isin) for i, isin in enumerate(ranking, 1))
    (args.output_dir / 'run_manifest.json').write_text(json.dumps(
        dict(manifest, method=method, runtime=metadata, failures=failures), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')


def main(argv=None):
    protocol = json.loads((ROOT / 'protocol.json').read_bytes())
    bundle = json.loads((ROOT / 'manifest.json').read_bytes())
    generation = bundle['generation']
    users = protocol['users']

    def make_backend(model, revision, device, allow_download):
        if model != generation['model'] or revision != generation['revision'] or allow_download:
            raise ValueError('Teacher must use the preverified pinned checkpoint in HF cache')
        started = time.perf_counter()
        backend = original_backend(model, revision, device, allow_download)
        backend.metadata.update(actual_model_dtype=str(next(backend.model.parameters()).dtype),
                                gpu=backend.torch.cuda.get_device_name())
        backend.load_seconds = time.perf_counter() - started
        return backend

    class ResumableTeacher:
        def __init__(self, backend, out):
            self.backend = backend
            self.path = out / 'raw_generations.jsonl'
            check_identity(out / 'resume_identity.json', {'runtime': backend.metadata, 'model_files_sha256':
                           bundle['model_files_sha256'], 'bundle_manifest_sha256': sha256(ROOT / 'manifest.json')})
            self.saved = read_jsonl(self.path)
            if [row['id'] for row in self.saved] != users[:len(self.saved)]:
                raise TeacherGenerationFailed('Teacher journal IDs differ from frozen cohort')
            self.index = 0
            append(out / 'resume_log.jsonl', {'previously_completed': len(self.saved),
                                             'model_load_seconds': backend.load_seconds, 'time_unix': time.time()})

        @property
        def metadata(self):
            return dict(self.backend.metadata, model_load_seconds=self.backend.load_seconds,
                        cached_before_pass=len(self.saved), new_calls=self.index - len(self.saved),
                        generation_seconds=sum(row['seconds'] for row in read_jsonl(self.path)))

        def generate(self, prompt, max_new_tokens=512):
            uid = users[self.index]
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            if self.index < len(self.saved):
                result = self.saved[self.index]
                if result['prompt_sha256'] != digest or result['max_new_tokens'] != max_new_tokens:
                    raise TeacherGenerationFailed('Teacher prompt or settings changed across resume')
            else:
                try:
                    result = self.backend.generate(prompt, max_new_tokens=max_new_tokens)
                except (ValueError, RuntimeError, MemoryError) as exc:
                    raise TeacherGenerationFailed(f'Teacher generation failed before completing ID {self.index + 1}') from exc
                append(self.path, dict(result, id=uid, prompt_sha256=digest, max_new_tokens=max_new_tokens))
            self.index += 1
            return result

    original_backend = runtime.LocalGenerator
    data_adapter.load = lambda args: past_bundle(args, protocol)
    data_adapter.save_results = export_unscored
    runtime.LocalGenerator = make_backend
    runtime.LoggedGenerator = ResumableTeacher
    ranker.main(argv)


if __name__ == '__main__':
    main()
