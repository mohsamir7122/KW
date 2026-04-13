#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.candidate_assembly import assemble_candidates
from kw_mi_os.contracts import RunManifest, sha256_of_text
from kw_mi_os.evaluation import generate_evaluation_report, outcome_records_to_json, track_candidate_outcomes
from kw_mi_os.evidence_normalization import normalize_evidence
from kw_mi_os.governance import governance_outputs
from kw_mi_os.historical_snapshot import build_historical_snapshot
from kw_mi_os.ingestion import default_source_catalog, fetch_json
from kw_mi_os.learning import build_learning_records, learning_records_to_json
from kw_mi_os.market_data import (
    build_market_data_snapshot,
    evaluate_market_data_quality,
    fetch_market_rows_from_source,
    market_source_catalog,
    normalize_and_map_market_rows,
    write_market_data_artifacts,
)
from kw_mi_os.models import (
    AlertRecord,
    BenchmarkResult,
    DecisionQualityReport,
    ExclusionRecord,
    FailureRecord,
    FreshnessCheck,
    HealthStatusReport,
    OperatingStatusSnapshot,
    PhaseCompletionRecord,
    PortfolioSnapshot,
    RebalanceAction,
    SchedulerStatus,
    SignalInput,
    SourceClass,
    SourceEvidenceRecord,
    MarketDataRow,
    MarketSourceClass,
    MarketSourceStatus,
)
from kw_mi_os.phase4 import (
    build_benchmark_result,
    build_decision_quality_report,
    build_signal_usefulness_report,
    calibrated_records_to_json,
    calibrate_signals,
)
from kw_mi_os.phase5 import apply_risk_controls, alerts_to_json, build_alerts, construct_portfolio_proposal, plan_rebalance
from kw_mi_os.phase6 import build_health_status_report, to_json
from kw_mi_os.phase7 import (
    build_consolidated_latest_report,
    build_dashboard_snapshot,
    build_daily_review_summary,
    build_reporting_metadata,
    build_review_checklist,
)
from kw_mi_os.phase8 import (
    append_rollout_history,
    build_daily_rollout_report,
    build_operator_verdict,
    build_rollout_metadata,
    build_signoff_recommendation,
)
from kw_mi_os.phase9 import build_daily_export_bundle, write_daily_exports
from kw_mi_os.phase_contracts import PHASE_CONTRACTS
from kw_mi_os.runtime_semantics import RUNTIME_SEMANTICS
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.source_growth import build_source_growth_record, source_growth_to_json
from kw_mi_os.universe import load_tradable_universe
from kw_mi_os.validation import (
    validate_alert_records,
    validate_benchmark_result,
    validate_calibrated_signals,
    validate_calibration_metadata,
    validate_candidate_records,
    validate_candidate_outcomes,
    validate_decision_quality_report,
    validate_evaluation_report,
    validate_historical_snapshot,
    validate_learning_records,
    validate_manifest,
    validate_portfolio_proposal,
    validate_portfolio_snapshot_compatibility,
    validate_quarterly,
    validate_rebalance_actions,
    validate_risk_control_result,
    validate_source_growth_record,
    validate_signal_usefulness_report,
    validate_operating_run_record,
    validate_scheduler_status,
    validate_freshness_checks,
    validate_failure_records,
    validate_phase_completion,
    validate_health_status_report,
    validate_operating_status_snapshot,
    validate_consolidated_latest_report,
    validate_daily_review_summary,
    validate_dashboard_snapshot,
    validate_phase7_required_inputs,
    validate_reporting_metadata,
    validate_review_checklist,
    validate_daily_rollout_report,
    validate_daily_export_bundle,
    validate_export_metadata,
    validate_csv_export,
    validate_markdown_summary,
    validate_operator_verdict,
    validate_phase8_required_inputs,
    validate_rollout_history,
    validate_rollout_metadata,
    validate_signoff_recommendation,
    validate_market_data_snapshot,
    validate_market_data_rows,
    validate_market_quality_report,
    validate_market_source_statuses,
)


def _deterministic_observed_outcomes(mode: str) -> dict[str, float]:
    if mode == 'sample':
        return {'NBK': 0.067, 'ZAIN': -0.018}
    return {'NBK': 0.021}


