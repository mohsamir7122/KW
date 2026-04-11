from pathlib import Path
from datetime import date
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.evaluation import generate_evaluation_report, track_candidate_outcomes
from kw_mi_os.evidence_normalization import normalize_evidence
from kw_mi_os.governance import governance_outputs
from kw_mi_os.historical_snapshot import build_historical_snapshot
from kw_mi_os.ingestion import FetchResult, SourceCatalogEntry, fetch_json
from kw_mi_os.learning import build_learning_records
from kw_mi_os.models import CandidateRecord, SignalInput, SourceClass, SourceEvidenceRecord
from kw_mi_os.phase_contracts import PHASE_CONTRACTS
from kw_mi_os.ranking import rank_candidates
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.source_growth import build_source_growth_record
from kw_mi_os.universe import load_tradable_universe
from kw_mi_os.validation import (
    validate_candidate_outcomes,
    validate_evaluation_report,
    validate_historical_snapshot,
    validate_learning_records,
    validate_manifest,
    validate_quarterly,
    validate_source_growth_record,
    validate_universe,
)


def _sample_pipeline_inputs():
    universe = load_tradable_universe(ROOT / 'config/kuwait_equities_master.csv')
    known_symbols = {u.symbol for u in universe}
    evidence, quarantined = normalize_evidence([
        {'symbol': 'NBK', 'source_name': 'official_exchange_status', 'source_type': 'official_exchange', 'evidence_type': 'filing', 'polarity': 0.3, 'confidence': 0.9, 'tradable_impact': 1.0, 'timestamp': '2026-04-10T00:00:00Z', 'source_reference': 'ref:nbk'},
        {'symbol': 'ZAIN', 'source_name': 'major_media_feed', 'source_type': 'major_financial_media', 'evidence_type': 'news', 'polarity': 0.1, 'confidence': 0.7, 'tradable_impact': 0.6, 'timestamp': '2026-04-10T00:00:00Z', 'source_reference': 'ref:zain'},
    ], known_symbols)
    quarterly = validate_quarterly(ROOT / 'data/quarterly_history.csv')
    return universe, quarterly, evidence, quarantined


def test_signal_computation_bounds_and_missing_penalty():
    signals = compute_signals([SignalInput('NBK', None, 0.3, 5_000_000, 15, 0.5, 0.9)])
    s = signals['NBK']
    assert 0 <= s.trend_signal <= 1
    assert 0 <= s.quality_signal <= 1
    assert s.missing_data_penalty > 0


def test_entity_resolution_rejects_context_in_normalization():
    normalized, quarantined = normalize_evidence([
        {'symbol': 'MACRO', 'source_name': 'x', 'source_type': 'macro_context_only', 'evidence_type': 'macro', 'polarity': 0, 'confidence': 0.5, 'tradable_impact': 0.3, 'timestamp': '2026-04-10T00:00:00Z'}
    ], {'NBK'})
    assert normalized == []
    assert quarantined and quarantined[0]['blocked_by'] == 'context_entity'


def test_governance_boundary_macro_no_contribution():
    outputs = governance_outputs([
        SourceEvidenceRecord(source='macro', source_class=SourceClass.macro_context_only, parser_success=1, completeness=1, freshness=1, conflict_penalty=0, impacted_tradable=True, impact=4)
    ])
    assert outputs['macro'].contribution_score == 0.0


def test_ranking_no_double_counting_of_trust():
    universe = load_tradable_universe(ROOT / 'config/kuwait_equities_master.csv')
    signals = compute_signals([SignalInput('NBK', 0.1, 0.3, 8_000_000, 12, 0.7, 0.9)])
    gov = {'NBK': governance_outputs([
        SourceEvidenceRecord(source='NBK', source_class=SourceClass.official_exchange, parser_success=1, completeness=1, freshness=1, conflict_penalty=0, impacted_tradable=True, impact=1)
    ])['NBK']}
    ranked = rank_candidates(universe, signals, gov)
    nbk = [r for r in ranked if r.symbol == 'NBK'][0]
    assert nbk.final_score == round(nbk.base_signal * nbk.trust_score, 4)


def test_phase_contracts_defined_and_idempotent():
    assert set(PHASE_CONTRACTS.keys()) == {'all', 'ingest', 'score', 'phase3'}
    assert all(v.idempotent for v in PHASE_CONTRACTS.values())
    assert PHASE_CONTRACTS['phase3'].outputs


def test_historical_snapshot_validation_and_point_in_time_behavior():
    _, quarterly, evidence, _ = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_1',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    validate_historical_snapshot(snapshot)
    assert all(s.quarter_end <= snapshot.as_of_date for s in snapshot.equity_state)

