"""Fit the registered LambdaMART grid, select on May and freeze the winner."""

import json
import os
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
import time

import joblib
import lightgbm as lgb
import numpy as np
from scipy import sparse

from pools import ROOT, read_json, sha256, write_json
from prepare_pools import HW8
from input_contract import canonical, digest
from ranker_features import RankerFeatures
from ranker_metrics import evaluate


def load_prepared(pools_dir, slices):
    payloads = {'train': [], 'validation': [], 'development': []}
    train_groups, valid_groups, valid_mappings = [], [], []
    for entry in slices:
        role, cutoff = entry['role'], entry['cutoff']
        filenames = {f'pools_{cutoff}.csv', f'payloads_{cutoff}.jsonl'}
        if role != 'development':
            filenames.add(f'labels_{cutoff}.json')
        if filenames != entry['files_sha256'].keys():
            raise ValueError(f'Unexpected set of frozen files at {cutoff}')
        for name in filenames:
            if sha256(pools_dir / name) != entry['files_sha256'][name]:
                raise ValueError(f'Frozen artifact changed: {name}')
        entries = [json.loads(line) for line in (pools_dir / f'payloads_{cutoff}.jsonl').read_bytes().splitlines()]
        if (len(entries) != entry['groups'] or any(payload['cutoff'] != cutoff for payload in entries)):
            raise ValueError(f'Frozen payloads disagree with cutoff {cutoff}')
        payloads[role].extend(entries)
        if role == 'development':
            continue
        supervision = read_json(pools_dir / f'labels_{cutoff}.json')
        for payload, group in zip(entries, supervision['groups'], strict=True):
            aliases = [candidate['asset_alias'] for candidate in payload['candidates']]
            if (payload['user_alias'] != group['group_key'] or aliases != group['candidate_aliases']
                    or len(group['labels']) != len(aliases)):
                raise ValueError(f'Candidate and label alignment mismatch at {cutoff}')
        if role == 'train':
            train_groups.extend(supervision['groups'])
        else:
            valid_groups.extend(supervision['groups'])
            valid_mappings.extend(supervision['mappings'])
    return payloads, train_groups, valid_groups, valid_mappings


def build_features(out, payloads, text_settings):
    started = time.perf_counter()
    encoder = RankerFeatures(text_settings).fit([p for p in payloads['train'] if p['candidates']])
    fit_state = canonical(encoder.fitted_state())
    joblib.dump(encoder, out / 'train_encoder.joblib')
    fit_seconds = time.perf_counter() - started
    matrices, seconds = {}, {}
    for role, entries in payloads.items():
        started = time.perf_counter()
        nonempty = [payload for payload in entries if payload['candidates']]
        matrix = encoder.transform(nonempty) if nonempty else sparse.csr_matrix((0, encoder.feature_count))
        if matrix.shape[0] != sum(len(payload['candidates']) for payload in entries):
            raise ValueError(f'Feature row count mismatch for {role}')
        sparse.save_npz(out / f'{role}_X.npz', matrix)
        matrices[role] = matrix
        seconds[role] = time.perf_counter() - started
    if fit_state != canonical(encoder.fitted_state()):
        raise ValueError('Applying the encoder changed its train-fitted state')
    return matrices, {'fit_and_save_seconds': fit_seconds, 'transform_and_save_seconds': seconds,
                      'total_seconds': fit_seconds + sum(seconds.values()),
                      'shapes': {role: list(matrix.shape) for role, matrix in matrices.items()},
                      'train_fitted_state_sha256': digest(fit_state)}


