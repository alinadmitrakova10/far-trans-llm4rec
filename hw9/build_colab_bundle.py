"""Package exact code and verified HW8 reference inputs for the fresh Colab run."""
import subprocess
import zipfile
from pathlib import Path
from verify_hw8 import ROOT, load
from protocol import digest, load_starter
from experiment import save


def main():
    starter = ROOT / 'hw8/reference/starter/starter.py'
    load_starter(starter)
    verification = ROOT / 'hw9/outputs/hw8_reproduction_20261126/verification.json'
    reference = load(verification)
    files = [*sorted((ROOT / 'hw9').glob('*.py')),
             ROOT / 'hw9/requirements-colab.txt', ROOT / 'hw9/requirements-local.txt',
             ROOT / 'hw9/README.md', ROOT / 'hw9/COLAB.md', ROOT / 'hw9/PLAN.md',
             ROOT / 'hw9/notebooks/hw9_fresh_qwen_t4.ipynb',
             *sorted((ROOT / 'hw8/src').glob('*.py')), ROOT / 'hw8/requirements-colab.txt',
             starter, verification]
    for relative, info in reference['inventory'].items():
        path = ROOT / 'hw8/outputs/colab_gpu' / relative
        assert digest(path) == info['sha256'], relative
        files.append(path)
    provenance = dict(git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                      git_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
                      file_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in files})
    manifest = ROOT / 'hw9/outputs/colab_bundle_manifest.json'
    save(manifest, provenance)
    target = ROOT / 'hw9/outputs/hw9_colab_bundle.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(manifest, 'hw9/bundle_manifest.json')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(set(archive.namelist())) == len(archive.namelist())
        for path in files:
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
    print(f'{target}\nSHA256: {digest(target)}\nBytes: {target.stat().st_size}')


if __name__ == '__main__':
    main()