def test_outcome_tracking_and_invalid_entity_join_rejection():
    _, quarterly, evidence, _ = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_2',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    candidates = [CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x')]
    outcomes = track_candidate_outcomes(
        candidates=candidates,
        snapshot=snapshot,
        observed_outcomes_by_symbol={'NBK': 0.04},
        explanations_by_symbol={'NBK': {'missing_data_penalties': 0.02}},
    )
    validate_candidate_outcomes(outcomes)
    assert outcomes[0].outcome_status == 'candidate_outcome_observed'

    with pytest.raises(ValueError):
        track_candidate_outcomes(
            candidates=[CandidateRecord(symbol='MISSING', base_signal=0.1, trust_score=0.8, final_score=0.08, reason='x')],
            snapshot=snapshot,
            observed_outcomes_by_symbol={},
            explanations_by_symbol={},
        )


def test_learning_and_source_growth_artifact_structures():
    _, quarterly, evidence, quarantined = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_3',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    outcomes = track_candidate_outcomes(
        candidates=[CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x')],
        snapshot=snapshot,
        observed_outcomes_by_symbol={'NBK': 0.02},
        explanations_by_symbol={'NBK': {'contributing_factors': {'base_signal': 0.4, 'trust_score': 0.9}, 'top_contributing_signals': {'trend_signal': 0.7, 'quality_signal': 0.6, 'liquidity_signal': 0.5}, 'missing_data_penalties': 0.01}},
    )
    learning = build_learning_records(snapshot_id=snapshot.snapshot_id, outcomes=outcomes, explanations_by_symbol={})
    validate_learning_records(learning)
    assert learning and 'realized_return' in learning[0].outcome

    source_growth = build_source_growth_record(
        snapshot=snapshot,
        evidence=evidence,
        quarantined=quarantined,
        candidate_symbols=['NBK'],
    )
    validate_source_growth_record(source_growth)
    assert source_growth.source_acceptance_rejection_counts


def test_evaluation_report_generation():
    _, quarterly, evidence, _ = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_4',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    outcomes = track_candidate_outcomes(
        candidates=[CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x')],
        snapshot=snapshot,
        observed_outcomes_by_symbol={'NBK': 0.03},
        explanations_by_symbol={'NBK': {'top_contributing_signals': {'trend_signal': 0.7}}},
    )
    report = generate_evaluation_report(snapshot=snapshot, outcomes=outcomes, explanations_by_symbol={'NBK': {'top_contributing_signals': {'trend_signal': 0.7}}})
    validate_evaluation_report(report)
    assert report.observed_count == 1


def test_run_phase_publishes_required_artifacts_and_manifest_enrichment():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    required = [
        ROOT / 'runtime/candidates/candidates.json',
        ROOT / 'runtime/quality/exclusions.json',
        ROOT / 'runtime/quality/explanations.json',
        ROOT / 'runtime/quality/quality_report.json',
        ROOT / 'runtime/learning/evaluation_snapshot.json',
        ROOT / 'runtime/learning/candidate_outcomes.json',
        ROOT / 'runtime/learning/learning_records.json',
        ROOT / 'runtime/source_growth/source_growth_report.json',
        ROOT / 'runtime/quality/evaluation_quality_report.json',
        ROOT / 'runtime/latest/evaluation_latest.json',
        ROOT / 'runtime/latest/run_manifest.json',
    ]
    for p in required:
        assert p.exists()

    manifest = json.loads((ROOT / 'runtime/latest/run_manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest)
    assert 'historical_snapshot_schema' in manifest['validations']


def test_runtime_git_tracking_policy_only_gitkeep():
    tracked = subprocess.check_output(['git', 'ls-files', 'runtime']).decode().strip().splitlines()
    assert all(p.endswith('.gitkeep') for p in tracked)


def test_reference_data_validation_passes():
    assert len(validate_universe(ROOT / 'config/kuwait_equities_master.csv')) >= 4
    assert len(validate_quarterly(ROOT / 'data/quarterly_history.csv')) >= 3


def test_negative_path_malformed_universe(tmp_path: Path):
    bad = tmp_path / 'bad.csv'
    bad.write_text('symbol,broken\nNBK,x\n', encoding='utf-8')
    with pytest.raises(ValueError):
        validate_universe(bad)


def test_ingestion_fallback_behavior(monkeypatch):
    def fake_urlopen(*args, **kwargs):  # noqa: ARG001
        raise OSError('network down')

    import kw_mi_os.ingestion as ingestion

    monkeypatch.setattr(ingestion, 'urlopen', fake_urlopen)
    result = fetch_json(SourceCatalogEntry('x', SourceClass.official_exchange, 'https://example.com'))
    assert isinstance(result, FetchResult)
    assert result.status == 'fallback_unavailable'


def test_deterministic_sample_mode_outputs():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    first = (ROOT / 'runtime/latest/evaluation_latest.json').read_text(encoding='utf-8')
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    second = (ROOT / 'runtime/latest/evaluation_latest.json').read_text(encoding='utf-8')
    assert first == second
