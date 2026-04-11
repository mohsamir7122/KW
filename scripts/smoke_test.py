#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.entity_resolution import resolve_to_canonical_symbol
from kw_mi_os.governance import governance_outputs
from kw_mi_os.models import SignalInput, SourceClass, SourceEvidenceRecord
from kw_mi_os.ranking import rank_candidates
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.universe import load_tradable_universe


def main() -> int:
    universe = load_tradable_universe(ROOT / 'config/kuwait_equities_master.csv')
    known_symbols = {r.symbol for r in universe}
    assert resolve_to_canonical_symbol('macro', known_symbols).canonical_symbol is None
    assert resolve_to_canonical_symbol('nbk.kw', known_symbols).canonical_symbol == 'NBK'

    signals = compute_signals([
        SignalInput('NBK', 0.08, 0.3, 8_000_000, 14, 0.6, 0.9),
        SignalInput('ZAIN', 0.03, 0.22, 7_000_000, 16, 0.55, 0.8),
    ])
    gov = governance_outputs([
        SourceEvidenceRecord('NBK', SourceClass.official_exchange, 0.95, 0.9, 0.85, 0.05, True, 1.1)
    ])
    ranked = rank_candidates(universe, signals, gov)
    if not ranked or ranked[0].reason == '':
        print('smoke_test: ranking/explainability failed')
        return 1
    print('smoke_test: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
