#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.candidate_assembly import assemble_candidates
from kw_mi_os.contracts import RunManifest, sha256_of_text
from kw_mi_os.evidence_normalization import normalize_evidence
from kw_mi_os.governance import governance_outputs
from kw_mi_os.ingestion import default_source_catalog, fetch_json
from kw_mi_os.models import ExclusionRecord, SignalInput, SourceClass, SourceEvidenceRecord
from kw_mi_os.phase_contracts import PHASE_CONTRACTS
from kw_mi_os.runtime_semantics import RUNTIME_SEMANTICS
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.universe import load_tradable_universe
from kw_mi_os.validation import validate_manifest, validate_quarterly


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['sample', 'live'], default='sample')
    parser.add_argument('--phase', choices=['all', 'ingest', 'score'], default='all')
    parser.add_argument('--sample-mode', action='store_true')
    args = parser.parse_args()

    mode = 'sample' if args.sample_mode else args.mode
    contract = PHASE_CONTRACTS[args.phase]

    universe_file = ROOT / 'config/kuwait_equities_master.csv'
    quarterly_file = ROOT / 'data/quarterly_history.csv'

    tradable = load_tradable_universe(universe_file)
    validate_quarterly(quarterly_file)

    fetch_results = [fetch_json(entry) for entry in default_source_catalog()]
    internet_status = 'ok' if any(r.status == 'ok' for r in fetch_results) else 'fallback_unavailable'

    known_symbols = {u.symbol for u in tradable}
    raw_evidence = [
        {'symbol': 'NBK', 'source_name': 'official_exchange_status', 'source_type': 'official_exchange', 'evidence_type': 'filing', 'polarity': 0.3, 'confidence': 0.9, 'tradable_impact': 1.0, 'timestamp': '2026-04-10T00:00:00Z', 'source_reference': 'ref:nbk'},
        {'symbol': 'ZAIN', 'source_name': 'major_media_feed', 'source_type': 'major_financial_media', 'evidence_type': 'news', 'polarity': 0.1, 'confidence': 0.7, 'tradable_impact': 0.6, 'timestamp': '2026-04-10T00:00:00Z', 'source_reference': 'ref:zain'},
        {'symbol': 'MACRO', 'source_name': 'macro_context_probe', 'source_type': 'macro_context_only', 'evidence_type': 'macro', 'polarity': -0.2, 'confidence': 0.5, 'tradable_impact': 0.4, 'timestamp': '2026-04-10T00:00:00Z', 'source_reference': 'ref:macro'},
    ]
    evidence, quarantined = normalize_evidence(raw_evidence, known_symbols)

    signal_inputs = [
        SignalInput('NBK', 0.08, 0.34, 8_500_000, 14.0, 0.65, 0.92),
        SignalInput('ZAIN', 0.04, 0.22, 7_000_000, 16.0, 0.55, 0.81),
        SignalInput('AGLTY', 0.02, 0.18, 4_000_000, 18.0, 0.4, 0.7),
    ]
    signals = compute_signals(signal_inputs)

    evidence_to_governance = [
        SourceEvidenceRecord('NBK', SourceClass.official_exchange, 0.95, 0.9, 0.88, 0.03, True, 1.0),
        SourceEvidenceRecord('ZAIN', SourceClass.major_financial_media, 0.82, 0.76, 0.7, 0.08, True, 0.7),
        SourceEvidenceRecord('AGLTY', SourceClass.secondary_aggregator, 0.75, 0.7, 0.64, 0.12, True, 0.5),
    ]
    governance = governance_outputs(evidence_to_governance)

    candidates, exclusions, explanations, quality = assemble_candidates(
        tradable=tradable,
        signals=signals,
        governance_by_symbol=governance,
        evidence=evidence,
        run_id='phase2_sample_run',
    )
    exclusions += [
        ExclusionRecord(symbol=str(q['symbol']), blocked_by='entity_resolution', reason=str(q['blocked_by']))
        for q in quarantined
    ]

    (ROOT / 'runtime' / 'candidates').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'quality').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'latest').mkdir(parents=True, exist_ok=True)

    candidates_path = ROOT / 'runtime' / 'candidates' / 'candidates.json'
    exclusions_path = ROOT / 'runtime' / 'quality' / 'exclusions.json'
    explanations_path = ROOT / 'runtime' / 'quality' / 'explanations.json'
    quality_path = ROOT / 'runtime' / 'quality' / 'quality_report.json'

    candidates_path.write_text(json.dumps([c.__dict__ for c in candidates], indent=2), encoding='utf-8')
    exclusions_path.write_text(json.dumps([e.__dict__ for e in exclusions], indent=2), encoding='utf-8')
    explanations_path.write_text(json.dumps(explanations, indent=2), encoding='utf-8')
    quality_path.write_text(json.dumps(quality.__dict__, indent=2), encoding='utf-8')

    latest_snapshot = ROOT / 'runtime' / 'latest' / 'candidates_latest.json'
    latest_snapshot.write_text(candidates_path.read_text(encoding='utf-8'), encoding='utf-8')

    checksums = {
        'config/kuwait_equities_master.csv': sha256_of_text(universe_file.read_text(encoding='utf-8')),
        'data/quarterly_history.csv': sha256_of_text(quarterly_file.read_text(encoding='utf-8')),
    }

    manifest = RunManifest(
        mode=mode,
        phase=args.phase,
        internet_fetch_status=internet_status,
        files_read=list(contract.reads),
        files_written=[str(candidates_path), str(exclusions_path), str(explanations_path), str(quality_path), str(latest_snapshot)],
        validations=['universe_schema', 'quarterly_schema', 'signal_bounds', 'evidence_normalization', 'manifest_schema'],
        warnings=[] if mode == 'sample' else ['live_mode_selected_manual_review_required'],
        failures=[],
        input_checksums=checksums,
    )
    manifest_path = ROOT / 'runtime' / 'latest' / 'run_manifest.json'
    manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    validate_manifest(json.loads(manifest_path.read_text(encoding='utf-8')))

    semantics_path = ROOT / 'runtime' / 'quality' / 'runtime_semantics.json'
    semantics_path.write_text(json.dumps(RUNTIME_SEMANTICS, indent=2), encoding='utf-8')

    print(f'run_phase: mode={mode} phase={args.phase} candidates={len(candidates)} exclusions={len(exclusions)} internet={internet_status}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
