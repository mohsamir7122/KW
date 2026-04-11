#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.runtime_semantics import RUNTIME_SEMANTICS
from kw_mi_os.validation import validate_quarterly, validate_universe

REQUIRED_PATHS = [
    Path('.github/workflows/market-intelligence-os.yml'),
    Path('config/kuwait_equities_master.csv'),
    Path('data/quarterly_history.csv'),
    Path('scripts/run_phase.py'),
    Path('scripts/smoke_test.py'),
    Path('tests/test_rules.py'),
]


def main() -> int:
    missing = [str(p) for p in REQUIRED_PATHS if not p.exists()]
    if missing:
        print('Missing required paths:', ', '.join(missing))
        return 1

    validate_universe(ROOT / 'config/kuwait_equities_master.csv')
    validate_quarterly(ROOT / 'data/quarterly_history.csv')

    for runtime_dir in RUNTIME_SEMANTICS:
        if not (ROOT / runtime_dir).exists():
            print(f'Missing runtime directory: {runtime_dir}')
            return 1

    tracked_runtime = subprocess.check_output(['git', 'ls-files', 'runtime']).decode('utf-8').strip().splitlines()
    if any(not p.endswith('.gitkeep') for p in tracked_runtime):
        print('Runtime artifacts tracked in git. Keep runtime structure-only in git.')
        return 1

    print('bootstrap_audit: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
