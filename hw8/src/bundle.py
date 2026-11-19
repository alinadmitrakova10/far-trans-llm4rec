"""Build uploadable workflow ZIP, never data/model/results; outputs are ignored."""
from pathlib import Path
import zipfile
from protocol import load_starter

ROOT = Path(__file__).resolve().parents[2]


def main():
    starter = ROOT / 'hw8/reference/starter/starter.py'
    load_starter(starter)
    target = ROOT / 'hw8/outputs/workflow_bundle.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / 'hw8/src').glob('*.py'))
    files += [ROOT / 'hw8/requirements-colab.txt', ROOT / 'hw8/README.md', starter]
    files += [starter.parent / n for n in ('README.md', 'test_starter.py', 'extensions.py')]
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == sorted(p.relative_to(ROOT).as_posix() for p in files)
        for path in files:
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
    print(target)


if __name__ == '__main__':
    main()
