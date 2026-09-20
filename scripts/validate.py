"""One repeatable local validation entrypoint; no training, capture or remote jobs."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-only', action='store_true', help='omit optional NumPy/PyTorch ML suites')
    args = parser.parse_args()
    suites = ['core/contracts/tests', 'tests/runtime', 'tests/integration']
    if not args.runtime_only:
        suites += ['training/tests', 'analyzers/tests', 'benchmarks/tests']
    for path in suites:
        subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', path, '-q'], cwd=ROOT, check=True)
    tests = [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tests/ui').glob('*.test.mjs'))]
    if not tests:
        raise RuntimeError('UI test suite missing')
    subprocess.run(['node', '--test', *tests], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-B', 'docs/implementation/checkpoint1_smoke.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-B', 'tests/ui/live_reference_smoke.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-B', 'scripts/release_audit.py', '--self-test'], cwd=ROOT, check=True)
    print('ALL SELECTED VALIDATION PASSED; no empirical or hardware claim.')


if __name__ == '__main__':
    main()
