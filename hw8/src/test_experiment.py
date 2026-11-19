"""Meaningful scorer and temporal isolation checks; no model downloads/inference."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import numpy as np

from profiles import build_profiles, shared_token_limit, structured_vectors
from protocol import load_starter
from scorer import recommend

STARTER = Path(__file__).resolve().parents[1] / 'reference/starter/starter.py'
st = load_starter(STARTER)
spec = importlib.util.spec_from_file_location('starter_fixture', STARTER.with_name('test_starter.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ExperimentChecks(unittest.TestCase):
    def test_future_mutation_cannot_change_profiles_or_recommendations(self):
        results = []
        for variant in ('base', 'mutated'):
            with tempfile.TemporaryDirectory() as tmp:
                data = Path(tmp)
                fixture.write_fixture(data, future_variant=variant)
                assets, customers, history, truth, _, _ = st.load_data(data, '2021-06-01', 30)
                users = sorted(u for u in customers if history.get(u))
                profiles = build_profiles(users, assets, history,
                                          st.scan_recent_events(data, '2021-06-01', assets), '2021-06-01')
                vectors, _ = structured_vectors(profiles, users)
                ranks, _ = recommend(vectors, users, users, history, assets, st.popularity_scores(history, assets))
                results.append((profiles, ranks))
        self.assertEqual(results[0], results[1])

    def test_self_exclusion_negative_cosine_ties_and_fallback(self):
        catalog = list('ABCDEFGHIJKL')
        users = ['a', 'b', 'c', 'd']
        # b/c tie, a's own purchase L must not receive a vote; d negative excluded.
        z = np.array([[1, 0], [1, 1], [1, -1], [-1, 0]], dtype=np.float32)
        history = {'a': {'L': 1}, 'b': {'B': 1}, 'c': {'A': 1}, 'd': {'D': 1}}
        pop = dict.fromkeys(catalog, 0)
        pop['K'] = 3
        ranks, audit = recommend(z, users, ['a'], history, catalog, pop)
        self.assertEqual(ranks['a'][:3], ['A', 'B', 'C'])
        self.assertEqual(audit['users']['a']['neighbors'], ['b', 'c'])
        z[0] = 0
        ranks, audit = recommend(z, users, ['a'], history, catalog, pop)
        self.assertEqual(ranks['a'][0], 'K')
        self.assertTrue(audit['users']['a']['fallback'])

    def test_shared_truncation_removes_whole_rows(self):
        class Tokenizer:
            def __call__(self, text):
                return {'input_ids': list(range(len(text)))}
        profiles = {'u': [{'test': 'x' * 200}, {'test': 'y' * 200}]}
        kept, audit = shared_token_limit(profiles, Tokenizer())
        self.assertEqual(kept['u'], profiles['u'][:1])
        self.assertEqual(audit['u']['retained_rows'], 1)


if __name__ == '__main__':
    unittest.main()
