"""As-of-cutoff candidate retrieval and coverage for the frozen HW9 protocol."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor' / 'far-trans'))
import starter


SOURCE_NAMES = ('cbf', 'recency', 'popularity')
RULES = ('P0', 'U1', 'U2', 'U3')


@dataclass
class Slice:
    assets: dict
    profiles: dict
    history: dict
    last_buy: dict
    truth: dict | None


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_inputs(data_dir, package):
    config = read_json(ROOT / 'protocol_hw9.json')
    with ZipFile(package) as archive:
        shared = json.loads(archive.read('protocol.json'))
    digest = shared.pop('protocol_hash')
    if digest != config['development']['protocol_hash'] or digest != hashlib.sha256(
        json.dumps(shared, sort_keys=True).encode()
    ).hexdigest():
        raise ValueError('Shared protocol hash mismatch')
    shared['protocol_hash'] = digest
    for filename, expected in shared['source_sha256'].items():
        if sha256(data_dir / filename) != expected:
            raise ValueError(f'CSV hash mismatch: {filename}')
    return config, shared


def load_slice(data_dir, cutoff, *, horizon_days=None):
    """Use starter eligibility and row policy, with a bounded label window when requested."""
    truth = None
    end = None
    if horizon_days is not None:
        end = (date.fromisoformat(cutoff) + timedelta(days=horizon_days)).isoformat()
        if end > '2021-06-01':
            raise ValueError('Stage 2 cannot load a label window reaching into June')
        truth = defaultdict(set)

    assets = starter.latest_before(data_dir / 'asset_information.csv', 'ISIN', cutoff)
    profiles = starter.latest_before(data_dir / 'customer_information.csv', 'customerID', cutoff)
    priced = {row['ISIN'] for row in starter.rows(data_dir / 'close_prices.csv')
              if row['timestamp'][:10] < cutoff and float(row['closePrice']) > 0}
    assets = {isin: row for isin, row in assets.items() if isin in priced}
    history, last_buy = defaultdict(Counter), defaultdict(dict)
    seen = set()
    for row in starter.rows(data_dir / 'transactions.csv'):
        timestamp = row['timestamp'][:10]
        if timestamp >= cutoff and (end is None or timestamp >= end):
            continue
        asset = row['ISIN']
        if row['transactionType'] != 'Buy' or asset not in assets or int(row['transactionID']) < 0:
            continue
        identity = tuple(sorted(row.items()))
        if identity in seen:
            continue
        seen.add(identity)
        user = row['customerID']
        if timestamp < cutoff:
            history[user][asset] += 1
            last_buy[user][asset] = max(last_buy[user].get(asset, ''), timestamp)
        else:
            truth[user].add(asset)
    return Slice(assets, profiles, history, last_buy, truth)


def candidate_sources(snapshot, users):
    features = {isin: starter.tokens(row) for isin, row in snapshot.assets.items()}
    popularity = starter.order(starter.popularity_scores(snapshot.history, snapshot.assets))
    for uid in users:
        scores = starter.content_scores(snapshot.history.get(uid, {}), features)
        cbf = starter.order(scores)[:50]
        latest = snapshot.last_buy.get(uid, {})
        recency = sorted(latest, key=lambda isin: (-date.fromisoformat(latest[isin]).toordinal(), isin))
        yield uid, {'cbf': cbf, 'recency': recency, 'popularity': popularity}, any(scores.values())


def build_pool(rule, sources, eligible):
    """Return ordered (ISIN, source) pairs, where the source first contributed that ISIN."""
    cbf = sources['cbf']
    if rule == 'P0':
        ordered = [('cbf', cbf[:20])]
    elif rule == 'U1':
        ordered = [(source, sources[source]) for source in ('recency', 'cbf', 'popularity')]
    elif rule == 'U2':
        ordered = [(source, sources[source]) for source in SOURCE_NAMES]
    elif rule == 'U3':
        ordered = [('cbf', cbf[:10]), ('recency', sources['recency']), ('popularity', sources['popularity'])]
    else:
        raise ValueError(f'Unknown pool rule: {rule}')

    pool, seen = [], set()
    active = [(source, iter(items)) for source, items in ordered]
    while active and len(pool) < 20:
        remaining = []
        for source, items in active:
            for isin in items:
                if isin not in eligible or isin in seen:
                    continue
                seen.add(isin)
                pool.append((isin, source))
                if len(pool) == 20:
                    return pool
                if rule == 'U2':
                    remaining.append((source, items))
                    break
        active = remaining
    return pool


def pool_rows(rule, uid, pool):
    return [{'method': rule, 'user_id': uid, 'rank': rank, 'ISIN': isin, 'source': source}
            for rank, (isin, source) in enumerate(pool, 1)]


def coverage(rows, users, truth):
    """Aggregate one pool CSV's rows (method,user_id,rank,ISIN) on an explicit cohort."""
    if not users or len(set(users)) != len(users):
        raise ValueError('Coverage requires a nonempty cohort of unique users')
    ranked = {uid: {} for uid in users}
    methods = set()
    for row in rows:
        uid, rank, isin = row['user_id'], int(row['rank']), row['ISIN']
        if uid not in ranked or rank < 1 or rank in ranked[uid] or not isin:
            raise ValueError('Pool has an invalid user, rank or ISIN')
        ranked[uid][rank] = isin
        methods.add(row['method'])
    if len(methods) > 1:
        raise ValueError('Compute coverage separately for each pool method')

    covered_pairs = all_pairs = buyers_hit = all_buyers = total_size = 0
    oracle, buyer_oracle = [], []
    for uid, slots in ranked.items():
        assets = set(slots.values())
        if len(assets) != len(slots) or set(slots) != set(range(1, len(slots) + 1)):
            raise ValueError('Pool ranks must be contiguous and ISIN unique per user')
        relevant = truth.get(uid, set())
        hits = assets & relevant
        value = starter.ndcg10(sorted(hits), relevant)
        oracle.append(value)
        if relevant:
            buyer_oracle.append(value)
        covered_pairs += len(hits)
        all_pairs += len(relevant)
        buyers_hit += bool(hits)
        all_buyers += bool(relevant)
        total_size += len(assets)
    return {'covered_pairs': covered_pairs, 'all_pairs': all_pairs, 'buyers_hit': buyers_hit,
            'all_buyers': all_buyers, 'oracle_all': sum(oracle) / len(users),
            'oracle_buyers': sum(buyer_oracle) / all_buyers if all_buyers else None,
            'mean_size': total_size / len(users)}
