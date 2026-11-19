"""Same-information purchase profiles; no labels, names or IDs in encoder inputs."""
import json
from collections import Counter, defaultdict
from datetime import date

FIELDS = ('assetCategory', 'assetSubCategory', 'sector', 'industry')
INSTRUCTION = ('Represent this past-purchase category profile for finding users with '
               'similar purchase preferences. Use only the supplied categories, purchase '
               'counts and recency buckets; do not infer additional facts.')
MAX_TOKENS = 512


def serialize(profile):
    return '\n'.join(json.dumps(row, ensure_ascii=False, separators=(',', ':'))
                     for row in profile) or 'No past purchases.'


def model_input(profile):
    return f'Instruct: {INSTRUCTION}\nQuery: {serialize(profile)}'


def build_profiles(users, assets, history, events, cutoff):
    """Use starter's selected as-of asset row, including first-row date ties."""
    result = {}
    for uid in users:
        counts, last = Counter(), {}
        observed = Counter()
        for stamp, isin, kind in events.get(uid, ()):
            assert stamp < cutoff
            if kind != 'Buy':
                continue
            observed[isin] += 1
            attrs = tuple(assets[isin].get(f, '').strip() or 'UNKNOWN' for f in FIELDS)
            counts[attrs] += 1
            last[attrs] = max(last.get(attrs, stamp), stamp)
        assert observed == history[uid], 'Profile scan differs from starter history'
        profile = []
        for attrs in sorted(counts):
            days = (date.fromisoformat(cutoff) - date.fromisoformat(last[attrs])).days
            bucket = '0-30 days' if days <= 30 else ('31-180 days' if days <= 180 else '>180 days')
            profile.append(dict(zip(FIELDS, attrs), buy_count=counts[attrs], recency=bucket))
        result[uid] = profile
    return result


def shared_token_limit(profiles, tokenizer):
    """Keep lexicographic complete-row prefix within 512 tokens, for BOTH encoders.

    Never tokenizer-truncate only Qwen. Deduplicate identical profiles first.
    """
    cache, result, audit = {}, {}, {}
    for uid, original in profiles.items():
        key = serialize(original)
        if key not in cache:
            kept = list(original)
            original_tokens = len(tokenizer(model_input(kept))['input_ids'])
            while len(tokenizer(model_input(kept))['input_ids']) > MAX_TOKENS:
                if not kept:
                    raise ValueError('Instruction alone exceeds token budget')
                kept.pop()
            cache[key] = (kept, original_tokens,
                          len(tokenizer(model_input(kept))['input_ids']))
        kept, before, after = cache[key]
        result[uid] = kept
        audit[uid] = dict(original_rows=len(original), retained_rows=len(kept),
                          original_tokens=before, retained_tokens=after)
    return result, audit


def structured_vectors(profiles, users):
    """Count-weighted one-hot marginals + joint tuple + joint tuple/recency.

    Exact counts and recency are retained in joint features. No IDF or test fit.
    """
    import numpy as np
    rows, vocabulary = [], set()
    for uid in users:
        features = defaultdict(float)
        for row in profiles[uid]:
            count = row['buy_count']
            for field in FIELDS:
                features[json.dumps([field, row[field]])] += count
            joint = [row[f] for f in FIELDS]
            features[json.dumps(['joint', *joint])] += count
            features[json.dumps(['joint_recency', *joint, row['recency']])] += count
        rows.append(features)
        vocabulary.update(features)
    vocabulary = sorted(vocabulary)
    index = {key: i for i, key in enumerate(vocabulary)}
    vectors = np.zeros((len(users), len(vocabulary)), dtype=np.float32)
    for r, features in enumerate(rows):
        for key, value in features.items():
            vectors[r, index[key]] = value
    return vectors, vocabulary