def train_grid(out, config, train, validation, train_groups, valid_groups, valid_mappings):
    sizes = [len(group['labels']) for group in train_groups if group['labels']]
    labels = np.asarray([label for group in train_groups for label in group['labels']], dtype=np.int8)
    if len(labels) != train.shape[0] or len(labels) != sum(sizes):
        raise ValueError('Training matrix, labels and group sizes disagree')
    dataset = lgb.Dataset(train, label=labels, group=sizes, free_raw_data=False)
    control_scores = [-rank for group in valid_groups for rank in range(len(group['labels']))]
    reference, _, _ = evaluate(control_scores, valid_groups, valid_mappings)
    records, models = [], {}
    seed = config['selection_seed']
    threads = config['base_parameters']['num_threads']
    grid_started = time.perf_counter()
    for item in config['grid']:
        params = dict(config['base_parameters'], objective=config['objective'], num_leaves=item['num_leaves'],
                      seed=seed, feature_fraction_seed=seed, bagging_seed=seed)
        started = time.perf_counter()
        model = lgb.train(params, dataset, num_boost_round=item['num_boost_round'])
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        scores = model.predict(validation, num_threads=threads)
        predict_seconds = time.perf_counter() - started
        metrics, _, _ = evaluate(scores, valid_groups, valid_mappings)
        models[item['id']] = model
        records.append({**item, 'actual_trees': model.num_trees(), 'seed': seed, 'metrics': metrics,
                        'fit_seconds': fit_seconds, 'validation_predict_seconds': predict_seconds})
        print(f'{item["id"]}: {metrics["ndcg_at_10"]:.4f} / {metrics["ndcg_at_10_nonempty"]:.4f}; '
              f'fit {fit_seconds:.4f} s', flush=True)
    elapsed = time.perf_counter() - grid_started
    best = min(records, key=lambda row: (-row['metrics']['ndcg_at_10'], row['num_boost_round'],
                                        row['num_leaves'], row['id']))
    models[best['id']].save_model(str(out / 'model.txt'))
    print(f'Initial order: {reference["ndcg_at_10"]:.4f} / {reference["ndcg_at_10_nonempty"]:.4f}; '
          f'frozen: {best["id"]}', flush=True)
    return {'matched_control': reference, 'grid': records, 'selected_configuration': best['id'],
            'fit_seconds_total': sum(row['fit_seconds'] for row in records),
            'grid_wall_seconds': elapsed, 'threads': threads}


def main():
    stage = ROOT / 'outputs' / 'stage2'
    final = stage / 'lambdamart'
    if final.exists():
        raise FileExistsError('LambdaMART artifacts are frozen and will not be overwritten')
    protocol = read_json(ROOT / 'protocol_hw9.json')
    lm = protocol['methods']['lambdamart']
    config_path = ROOT.parent / lm['base_config']
    config = read_json(config_path)
    actual_grid = {(row['num_leaves'], row['num_boost_round']) for row in config['grid']}
    expected_grid = {(leaves, rounds) for leaves in lm['num_leaves_grid'] for rounds in lm['num_boost_round_grid']}
    if (lgb.__version__ != config['lightgbm_version'] or lgb.__version__ != lm['lightgbm_version']
            or config['selection_seed'] != lm['selection_seed'] or config['objective'] != lm['objective']
            or len(config['grid']) != len(expected_grid) or actual_grid != expected_grid):
        raise ValueError('LightGBM environment or grid disagrees with the registered protocol')

    pools_dir = stage / 'pools'
    manifest_path = pools_dir / 'manifest.json'
    manifest = read_json(manifest_path)
    expected_cuts = [(cut, 'train') for cut in lm['train_cutoffs']]
    expected_cuts += [(lm['validation_cutoff'], 'validation'), (protocol['development']['cutoff'], 'development')]
    if ([(entry['cutoff'], entry['role']) for entry in manifest['slices']] != expected_cuts
            or manifest['protocol_hash'] != protocol['development']['protocol_hash']):
        raise ValueError('Frozen pool manifest disagrees with the registered cuts or protocol hash')
    payloads, train_groups, valid_groups, valid_mappings = load_prepared(pools_dir, manifest['slices'])
    text_settings = read_json(HW8 / 'TEMPORAL_CONFIG.json')['text_settings']
    with TemporaryDirectory(dir=stage, prefix='train-') as scratch:
        artifacts = Path(scratch) / 'lambdamart'
        artifacts.mkdir()
        matrices, features = build_features(artifacts, payloads, text_settings)
        grid = train_grid(artifacts, config, matrices['train'], matrices['validation'],
                          train_groups, valid_groups, valid_mappings)
        result = {'rule': manifest['rule'], 'pools_manifest_sha256': sha256(manifest_path),
                  'lightgbm_config_sha256': sha256(config_path), 'features': features, 'training': grid,
                  'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                                  'lightgbm': lgb.__version__, 'logical_cpu_count': os.cpu_count()},
                  'files_sha256': {path.name: sha256(path) for path in sorted(artifacts.iterdir())}}
        write_json(artifacts / 'manifest.json', result)
        artifacts.rename(final)
    print(json.dumps(result['files_sha256'], indent=2))


if __name__ == '__main__':
    main()
