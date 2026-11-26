"""CPU integration check of the fresh path with explicitly mocked GPU inference.

Requires local HW8 references/data. Does not produce experimental Qwen results.
"""
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

import run
import qwen
from summarize import summarize
from experiment import read_csv


def main():
    notebook = json.loads((run.ROOT / 'hw9/notebooks/hw9_fresh_qwen_t4.ipynb').read_text(encoding='utf-8'))
    cells = [c for c in notebook['cells'] if c['cell_type'] == 'code']
    for i, cell in enumerate(cells, 1):
        assert cell['execution_count'] is None and cell['outputs'] == []
        compile(''.join(cell['source']), f'colab_cell_{i}', 'exec')
    print(f'Notebook: {len(cells)} code cells compile; no saved outputs.')
    enc = run.ROOT / 'hw8/outputs/colab_gpu/encoders'
    profiles, truncation = run.load(enc / 'profiles.json'), run.load(enc / 'truncation.json')
    # Deliberately different from the saved matrix: prove all fresh consumers
    # use embed()'s return value, not the old Qwen reference.
    fresh = np.roll(np.load(enc / 'qwen_knn/vectors.npy'), 1, axis=0)
    calls = []

    def fake_embed(texts, tok, batch_size, device):
        assert texts == [run.model_input(profiles[u]) for u in run.load(enc / 'neighbor_users.json')]
        assert batch_size == 8 and device == 'cuda'
        calls.append(True)
        return fresh.copy(), dict(model_load_seconds=0.0, inference_seconds=0.0,
                                  failures=[], hardware='CPU TEST MOCK; NOT QWEN INFERENCE')

    def fake_limit(original, tok):
        for uid, profile in profiles.items():
            assert original[uid][:len(profile)] == profile
        return profiles, truncation

    with tempfile.TemporaryDirectory(prefix='hw9_colab_check_', dir=run.ROOT / 'hw9/outputs') as directory:
        out = Path(directory) / 'mocked_fresh_test'
        with patch('sys.argv', ['run.py', '--fresh-qwen', '--output-dir', str(out)]), \
             patch.object(qwen, 'tokenizer', return_value=object()), \
             patch.object(qwen, 'embed', side_effect=fake_embed), \
             patch.object(run, 'shared_token_limit', side_effect=fake_limit), \
             contextlib.redirect_stdout(io.StringIO()):
            run.main()
            summarize(out)
        assert calls == [True]
        np.testing.assert_array_equal(np.load(out / 'qwen_knn/vectors.npy'), fresh)
        neighbors = run.load(out / 'neighbor_users.json')
        for seed in range(42, 52):
            donors = read_csv(out / f'qwen_shuffle_{seed}/donors.csv')
            assert [r['user_id'] for r in donors] == neighbors
        personal = out / 'personal_check/870E814DB274CFA95600'
        assert run.load(personal / 'unique_relevant_isins.json') == ['GRS014003032', 'GRS191213008']
        assert len(read_csv(personal / 'june_buy_source_rows.csv')) == 3
        for method in ('qwen_knn', 'tfidf_knn'):
            assert len(read_csv(personal / f'{method}_top10.csv')) == 10
            assert len(read_csv(personal / f'{method}_per_user.csv')) == 1
        assert (out / 'RESULTS.md').exists()
    print('Fresh pipeline: passed on full slice with MOCKED tokenizer/inference; real T4 inference not run.')


if __name__ == '__main__':
    main()
