"""Re-run the real baseline and compare all five deterministic artifacts bytewise."""
from experiment import ROOT, baseline, save
from protocol import digest


def main():
    out = ROOT / 'hw8/outputs/local'
    starter = ROOT / 'hw8/reference/starter/starter.py'
    baseline(starter, ROOT / 'data/raw/FAR-Trans/FAR-Trans', out / 'reproduced')
    hashes = {}
    for name in ('protocol.json', 'contexts.jsonl', 'predictions.csv', 'per_user.csv', 'metrics.json'):
        first = digest(out / 'baseline' / name)
        second = digest(out / 'reproduced/baseline' / name)
        assert first == second, name
        hashes[name] = first
    save(out / 'reproducibility.json', dict(status='five artifacts byte-identical on real-data rerun', sha256=hashes))
    print('Real-data baseline rerun: five artifacts byte-identical.')


if __name__ == '__main__':
    main()