def _load_prior_snapshot(path: Path) -> PortfolioSnapshot | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    return PortfolioSnapshot(
        snapshot_id=str(data['snapshot_id']),
        as_of_utc=str(data['as_of_utc']),
        positions=list(data['positions']),
        residual_cash_weight=float(data.get('residual_cash_weight', 0.0)),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['sample', 'live'], default='sample')
    parser.add_argument('--phase', choices=['all', 'ingest', 'score', 'phase3', 'phase4', 'phase5', 'phase6', 'phase7', 'phase8', 'phase9', 'phase10', 'market_data'], default='all')
    parser.add_argument('--sample-mode', action='store_true')
    args = parser.parse_args()

    mode = 'sample' if args.sample_mode else args.mode
    selected_phase = 'phase10' if args.phase == 'market_data' else args.phase
    contract = PHASE_CONTRACTS[selected_phase]

    universe_file = ROOT / 'config/kuwait_equities_master.csv'
    quarterly_file = ROOT / 'data/quarterly_history.csv'

    tradable = load_tradable_universe(universe_file)
    quarterly_records = validate_quarterly(quarterly_file)

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
        run_id='phase3_sample_run',
    )
    exclusions += [
        ExclusionRecord(symbol=str(q['symbol']), blocked_by='entity_resolution', reason=str(q['blocked_by']))
        for q in quarantined
    ]

    (ROOT / 'runtime' / 'candidates').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'quality').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'latest').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'learning').mkdir(parents=True, exist_ok=True)
    (ROOT / 'runtime' / 'source_growth').mkdir(parents=True, exist_ok=True)

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

    files_written = [
        str(candidates_path),
        str(exclusions_path),
        str(explanations_path),
        str(quality_path),
        str(latest_snapshot),
    ]

    validations = [
        'universe_schema',
        'quarterly_schema',
        'signal_bounds',
        'evidence_normalization',
    ]
    warnings: list[str] = [] if mode == 'sample' else ['live_mode_selected_manual_review_required', 'phase3_live_uses_limited_outcome_feed']

    phase3_outcomes = []
    phase3_snapshot_id = 'kw_phase3_sample_2026q1'
    benchmark = None
    decision_quality = None
    calibrated_signals = []
    if selected_phase in {'all', 'phase3', 'phase4', 'phase5', 'phase6', 'phase7', 'phase8'}:
        snapshot = build_historical_snapshot(
            snapshot_id=phase3_snapshot_id,
            as_of_date=date.fromisoformat('2026-04-10'),
            quarterly_records=quarterly_records,
            evidence_records=evidence,
        )
        validate_historical_snapshot(snapshot)

        explanations_by_symbol = {str(row.get('symbol', '')): row for row in explanations}
        outcomes = track_candidate_outcomes(
            candidates=candidates,
            snapshot=snapshot,
            observed_outcomes_by_symbol=_deterministic_observed_outcomes(mode),
            explanations_by_symbol=explanations_by_symbol,
        )
        phase3_outcomes = validate_candidate_outcomes(outcomes)

        evaluation_report = generate_evaluation_report(
            snapshot=snapshot,
            outcomes=outcomes,
            explanations_by_symbol=explanations_by_symbol,
        )
        validate_evaluation_report(evaluation_report)

        learning_records = build_learning_records(
            snapshot_id=snapshot.snapshot_id,
            outcomes=outcomes,
            explanations_by_symbol=explanations_by_symbol,
        )
        validate_learning_records(learning_records)

        source_growth = build_source_growth_record(
            snapshot=snapshot,
            evidence=evidence,
            quarantined=quarantined,
            candidate_symbols=[c.symbol for c in candidates],
        )
        validate_source_growth_record(source_growth)

        evaluation_snapshot_path = ROOT / 'runtime' / 'learning' / 'evaluation_snapshot.json'
        candidate_outcomes_path = ROOT / 'runtime' / 'learning' / 'candidate_outcomes.json'
        learning_records_path = ROOT / 'runtime' / 'learning' / 'learning_records.json'
        source_growth_path = ROOT / 'runtime' / 'source_growth' / 'source_growth_report.json'
        evaluation_quality_path = ROOT / 'runtime' / 'quality' / 'evaluation_quality_report.json'
        evaluation_latest_path = ROOT / 'runtime' / 'latest' / 'evaluation_latest.json'

        evaluation_snapshot_path.write_text(json.dumps(asdict(snapshot), indent=2, default=str), encoding='utf-8')
        candidate_outcomes_path.write_text(json.dumps(outcome_records_to_json(outcomes), indent=2), encoding='utf-8')
        learning_records_path.write_text(json.dumps(learning_records_to_json(learning_records), indent=2), encoding='utf-8')
        source_growth_path.write_text(json.dumps(source_growth_to_json(source_growth), indent=2, default=str), encoding='utf-8')
        evaluation_quality_path.write_text(json.dumps(asdict(evaluation_report), indent=2), encoding='utf-8')
        evaluation_latest_path.write_text(json.dumps(asdict(evaluation_report), indent=2), encoding='utf-8')

        files_written.extend([
            str(evaluation_snapshot_path),
            str(candidate_outcomes_path),
            str(learning_records_path),
            str(source_growth_path),
            str(evaluation_quality_path),
            str(evaluation_latest_path),
        ])
        validations.extend([
            'historical_snapshot_schema',
            'candidate_outcome_schema',
            'evaluation_report_schema',
            'learning_schema',
            'source_growth_schema',
        ])

    if selected_phase in {'all', 'phase4', 'phase5', 'phase6', 'phase7', 'phase8'}:
        calibration_metadata, calibrated_signals = calibrate_signals(phase3_snapshot_id, phase3_outcomes)
        validate_calibration_metadata(calibration_metadata)
        validate_calibrated_signals(calibrated_signals)

        benchmark = build_benchmark_result(phase3_snapshot_id, phase3_outcomes)
        validate_benchmark_result(benchmark)

        usefulness = build_signal_usefulness_report(phase3_snapshot_id, calibrated_signals)
        validate_signal_usefulness_report(usefulness)

        decision_quality = build_decision_quality_report(phase3_snapshot_id, benchmark, usefulness, calibration_metadata)
        validate_decision_quality_report(decision_quality)

        calibrated_signals_path = ROOT / 'runtime' / 'learning' / 'calibrated_signals.json'
        signal_usefulness_path = ROOT / 'runtime' / 'learning' / 'signal_usefulness_report.json'
        benchmark_path = ROOT / 'runtime' / 'quality' / 'benchmark_report.json'
        decision_quality_path = ROOT / 'runtime' / 'quality' / 'decision_quality_report.json'
        benchmark_latest_path = ROOT / 'runtime' / 'latest' / 'benchmark_latest.json'
        decision_quality_latest_path = ROOT / 'runtime' / 'latest' / 'decision_quality_latest.json'

        calibrated_signals_path.write_text(
            json.dumps(calibrated_records_to_json(calibration_metadata, calibrated_signals), indent=2),
            encoding='utf-8',
        )
        signal_usefulness_path.write_text(json.dumps(asdict(usefulness), indent=2), encoding='utf-8')
        benchmark_path.write_text(json.dumps(asdict(benchmark), indent=2), encoding='utf-8')
        decision_quality_path.write_text(json.dumps(asdict(decision_quality), indent=2), encoding='utf-8')
        benchmark_latest_path.write_text(benchmark_path.read_text(encoding='utf-8'), encoding='utf-8')
        decision_quality_latest_path.write_text(decision_quality_path.read_text(encoding='utf-8'), encoding='utf-8')

        files_written.extend([
            str(calibrated_signals_path),
            str(signal_usefulness_path),
            str(benchmark_path),
            str(decision_quality_path),
            str(benchmark_latest_path),
            str(decision_quality_latest_path),
        ])
        validations.extend([
            'phase4_calibration_schema',
            'phase4_benchmark_schema',
            'phase4_signal_usefulness_schema',
            'phase4_decision_quality_schema',
        ])

    if selected_phase in {'all', 'phase5', 'phase6', 'phase7', 'phase8'}:
        if benchmark is None or decision_quality is None:
            raise ValueError('phase5 requires phase4 outputs')

        prior_portfolio_path = ROOT / 'runtime' / 'latest' / 'portfolio_latest.json'
        prior_snapshot = _load_prior_snapshot(prior_portfolio_path)

        liquidity_by_symbol = {symbol: signal.liquidity_signal for symbol, signal in signals.items()}
        proposal = construct_portfolio_proposal(
            candidates=candidates,
            calibrated_signals=calibrated_signals,
            decision_quality_score=decision_quality.decision_quality_score,
            liquidity_by_symbol=liquidity_by_symbol,
            tradable_symbols={u.symbol for u in tradable},
            min_inclusion_quality=0.1,
            max_holdings=3,
            target_invested_weight=1.0,
        )
        validate_portfolio_proposal(proposal)

        risk_result = apply_risk_controls(
            proposal=proposal,
            prior_snapshot=prior_snapshot,
            max_single_position_weight=0.55,
            max_total_active_positions=3,
            min_liquidity_signal=0.3,
            min_decision_quality_signal=0.15,
            turnover_cap=0.8,
            cash_buffer=0.02,
        )
        validate_risk_control_result(risk_result)
        validate_portfolio_snapshot_compatibility(prior_snapshot, risk_result.risk_adjusted_snapshot)

        rebalance_actions = plan_rebalance(prior_snapshot, risk_result.risk_adjusted_snapshot)
        validate_rebalance_actions(rebalance_actions)

        alerts = build_alerts(decision_quality, proposal, risk_result, rebalance_actions, benchmark.excess_return)
        validate_alert_records(alerts)

        portfolio_latest_path = ROOT / 'runtime' / 'latest' / 'portfolio_latest.json'
        rebalance_latest_path = ROOT / 'runtime' / 'latest' / 'rebalance_latest.json'
        alerts_latest_path = ROOT / 'runtime' / 'latest' / 'alerts_latest.json'
        portfolio_quality_path = ROOT / 'runtime' / 'quality' / 'portfolio_quality_report.json'
        risk_quality_path = ROOT / 'runtime' / 'quality' / 'risk_control_report.json'
        alert_quality_path = ROOT / 'runtime' / 'quality' / 'alert_report.json'
        decision_history_path = ROOT / 'runtime' / 'learning' / 'portfolio_decision_history.json'

        portfolio_latest_path.write_text(json.dumps(asdict(risk_result.risk_adjusted_snapshot), indent=2), encoding='utf-8')
        rebalance_latest_path.write_text(json.dumps([asdict(a) for a in rebalance_actions], indent=2), encoding='utf-8')
        alerts_latest_path.write_text(json.dumps(alerts_to_json(alerts), indent=2), encoding='utf-8')
        portfolio_quality_path.write_text(json.dumps(asdict(proposal.quality_report), indent=2), encoding='utf-8')
        risk_quality_path.write_text(json.dumps(asdict(risk_result), indent=2), encoding='utf-8')
        alert_quality_path.write_text(json.dumps({'total_alerts': len(alerts), 'alerts': alerts_to_json(alerts)}, indent=2), encoding='utf-8')

        history: list[dict[str, object]] = []
        if decision_history_path.exists():
            history = list(json.loads(decision_history_path.read_text(encoding='utf-8')))
        history.append(
            {
                'proposal': asdict(proposal),
                'risk_result': asdict(risk_result),
                'rebalance_actions': [asdict(a) for a in rebalance_actions],
                'alerts': alerts_to_json(alerts),
            }
        )
        decision_history_path.write_text(json.dumps(history[-20:], indent=2), encoding='utf-8')

        files_written.extend([
            str(portfolio_latest_path),
            str(rebalance_latest_path),
            str(alerts_latest_path),
            str(portfolio_quality_path),
            str(risk_quality_path),
            str(alert_quality_path),
            str(decision_history_path),
        ])
        validations.extend([
            'phase5_portfolio_proposal_schema',
            'phase5_risk_control_schema',
            'phase5_rebalance_schema',
            'phase5_alert_schema',
            'phase5_snapshot_compatibility',
        ])

    if selected_phase in {'all', 'phase6', 'phase7', 'phase8'}:
        current_failures = []
        if internet_status != 'ok':
            current_failures.append('network_unavailable')

        run_record, scheduler_status, health_report, operating_status, failure_records = build_health_status_report(
            run_id='phase6_sample_run',
            mode=mode,
            run_outcome='success' if not current_failures else 'degraded',
            failures=current_failures,
        )
        validate_operating_run_record(run_record)
        validate_scheduler_status(scheduler_status)
        validate_freshness_checks(health_report.freshness_checks)
        validate_failure_records(failure_records)
        validate_phase_completion(health_report.phase_completion)
        validate_health_status_report(health_report)
        validate_operating_status_snapshot(operating_status)

        operating_latest_path = ROOT / 'runtime' / 'latest' / 'operating_status_latest.json'
        health_latest_path = ROOT / 'runtime' / 'latest' / 'health_status_latest.json'
        scheduler_latest_path = ROOT / 'runtime' / 'latest' / 'scheduler_status_latest.json'
        operating_report_path = ROOT / 'runtime' / 'quality' / 'operating_status_report.json'
        health_report_path = ROOT / 'runtime' / 'quality' / 'health_report.json'
        failure_report_path = ROOT / 'runtime' / 'quality' / 'failure_report.json'
        freshness_report_path = ROOT / 'runtime' / 'quality' / 'freshness_report.json'
        run_history_path = ROOT / 'runtime' / 'learning' / 'operating_run_history.json'

        operating_latest_path.write_text(json.dumps(to_json(operating_status), indent=2), encoding='utf-8')
        health_latest_path.write_text(json.dumps(to_json(health_report), indent=2), encoding='utf-8')
        scheduler_latest_path.write_text(json.dumps(to_json(scheduler_status), indent=2), encoding='utf-8')
        operating_report_path.write_text(json.dumps({'run_record': to_json(run_record), 'operating_status': to_json(operating_status)}, indent=2), encoding='utf-8')
        health_report_path.write_text(json.dumps(to_json(health_report), indent=2), encoding='utf-8')
        failure_report_path.write_text(json.dumps([to_json(f) for f in failure_records], indent=2), encoding='utf-8')
        freshness_report_path.write_text(json.dumps([to_json(f) for f in health_report.freshness_checks], indent=2), encoding='utf-8')

        history: list[dict[str, object]] = []
        if run_history_path.exists():
            history = list(json.loads(run_history_path.read_text(encoding='utf-8')))
        history.append(to_json(run_record))
        run_history_path.write_text(json.dumps(history[-50:], indent=2), encoding='utf-8')

        files_written.extend([
            str(operating_latest_path),
            str(health_latest_path),
            str(scheduler_latest_path),
            str(operating_report_path),
            str(health_report_path),
            str(failure_report_path),
            str(freshness_report_path),
            str(run_history_path),
        ])
        validations.extend([
            'phase6_operating_run_record_schema',
            'phase6_scheduler_status_schema',
            'phase6_freshness_schema',
            'phase6_failure_classification_schema',
            'phase6_health_report_schema',
            'phase6_operating_status_schema',
        ])

    if selected_phase in {'all', 'phase7', 'phase8'}:
        phase7_inputs = [
            ROOT / 'runtime' / 'latest' / 'operating_status_latest.json',
            ROOT / 'runtime' / 'latest' / 'health_status_latest.json',
            ROOT / 'runtime' / 'latest' / 'candidates_latest.json',
            ROOT / 'runtime' / 'latest' / 'decision_quality_latest.json',
            ROOT / 'runtime' / 'latest' / 'benchmark_latest.json',
            ROOT / 'runtime' / 'latest' / 'portfolio_latest.json',
            ROOT / 'runtime' / 'latest' / 'rebalance_latest.json',
            ROOT / 'runtime' / 'latest' / 'alerts_latest.json',
        ]
        try:
            validate_phase7_required_inputs(phase7_inputs)
        except ValueError as exc:
            if mode == 'live':
                warnings.append('phase7_live_inputs_missing_reporting_fallback_applied')
                print(f'phase7: fallback reporting mode due to missing inputs: {exc}')
            else:
                raise

        operating = json.loads((ROOT / 'runtime' / 'latest' / 'operating_status_latest.json').read_text(encoding='utf-8'))
        health = json.loads((ROOT / 'runtime' / 'latest' / 'health_status_latest.json').read_text(encoding='utf-8'))
        latest_candidates = validate_candidate_records(json.loads((ROOT / 'runtime' / 'latest' / 'candidates_latest.json').read_text(encoding='utf-8')))
        latest_decision_quality = validate_decision_quality_report(
            DecisionQualityReport(**json.loads((ROOT / 'runtime' / 'latest' / 'decision_quality_latest.json').read_text(encoding='utf-8')))
        )
        latest_benchmark = validate_benchmark_result(
            BenchmarkResult(**json.loads((ROOT / 'runtime' / 'latest' / 'benchmark_latest.json').read_text(encoding='utf-8')))
        )
        latest_portfolio = PortfolioSnapshot(**json.loads((ROOT / 'runtime' / 'latest' / 'portfolio_latest.json').read_text(encoding='utf-8')))
        latest_rebalance = [RebalanceAction(**row) for row in json.loads((ROOT / 'runtime' / 'latest' / 'rebalance_latest.json').read_text(encoding='utf-8'))]
        latest_alerts = validate_alert_records([AlertRecord(**row) for row in json.loads((ROOT / 'runtime' / 'latest' / 'alerts_latest.json').read_text(encoding='utf-8'))])

        dashboard = build_dashboard_snapshot(
            run_id=str(operating['run_id']),
            mode=mode,
            operating_status=OperatingStatusSnapshot(**operating),
            health_report=HealthStatusReport(
                run_id=str(health['run_id']),
                overall_status=str(health['overall_status']),
                scheduler=SchedulerStatus(**health['scheduler']),
                freshness_checks=[FreshnessCheck(**row) for row in health['freshness_checks']],
                failures=[FailureRecord(**row) for row in health['failures']],
                phase_completion=[PhaseCompletionRecord(**row) for row in health['phase_completion']],
                summary=str(health['summary']),
            ),
            candidates=latest_candidates,
            decision_quality=latest_decision_quality,
            benchmark=latest_benchmark,
            portfolio=latest_portfolio,
            rebalance_actions=latest_rebalance,
            alerts=latest_alerts,
        )
        validate_dashboard_snapshot(dashboard)

        summary = build_daily_review_summary(
            dashboard=dashboard,
            health_report=HealthStatusReport(
                run_id=str(health['run_id']),
                overall_status=str(health['overall_status']),
                scheduler=SchedulerStatus(**health['scheduler']),
                freshness_checks=[FreshnessCheck(**row) for row in health['freshness_checks']],
                failures=[FailureRecord(**row) for row in health['failures']],
                phase_completion=[PhaseCompletionRecord(**row) for row in health['phase_completion']],
                summary=str(health['summary']),
            ),
            alerts=latest_alerts,
            rebalance_actions=latest_rebalance,
        )
        validate_daily_review_summary(summary)

        checklist = build_review_checklist(summary, dashboard)
        validate_review_checklist(checklist)

        phase7_output_paths = [
            'runtime/latest/dashboard_snapshot.json',
            'runtime/latest/daily_review_latest.json',
            'runtime/latest/consolidated_latest_report.json',
            'runtime/quality/operator_summary_report.json',
            'runtime/quality/review_checklist_report.json',
            'runtime/quality/reporting_metadata.json',
        ]
        metadata = build_reporting_metadata(
            mode=mode,
            upstream_inputs=[str(path.relative_to(ROOT)) for path in phase7_inputs],
            generated_outputs=phase7_output_paths,
            deterministic=(mode == 'sample'),
        )
        validate_reporting_metadata(metadata)

        consolidated = build_consolidated_latest_report(
            dashboard=dashboard,
            summary=summary,
            checklist=checklist,
            metadata=metadata,
        )
        validate_consolidated_latest_report(consolidated)

        dashboard_latest_path = ROOT / 'runtime' / 'latest' / 'dashboard_snapshot.json'
        daily_latest_path = ROOT / 'runtime' / 'latest' / 'daily_review_latest.json'
        consolidated_latest_path = ROOT / 'runtime' / 'latest' / 'consolidated_latest_report.json'
        operator_summary_path = ROOT / 'runtime' / 'quality' / 'operator_summary_report.json'
        checklist_quality_path = ROOT / 'runtime' / 'quality' / 'review_checklist_report.json'
        metadata_quality_path = ROOT / 'runtime' / 'quality' / 'reporting_metadata.json'

        dashboard_latest_path.write_text(json.dumps(asdict(dashboard), indent=2), encoding='utf-8')
        daily_latest_path.write_text(json.dumps(asdict(summary), indent=2), encoding='utf-8')
        consolidated_latest_path.write_text(json.dumps(asdict(consolidated), indent=2), encoding='utf-8')
        operator_summary_path.write_text(json.dumps(asdict(summary), indent=2), encoding='utf-8')
        checklist_quality_path.write_text(json.dumps(asdict(checklist), indent=2), encoding='utf-8')
        metadata_quality_path.write_text(json.dumps(asdict(metadata), indent=2), encoding='utf-8')

        files_written.extend([
            str(dashboard_latest_path),
            str(daily_latest_path),
            str(consolidated_latest_path),
            str(operator_summary_path),
            str(checklist_quality_path),
            str(metadata_quality_path),
        ])
        validations.extend([
            'phase7_required_inputs_present',
            'phase7_dashboard_snapshot_schema',
            'phase7_daily_review_summary_schema',
            'phase7_review_checklist_schema',
            'phase7_reporting_metadata_schema',
            'phase7_consolidated_report_schema',
        ])

    if selected_phase in {'all', 'phase8', 'phase9'}:
        phase8_inputs = [
            ROOT / 'runtime' / 'latest' / 'operating_status_latest.json',
            ROOT / 'runtime' / 'latest' / 'health_status_latest.json',
            ROOT / 'runtime' / 'latest' / 'daily_review_latest.json',
            ROOT / 'runtime' / 'latest' / 'decision_quality_latest.json',
            ROOT / 'runtime' / 'latest' / 'benchmark_latest.json',
            ROOT / 'runtime' / 'latest' / 'rebalance_latest.json',
            ROOT / 'runtime' / 'latest' / 'alerts_latest.json',
        ]
        validate_phase8_required_inputs(phase8_inputs)

        operating = json.loads((ROOT / 'runtime' / 'latest' / 'operating_status_latest.json').read_text(encoding='utf-8'))
        daily_review = json.loads((ROOT / 'runtime' / 'latest' / 'daily_review_latest.json').read_text(encoding='utf-8'))
        decision_quality = json.loads((ROOT / 'runtime' / 'latest' / 'decision_quality_latest.json').read_text(encoding='utf-8'))
        benchmark = json.loads((ROOT / 'runtime' / 'latest' / 'benchmark_latest.json').read_text(encoding='utf-8'))
        alerts_latest = json.loads((ROOT / 'runtime' / 'latest' / 'alerts_latest.json').read_text(encoding='utf-8'))
        rebalance_latest = json.loads((ROOT / 'runtime' / 'latest' / 'rebalance_latest.json').read_text(encoding='utf-8'))

        alert_summary = {
            'total_alerts': len(alerts_latest),
            'critical_alert_count': sum(1 for row in alerts_latest if row.get('severity') == 'critical'),
            'warning_alert_count': sum(1 for row in alerts_latest if row.get('severity') == 'warning'),
        }
        run_date = '2026-04-10' if mode == 'sample' else date.today().isoformat()
        health_state = str(operating.get('operating_status', 'failed'))
        run_completion_status = 'completed' if health_state != 'failed' else 'failed'

        top_issues = [
            str(row.get('alert_type'))
            for row in alerts_latest
            if isinstance(row, dict) and row.get('severity') in {'critical', 'warning'}
        ]
        if not top_issues:
            top_issues = [health_state]

        verdict = build_operator_verdict(
            run_id=str(operating.get('run_id')),
            health_state=health_state,
            decision_quality_score=float(decision_quality.get('decision_quality_score', 0.0)),
            benchmark_excess_return=float(benchmark.get('excess_return', 0.0)),
            alert_summary=alert_summary,
            degraded_reasons=[str(r) for r in operating.get('degraded_reasons', [])],
            daily_inspect_first=[str(v) for v in daily_review.get('inspect_first', [])],
        )
        validate_operator_verdict(verdict)
        signoff = build_signoff_recommendation(verdict=verdict)
        validate_signoff_recommendation(signoff)

        report = build_daily_rollout_report(
            run_id=verdict.run_id,
            run_date=run_date,
            run_mode=mode,
            run_completion_status=run_completion_status,
            health_state=health_state,
            alert_summary=alert_summary,
            top_issues=top_issues,
            portfolio_rebalance_present=len(rebalance_latest) > 0,
            decision_quality_present='decision_quality_score' in decision_quality,
            verdict=verdict,
        )
        validate_daily_rollout_report(report)

        history_path = ROOT / 'runtime' / 'learning' / 'rollout_30_day_history.json'
        existing_history: list[dict[str, object]] = []
        if history_path.exists():
            history_json = json.loads(history_path.read_text(encoding='utf-8'))
            existing_history = list(history_json.get('records', []))
        history = append_rollout_history(existing=existing_history, report=report, window_days=30)
        validate_rollout_history(history)

        phase8_output_paths = [
            'runtime/latest/daily_rollout_latest.json',
            'runtime/latest/operator_verdict_latest.json',
            'runtime/latest/signoff_recommendation_latest.json',
            'runtime/quality/daily_rollout_report.json',
            'runtime/quality/operator_verdict_report.json',
            'runtime/quality/rollout_metadata.json',
            'runtime/learning/rollout_30_day_history.json',
        ]
        metadata = build_rollout_metadata(
            mode=mode,
            upstream_inputs=[str(path.relative_to(ROOT)) for path in phase8_inputs],
            generated_outputs=phase8_output_paths,
            deterministic=(mode == 'sample'),
        )
        validate_rollout_metadata(metadata)

        daily_rollout_latest_path = ROOT / 'runtime' / 'latest' / 'daily_rollout_latest.json'
        verdict_latest_path = ROOT / 'runtime' / 'latest' / 'operator_verdict_latest.json'
        signoff_latest_path = ROOT / 'runtime' / 'latest' / 'signoff_recommendation_latest.json'
        rollout_report_path = ROOT / 'runtime' / 'quality' / 'daily_rollout_report.json'
        verdict_report_path = ROOT / 'runtime' / 'quality' / 'operator_verdict_report.json'
        rollout_metadata_path = ROOT / 'runtime' / 'quality' / 'rollout_metadata.json'

        daily_rollout_latest_path.write_text(json.dumps(asdict(report), indent=2), encoding='utf-8')
        verdict_latest_path.write_text(json.dumps(asdict(verdict), indent=2), encoding='utf-8')
        signoff_latest_path.write_text(json.dumps(asdict(signoff), indent=2), encoding='utf-8')
        rollout_report_path.write_text(json.dumps(asdict(report), indent=2), encoding='utf-8')
        verdict_report_path.write_text(json.dumps({'operator_verdict': asdict(verdict), 'signoff': asdict(signoff)}, indent=2), encoding='utf-8')
        rollout_metadata_path.write_text(json.dumps(asdict(metadata), indent=2), encoding='utf-8')
        history_path.write_text(json.dumps(asdict(history), indent=2), encoding='utf-8')

        files_written.extend([
            str(daily_rollout_latest_path),
            str(verdict_latest_path),
            str(signoff_latest_path),
            str(rollout_report_path),
            str(verdict_report_path),
            str(rollout_metadata_path),
            str(history_path),
        ])
        validations.extend([
            'phase8_required_inputs_present',
            'phase8_operator_verdict_schema',
            'phase8_signoff_consistency_schema',
            'phase8_daily_rollout_schema',
            'phase8_rollout_history_schema',
            'phase8_rollout_metadata_schema',
        ])

    if selected_phase in {'all', 'phase9'}:
        bundle, csv_specs, markdown = build_daily_export_bundle(root=ROOT, mode=mode)
        validate_daily_export_bundle(bundle)
        validate_export_metadata(bundle.export_metadata)
        validate_markdown_summary(markdown)
        exported = write_daily_exports(root=ROOT, bundle=bundle, markdown=markdown)
        for spec in csv_specs:
            validate_csv_export(ROOT / spec.output_path, spec.headers)

        files_written.extend([str(ROOT / rel) for rel in exported])
        validations.extend([
            'phase9_required_inputs_present',
            'phase9_daily_export_bundle_schema',
            'phase9_export_metadata_schema',
            'phase9_markdown_summary_sections',
            'phase9_csv_consistency',
            'phase9_contradiction_rejection',
        ])

    if selected_phase in {'all', 'phase10'}:
        now_utc = datetime.now(timezone.utc) if mode == 'live' else datetime.fromisoformat('2026-04-10T15:00:00+00:00')
        if mode == 'sample':
            collected_rows = [
                MarketDataRow('NBK', 'National Bank of Kuwait', '', 0.92, 0.01, 1.1, 1200000, 1104000.0, '2026-04-10', 'closed', 'sample_seed', MarketSourceClass.priority_1_official_market.value, 'sample://seed', '2026-04-10T15:00:00+00:00', 'sample:NBK'),
                MarketDataRow('ZAIN', 'Mobile Telecommunications Company', '', 0.53, -0.005, -0.9, 900000, 477000.0, '2026-04-10', 'closed', 'sample_seed', MarketSourceClass.priority_1_official_market.value, 'sample://seed', '2026-04-10T15:00:00+00:00', 'sample:ZAIN'),
            ]
            source_statuses = [
                MarketSourceStatus(
                    source_name='sample_seed',
                    source_class=MarketSourceClass.priority_1_official_market.value,
                    attempted=True,
                    success=True,
                    rows_fetched=2,
                    error=None,
                    fallback_used=False,
                    notes='deterministic_sample_mode',
                )
            ]
        else:
            sources = market_source_catalog()
            collected_rows = []
            source_statuses = []
            for source in sorted(sources, key=lambda row: row.fallback_priority):
                source_rows, source_status = fetch_market_rows_from_source(source, tradable, now_utc)
                source_statuses.append(source_status)
                if source_rows:
                    collected_rows.extend(source_rows)
                    if source.fallback_priority == 1:
                        break

        normalized_rows, unresolved_errors = normalize_and_map_market_rows(collected_rows, tradable)
        quality = evaluate_market_data_quality(
            rows=normalized_rows,
            source_statuses=source_statuses,
            unresolved_errors=unresolved_errors,
            now_utc=now_utc,
        )
        validate_market_source_statuses(source_statuses)
        validate_market_quality_report(quality)
        if quality.ready_for_downstream:
            validate_market_data_rows(normalized_rows)

        snapshot = build_market_data_snapshot(
            rows=normalized_rows,
            quality=quality,
            source_statuses=source_statuses,
            mode=mode,
            now_utc=now_utc,
        )
        validate_market_data_snapshot(snapshot)
        written = write_market_data_artifacts(ROOT, snapshot)
        files_written.extend(written)
        validations.extend([
            'phase10_market_source_status_schema',
            'phase10_market_quality_schema',
            'phase10_market_snapshot_schema',
        ])
        if not quality.ready_for_downstream:
            warnings.append('phase10_market_data_not_ready_for_downstream')
        if not quality.primary_source_ok:
            warnings.append('phase10_primary_source_unavailable_fallback_used')

    checksums = {
        'config/kuwait_equities_master.csv': sha256_of_text(universe_file.read_text(encoding='utf-8')),
        'data/quarterly_history.csv': sha256_of_text(quarterly_file.read_text(encoding='utf-8')),
    }

    if mode == 'live' and selected_phase in {'all', 'phase5'}:
        warnings.append('phase5_live_requires_external_portfolio_execution_inputs_fallback_only')

    manifest = RunManifest(
        mode=mode,
        phase=selected_phase,
        internet_fetch_status=internet_status,
        files_read=list(contract.reads),
        files_written=files_written,
        validations=validations + ['manifest_schema'],
        warnings=warnings,
        failures=[],
        input_checksums=checksums,
    )
    manifest_path = ROOT / 'runtime' / 'latest' / 'run_manifest.json'
    manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    validate_manifest(json.loads(manifest_path.read_text(encoding='utf-8')))

    semantics_path = ROOT / 'runtime' / 'quality' / 'runtime_semantics.json'
    semantics_path.write_text(json.dumps(RUNTIME_SEMANTICS, indent=2), encoding='utf-8')

    print(f'run_phase: mode={mode} phase={selected_phase} candidates={len(candidates)} exclusions={len(exclusions)} internet={internet_status}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
