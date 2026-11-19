"""Import the unchanged instructor starter and enforce its HW8 defaults."""
import hashlib
import importlib.util
import json
from pathlib import Path

STARTER_SHA256 = 'bf6b7c0b0b271e057e82547eff23738e65bc9cdbb626703d13d1801ff99aab80'
SOURCE_FILES = ('transactions.csv', 'asset_information.csv',
                'customer_information.csv', 'close_prices.csv')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_starter(path):
    if digest(path) != STARTER_SHA256:
        raise ValueError('Starter changed: investigate version before running')
    spec = importlib.util.spec_from_file_location('hw8_instructor_starter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(st, data, baseline):
    protocol = json.loads((baseline / 'protocol.json').read_text(encoding='utf-8'))
    unhashed = {k: v for k, v in protocol.items() if k != 'protocol_hash'}
    assert hashlib.sha256(json.dumps(unhashed, sort_keys=True).encode()).hexdigest() == protocol['protocol_hash']
    assert protocol['cutoff'] == '2021-06-01'
    assert protocol['end_exclusive'] == '2021-07-01'
    assert protocol['exclude_seen'] is False
    assert protocol['initial_positions'] == 'excluded'
    assert protocol['duplicate_policy'] == 'exact full rows only'
    assert protocol['cohort_selection'] == 'warm' and protocol['candidate_count'] == 50
    assert protocol['k'] == 10
    assert protocol['empty_truth_policy'] == 'zero in primary mean; nonempty mean also reported'
    assert protocol['source_sha256'] == {name: digest(data / name) for name in SOURCE_FILES}
    assets, customers, history, truth, end, excluded = st.load_data(data, protocol['cutoff'], 30)
    assert protocol['users'] == st.select_users(customers, history, 'warm', 100, None)
    assert len(protocol['users']) == 100
    assert protocol['eligible_assets'] == sorted(assets)
    assert end == protocol['end_exclusive']
    contexts = [json.loads(line) for line in (baseline / 'contexts.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [c['user_id'] for c in contexts] == protocol['users']
    assert all(c['eligible_asset_ids'] == sorted(assets) and c['cutoff'] == protocol['cutoff'] for c in contexts)
    return protocol, assets, customers, history, truth
