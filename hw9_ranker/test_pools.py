from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from pools import build_pool, coverage, load_slice, pool_rows


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.sources = {'cbf': ['A', 'B', 'C'], 'recency': ['A', 'D', 'B', 'F'],
                        'popularity': ['B', 'E', 'D', 'G', 'X']}
        self.eligible = set('ABCDEFG')

    def test_round_robin_skips_duplicates_and_exhausted_sources(self):
        self.assertEqual(build_pool('U2', self.sources, self.eligible), [
            ('A', 'cbf'), ('D', 'recency'), ('B', 'popularity'),
            ('C', 'cbf'), ('F', 'recency'), ('E', 'popularity'), ('G', 'popularity'),
        ])

    def test_concatenation_and_short_pools(self):
        self.assertEqual(build_pool('P0', self.sources, self.eligible),
                         [('A', 'cbf'), ('B', 'cbf'), ('C', 'cbf')])
        self.assertEqual(build_pool('U1', self.sources, self.eligible), [
            ('A', 'recency'), ('D', 'recency'), ('B', 'recency'), ('F', 'recency'),
            ('C', 'cbf'), ('E', 'popularity'), ('G', 'popularity'),
        ])
        self.assertEqual(build_pool('U3', self.sources, self.eligible), [
            ('A', 'cbf'), ('B', 'cbf'), ('C', 'cbf'), ('D', 'recency'),
            ('F', 'recency'), ('E', 'popularity'), ('G', 'popularity'),
        ])

    def test_cbf_limits_and_pool_position(self):
        cbf = [f'A{i:02}' for i in range(50)]
        sources = {'cbf': cbf, 'recency': ['R', cbf[11]], 'popularity': cbf}
        eligible = set(cbf) | {'R'}
        self.assertEqual(build_pool('P0', sources, eligible), [(isin, 'cbf') for isin in cbf[:20]])
        rows = pool_rows('U3', 'u', build_pool('U3', sources, eligible))
        self.assertEqual([row['rank'] for row in rows], list(range(1, 21)))
        self.assertEqual([(row['ISIN'], row['source']) for row in rows[9:13]],
                         [(cbf[9], 'cbf'), ('R', 'recency'), (cbf[11], 'recency'), (cbf[10], 'popularity')])

    def test_coverage_for_external_rows_and_missing_users(self):
        rows = [{'method': 'external', 'user_id': 'u1', 'rank': rank, 'ISIN': isin}
                for rank, isin in [(2, 'A'), (1, 'X')]]
        stats = coverage(rows, ['u1', 'u2', 'u3'], {'u1': {'A', 'B'}, 'u2': {'C'}})
        self.assertEqual((stats['covered_pairs'], stats['all_pairs'], stats['buyers_hit'], stats['all_buyers']),
                         (1, 3, 1, 2))
        # u1 ideal-in-pool DCG = 1; full IDCG = 1 + 1/log2(3), so score = 0.6131471928.
        # u2 and u3 score 0. Macro scores are 0.6131471928/3 and 0.6131471928/2.
        self.assertAlmostEqual(stats['oracle_all'], 0.2043823976)
        self.assertAlmostEqual(stats['oracle_buyers'], 0.3065735964)
        self.assertEqual(stats['mean_size'], 2 / 3)

    def test_no_june_labels_or_parsing_of_future_transaction_fields(self):
        def rows(path):
            if path.name == 'close_prices.csv':
                return [{'timestamp': '2021-05-01', 'ISIN': 'A', 'closePrice': '5'}]
            return [{'timestamp': '2021-05-01', 'ISIN': 'A', 'transactionType': 'Buy',
                     'transactionID': '1', 'customerID': 'u'}, {'timestamp': '2021-06-01'}]

        with patch('pools.starter.latest_before', return_value={'A': {}}), patch('pools.starter.rows', side_effect=rows):
            june = load_slice(Path('.'), date(2021, 6, 1).isoformat())
            self.assertIsNone(june.truth)
            self.assertEqual(june.history['u']['A'], 1)
            with self.assertRaisesRegex(ValueError, 'reaching into June'):
                load_slice(Path('.'), '2021-06-01', horizon_days=30)


if __name__ == '__main__':
    unittest.main()
