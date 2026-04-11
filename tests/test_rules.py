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
from kw_mi_os.models import (
    AlertRecord,
    CalibratedSignalRecord,
    CandidateRecord,
    DecisionQualityReport,
    FailureRecord,
    FreshnessCheck,
    HealthStatusReport,
    PhaseCompletionRecord,
    PortfolioProposal,
    PortfolioQualityReport,
    PortfolioSnapshot,
    RebalanceAction,
    RiskControlCheck,
    RiskControlResult,
    SignalInput,
    SourceClass,
    SourceEvidenceRecord,
)
from kw_mi_os.phase4 import (
    build_benchmark_result,
    build_decision_quality_report,
    build_signal_usefulness_report,
    calibrate_signals,
)
from kw_mi_os.phase5 import apply_risk_controls, build_alerts, construct_portfolio_proposal, plan_rebalance
from kw_mi_os.phase6 import build_phase6_status
from kw_mi_os.phase_contracts import PHASE_CONTRACTS
from kw_mi_os.ranking import rank_candidates
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.source_growth import build_source_growth_record
from kw_mi_os.universe import load_tradable_universe
from kw_mi_os.validation import (
    validate_candidate_outcomes,
    validate_benchmark_result,
    validate_calibrated_signals,
    validate_calibration_metadata,
    validate_decision_quality_report,
    validate_evaluation_report,
    validate_failure_records,
    validate_freshness_checks,
    validate_health_status_report,
    validate_historical_snapshot,
    validate_learning_records,
    validate_manifest,
    validate_portfolio_proposal,
    validate_portfolio_snapshot_compatibility,
    validate_quarterly,
    validate_rebalance_actions,
    validate_risk_control_result,
    validate_operating_run_record,
    validate_operating_status_snapshot,
    validate_scheduler_status,
    validate_source_growth_record,
    validate_signal_usefulness_report,
    validate_alert_records,
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
    assert set(PHASE_CONTRACTS.keys()) == {'all', 'ingest', 'score', 'phase3', 'phase4', 'phase5', 'phase6'}
    assert all(v.idempotent for v in PHASE_CONTRACTS.values())
    assert PHASE_CONTRACTS['phase3'].outputs
    assert PHASE_CONTRACTS['phase4'].outputs
    assert PHASE_CONTRACTS['phase5'].outputs
    assert PHASE_CONTRACTS['phase6'].outputs


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
        ROOT / 'runtime/learning/calibrated_signals.json',
        ROOT / 'runtime/learning/signal_usefulness_report.json',
        ROOT / 'runtime/quality/benchmark_report.json',
        ROOT / 'runtime/quality/decision_quality_report.json',
        ROOT / 'runtime/latest/evaluation_latest.json',
        ROOT / 'runtime/latest/benchmark_latest.json',
        ROOT / 'runtime/latest/decision_quality_latest.json',
        ROOT / 'runtime/latest/portfolio_latest.json',
        ROOT / 'runtime/latest/rebalance_latest.json',
        ROOT / 'runtime/latest/alerts_latest.json',
        ROOT / 'runtime/quality/portfolio_quality_report.json',
        ROOT / 'runtime/quality/risk_control_report.json',
        ROOT / 'runtime/quality/alert_report.json',
        ROOT / 'runtime/learning/portfolio_decision_history.json',
        ROOT / 'runtime/latest/operating_status_latest.json',
        ROOT / 'runtime/latest/health_status_latest.json',
        ROOT / 'runtime/latest/scheduler_status_latest.json',
        ROOT / 'runtime/quality/operating_status_report.json',
        ROOT / 'runtime/quality/health_report.json',
        ROOT / 'runtime/quality/failure_report.json',
        ROOT / 'runtime/quality/freshness_report.json',
        ROOT / 'runtime/learning/operating_run_history.json',
        ROOT / 'runtime/latest/run_manifest.json',
    ]
    for p in required:
        assert p.exists()

    manifest = json.loads((ROOT / 'runtime/latest/run_manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest)
    assert 'historical_snapshot_schema' in manifest['validations']
    assert 'phase4_decision_quality_schema' in manifest['validations']
    assert 'phase5_alert_schema' in manifest['validations']
    assert 'phase6_operating_status_schema' in manifest['validations']


def test_phase4_outputs_validate_from_sample_outcomes():
    _, quarterly, evidence, _ = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_5',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    outcomes = track_candidate_outcomes(
        candidates=[CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x')],
        snapshot=snapshot,
        observed_outcomes_by_symbol={'NBK': 0.03},
        explanations_by_symbol={'NBK': {'missing_data_penalties': 0.01}},
    )
    metadata, calibrated = calibrate_signals(snapshot.snapshot_id, outcomes)
    validate_calibration_metadata(metadata)
    validate_calibrated_signals(calibrated)
    benchmark = build_benchmark_result(snapshot.snapshot_id, outcomes)
    validate_benchmark_result(benchmark)
    usefulness = build_signal_usefulness_report(snapshot.snapshot_id, calibrated)
    validate_signal_usefulness_report(usefulness)
    decision_quality = build_decision_quality_report(snapshot.snapshot_id, benchmark, usefulness, metadata)
    validate_decision_quality_report(decision_quality)
    assert 0 <= decision_quality.decision_quality_score <= 1


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


def test_phase6_scheduler_health_and_failure_schema():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    run_record, scheduler, health, snapshot, failures, freshness_checks = build_phase6_status(
        root=ROOT,
        mode='sample',
        phase='all',
        internet_status='ok',
        validations=['phase5_alert_schema'],
        warnings=[],
        manifest_run_id='sample_phase6_manifest',
        manifest_created_at='2026-04-11T00:00:00+00:00',
    )
    validate_operating_run_record(run_record)
    validate_scheduler_status(scheduler)
    validate_freshness_checks(freshness_checks)
    validate_failure_records(failures)
    validate_health_status_report(health)
    validate_operating_status_snapshot(snapshot)
    assert scheduler.deterministic_sample_mode is True


def test_phase6_rejects_contradictory_health_state():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    health_data = json.loads((ROOT / 'runtime/latest/health_status_latest.json').read_text(encoding='utf-8'))
    health_data['healthy'] = True
    health_data['failures'] = [{
        'failure_class': 'missing_required_artifact',
        'severity': 'critical',
        'artifact': 'runtime/latest/portfolio_latest.json',
        'message': 'broken',
        'operator_action': 'fix',
    }]

    report = HealthStatusReport(
        overall_status=str(health_data['overall_status']),
        healthy=bool(health_data['healthy']),
        degraded=bool(health_data['degraded']),
        failed=bool(health_data['failed']),
        degraded_mode=bool(health_data['degraded_mode']),
        input_freshness_status=str(health_data['input_freshness_status']),
        artifact_presence_status=str(health_data['artifact_presence_status']),
        validation_status=str(health_data['validation_status']),
        phase_completion_status=str(health_data['phase_completion_status']),
        internet_status=str(health_data['internet_status']),
        portfolio_output_status=str(health_data['portfolio_output_status']),
        alert_summary=dict(health_data['alert_summary']),
        checks=[FreshnessCheck(**c) for c in health_data['checks']],
        failures=[FailureRecord(**f) for f in health_data['failures']],
        phase_completion=[PhaseCompletionRecord(**p) for p in health_data['phase_completion']],
    )
    with pytest.raises(ValueError):
        validate_health_status_report(report)


def test_phase5_portfolio_and_risk_controls_non_tradable_rejection():
    _, quarterly, evidence, _ = _sample_pipeline_inputs()
    snapshot = build_historical_snapshot(
        snapshot_id='snap_6',
        as_of_date=date.fromisoformat('2026-04-10'),
        quarterly_records=quarterly,
        evidence_records=evidence,
    )
    outcomes = track_candidate_outcomes(
        candidates=[CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x')],
        snapshot=snapshot,
        observed_outcomes_by_symbol={'NBK': 0.03},
        explanations_by_symbol={'NBK': {'missing_data_penalties': 0.01}},
    )
    _, calibrated = calibrate_signals(snapshot.snapshot_id, outcomes)
    proposal = construct_portfolio_proposal(
        candidates=[
            CandidateRecord(symbol='NBK', base_signal=0.4, trust_score=0.9, final_score=0.36, reason='x'),
            CandidateRecord(symbol='NONTRADE', base_signal=0.4, trust_score=0.9, final_score=0.35, reason='x'),
        ],
        calibrated_signals=calibrated + [CalibratedSignalRecord(symbol='NONTRADE', snapshot_id='snap_6', raw_signal=0.35, calibrated_signal=0.35, observed_return=None, evaluable=True, outcome_status='candidate_outcome_unavailable')],
        decision_quality_score=0.6,
        liquidity_by_symbol={'NBK': 0.8, 'NONTRADE': 0.8},
        tradable_symbols={'NBK'},
        min_inclusion_quality=0.1,
        max_holdings=3,
    )
    validate_portfolio_proposal(proposal)
    assert all(p.symbol != 'NONTRADE' for p in proposal.positions)

    risk = apply_risk_controls(
        proposal=proposal,
        prior_snapshot=None,
        max_single_position_weight=0.6,
        max_total_active_positions=3,
        min_liquidity_signal=0.5,
        min_decision_quality_signal=0.2,
        turnover_cap=0.8,
        cash_buffer=0.01,
    )
    validate_risk_control_result(risk)
    assert 0 <= sum(p.target_weight for p in risk.adjusted_positions) <= 1


def test_phase5_rebalance_join_fail_closed_and_alert_structure():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    portfolio = json.loads((ROOT / 'runtime/latest/portfolio_latest.json').read_text(encoding='utf-8'))
    bad_prior = PortfolioSnapshot(
        snapshot_id='prior',
        as_of_utc='2026-04-10T00:00:00+00:00',
        positions=[{'symbol': portfolio['positions'][0]['symbol'], 'canonical_entity_id': 'KW:DIFF', 'weight': portfolio['positions'][0]['weight']}],
        residual_cash_weight=0.0,
    )
    target_snapshot = PortfolioSnapshot(
        snapshot_id=str(portfolio['snapshot_id']),
        as_of_utc=str(portfolio['as_of_utc']),
        positions=list(portfolio['positions']),
        residual_cash_weight=float(portfolio['residual_cash_weight']),
    )
    with pytest.raises(ValueError):
        plan_rebalance(prior_snapshot=bad_prior, target_snapshot=target_snapshot)

    actions = [RebalanceAction(symbol='NBK', canonical_entity_id='KW:NBK', action='hold', prior_weight=0.2, target_weight=0.2, delta_weight=0.0, reason='x')]
    validate_rebalance_actions(actions)
    mock_proposal = PortfolioProposal(
        proposal_id='p1',
        generated_at_utc='2026-04-10T00:00:00+00:00',
        positions=[],
        excluded_candidates=[{'reason': 'missing_calibrated_signal'}],
        max_holdings=3,
        min_inclusion_quality=0.1,
        total_target_weight=0.0,
        quality_report=PortfolioQualityReport(
            portfolio_quality_score=0.3,
            quality_bucket='weak',
            included_count=0,
            excluded_count=1,
            average_decision_quality=0.4,
            limitations=['sparse'],
        ),
    )
    mock_decision = DecisionQualityReport(
        snapshot_id='snap',
        decision_quality_score=0.4,
        confidence_band={'low': 0.1, 'high': 0.8},
        benchmark_comparison={},
        signal_usefulness={},
        summary='low quality',
        limitations=['sparse'],
    )
    mock_risk = RiskControlResult(
        proposal_id='p1',
        controls=[RiskControlCheck(control_name='turnover_cap', status='adjusted', binding=True, details={})],
        adjusted_positions=[],
        residual_cash_weight=1.0,
        turnover=0.8,
        status='adjusted',
        risk_adjusted_snapshot=target_snapshot,
    )
    alerts = build_alerts(
        decision_quality=mock_decision,
        proposal=mock_proposal,
        risk=mock_risk,
        rebalance_actions=actions,
        benchmark_excess_return=-0.01,
    )
    validate_alert_records(alerts)
    assert {a.severity for a in alerts}.issubset({'info', 'warning', 'critical'})
