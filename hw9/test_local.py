"""Focused checks for stratified shuffle and count-sensitive TF-IDF inputs."""
import unittest
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from run import permutation, changed_rows, TFIDF, group_for
from profiles import serialize


class LocalChecks(unittest.TestCase):
    def test_cycles_respect_groups_invalid_singletons_and_duplicate_vectors(self):
        vectors = np.array([[1, 0], [1, 0], [0, 1], [2, 1], [0, 0], [np.nan, 0]], dtype=np.float32)
        counts = [1, 1, 2, 11, 2, 1]
        original = vectors.copy()
        donor, labels, _ = permutation(vectors, counts, 42)
        np.testing.assert_array_equal(donor, [1, 0, 2, 3, 4, 5])
        np.testing.assert_array_equal(donor, permutation(vectors, counts, 42)[0])
        self.assertFalse(changed_rows(vectors, vectors[donor]).any())
        np.testing.assert_array_equal(vectors, original)
        self.assertEqual(labels, ['1', '1', '2-3', '11-30', '2-3', '1'])

    def test_full_group_cycles_are_bijective_without_self_donors(self):
        vectors = np.eye(15, dtype=np.float32)
        counts = [1, 1, 1, 2, 3, 3, 4, 5, 10, 11, 20, 30, 31, 50, 100]
        for seed in range(42, 52):
            donor, labels, _ = permutation(vectors, counts, seed)
            self.assertEqual(sorted(donor.tolist()), list(range(15)))
            self.assertTrue(np.all(donor != np.arange(15)))
            self.assertTrue(all(labels[i] == labels[j] for i, j in enumerate(donor)))
            self.assertTrue(changed_rows(vectors, vectors[donor]).all())
        self.assertEqual([group_for(i) for i in (1, 2, 3, 4, 10, 11, 30, 31)],
                         ['1', '2-3', '2-3', '4-10', '4-10', '11-30', '11-30', '31+'])

    def test_tfidf_retains_single_digit_counts_and_order(self):
        documents = [serialize([dict(assetCategory='Equity', buy_count=n)]) for n in (1, 2, 10)]
        model = TfidfVectorizer(**TFIDF)
        matrix = model.fit_transform(documents).toarray()
        for row, number in enumerate(('1', '2', '10')):
            self.assertIn(number, model.vocabulary_)
            self.assertGreater(matrix[row, model.vocabulary_[number]], 0)
        np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-6)
        np.testing.assert_array_equal(matrix, model.transform(documents).toarray())


if __name__ == '__main__':
    unittest.main()
