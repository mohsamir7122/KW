from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .models import (
    AlertRecord,
    BenchmarkResult,
    CalibratedSignalRecord,
    CalibrationMetadata,
    CandidateRecord,
    CandidateOutcomeRecord,
    DecisionQualityReport,
    EvaluationReport,
    EntityType,
    PortfolioProposal,
    PortfolioSnapshot,
    RebalanceAction,
    RiskControlResult,
    FailureRecord,
    FreshnessCheck,
    HealthStatusReport,
    OperatingRunRecord,
    OperatingStatusSnapshot,
    PhaseCompletionRecord,
    HistoricalSnapshotRecord,
    LearningRecord,
    ListingStatus,
    QuarterlyRecord,
    RunManifestModel,
    SchedulerStatus,
    SignalUsefulnessReport,
    SourceGrowthRecord,
    UniverseRecord,
)

UNIVERSE_COLUMNS = [
    'symbol', 'arabic_name', 'english_name', 'sector', 'market', 'listing_status',
    'entity_type', 'tradable_flag', 'sec_code', 'isin', 'source_primary',
    'source_secondary', 'verified_at_utc'
]

QUARTERLY_COLUMNS = [
    'symbol', 'quarter_end', 'fiscal_period', 'filing_date', 'revenue', 'operating_profit',
    'net_profit', 'eps', 'total_assets', 'total_liabilities', 'total_equity',
    'cash_from_operations', 'capex', 'dividend_flag', 'buyback_flag', 'material_event_flag',
    'source_primary', 'source_secondary', 'verified_at_utc'
]


def _parse_bool(v: str) -> bool:
    lv = v.strip().lower()
    if lv in {'true', '1', 'yes'}:
        return True
    if lv in {'false', '0', 'no'}:
        return False
    raise ValueError(f'invalid bool: {v}')


def _parse_datetime(v: str) -> datetime:
    return datetime.fromisoformat(v.replace('Z', '+00:00'))


def _load_rows(path: str | Path, required_columns: list[str]) -> list[dict[str, str]]:
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != required_columns:
            raise ValueError(f'Invalid schema for {path}')
        return list(reader)


def validate_universe(path: str | Path) -> list[UniverseRecord]:
    rows = _load_rows(path, UNIVERSE_COLUMNS)
    records: list[UniverseRecord] = []
    symbols: set[str] = set()
    for i, r in enumerate(rows, start=2):
        try:
            rec = UniverseRecord(
                symbol=r['symbol'].strip(),
                arabic_name=r['arabic_name'].strip(),
                english_name=r['english_name'].strip(),
                sector=r['sector'].strip(),
                market=r['market'].strip(),
                listing_status=ListingStatus(r['listing_status'].strip().lower()),
                entity_type=EntityType(r['entity_type'].strip().lower()),
                tradable_flag=_parse_bool(r['tradable_flag']),
                sec_code=int(r['sec_code']),
                isin=r['isin'].strip(),
                source_primary=r['source_primary'].strip(),
                source_secondary=r['source_secondary'].strip(),
                verified_at_utc=_parse_datetime(r['verified_at_utc']),
            )
        except Exception as exc:
            raise ValueError(f'Universe validation error at line {i}: {exc}') from exc

        if rec.symbol in symbols:
            raise ValueError(f'Duplicate symbol found in universe file: {rec.symbol}')
        symbols.add(rec.symbol)
        if rec.entity_type == EntityType.kuwait_listed_equity and rec.tradable_flag and rec.listing_status != ListingStatus.listed:
            raise ValueError(f'Tradable listed inconsistency for {rec.symbol}')
        records.append(rec)
    return records


def validate_quarterly(path: str | Path) -> list[QuarterlyRecord]:
    rows = _load_rows(path, QUARTERLY_COLUMNS)
    records: list[QuarterlyRecord] = []
    for i, r in enumerate(rows, start=2):
        try:
            records.append(
                QuarterlyRecord(
                    symbol=r['symbol'].strip(),
                    quarter_end=date.fromisoformat(r['quarter_end']),
                    fiscal_period=r['fiscal_period'].strip(),
                    filing_date=date.fromisoformat(r['filing_date']),
                    revenue=float(r['revenue']),
                    operating_profit=float(r['operating_profit']),
                    net_profit=float(r['net_profit']),
                    eps=float(r['eps']),
                    total_assets=float(r['total_assets']),
                    total_liabilities=float(r['total_liabilities']),
                    total_equity=float(r['total_equity']),
                    cash_from_operations=float(r['cash_from_operations']),
                    capex=float(r['capex']),
                    dividend_flag=_parse_bool(r['dividend_flag']),
                    buyback_flag=_parse_bool(r['buyback_flag']),
                    material_event_flag=_parse_bool(r['material_event_flag']),
                    source_primary=r['source_primary'].strip(),
                    source_secondary=r['source_secondary'].strip(),
                    verified_at_utc=_parse_datetime(r['verified_at_utc']),
                )
            )
        except Exception as exc:
            raise ValueError(f'Quarterly validation error at line {i}: {exc}') from exc
    return records


def validate_manifest(data: dict) -> RunManifestModel:
    return RunManifestModel(
        run_id=str(data['run_id']),
        created_at_utc=_parse_datetime(str(data['created_at_utc'])),
        mode=str(data['mode']),
        phase=str(data['phase']),
        git_commit=str(data['git_commit']),
        internet_fetch_status=str(data['internet_fetch_status']),
        files_read=list(data['files_read']),
        files_written=list(data['files_written']),
        input_checksums=dict(data['input_checksums']),
        validations=list(data['validations']),
        warnings=list(data['warnings']),
        failures=list(data['failures']),
    )


def validate_candidate_records(records: list[dict]) -> list[CandidateRecord]:
    output: list[CandidateRecord] = []
    for r in records:
        output.append(
            CandidateRecord(
                symbol=str(r['symbol']),
                base_signal=float(r['base_signal']),
                trust_score=float(r['trust_score']),
                final_score=float(r['final_score']),
                reason=str(r['reason']),
            )
        )
    return output


def validate_historical_snapshot(snapshot: HistoricalSnapshotRecord) -> HistoricalSnapshotRecord:
    if not snapshot.snapshot_id.strip():
        raise ValueError('snapshot_id is required')
    if not snapshot.equity_state:
        raise ValueError('historical snapshot requires equity_state')
    if not snapshot.evidence_state:
        raise ValueError('historical snapshot requires evidence_state')
    if not snapshot.coverage_symbols:
        raise ValueError('historical snapshot requires coverage_symbols')
    return snapshot


def validate_candidate_outcomes(records: list[CandidateOutcomeRecord]) -> list[CandidateOutcomeRecord]:
    for r in records:
        if not r.canonical_entity_id.startswith('KW:'):
            raise ValueError(f'invalid canonical_entity_id for {r.symbol}')
        if not (r.published and r.evaluable):
            raise ValueError(f'candidate {r.symbol} must be published and evaluable in phase3')
    return records


def validate_evaluation_report(report: EvaluationReport) -> EvaluationReport:
    if report.evaluated_count < report.observed_count:
        raise ValueError('evaluated_count cannot be less than observed_count')
    if report.unavailable_count != report.evaluated_count - report.observed_count:
        raise ValueError('unavailable_count mismatch')
    return report


def validate_learning_records(records: list[LearningRecord]) -> list[LearningRecord]:
    for r in records:
        if 'realized_return' not in r.outcome:
            raise ValueError(f'missing realized_return for {r.symbol}')
    return records


def validate_source_growth_record(record: SourceGrowthRecord) -> SourceGrowthRecord:
    if not record.source_coverage_over_time:
        raise ValueError('source coverage cannot be empty')
    return record


def validate_calibration_metadata(metadata: CalibrationMetadata) -> CalibrationMetadata:
    if metadata.sample_size < metadata.effective_sample_size:
        raise ValueError('sample_size cannot be less than effective_sample_size')
    if not (0.0 <= metadata.calibration_factor <= 2.0):
        raise ValueError('calibration_factor out of bounds')
    return metadata


def validate_calibrated_signals(records: list[CalibratedSignalRecord]) -> list[CalibratedSignalRecord]:
    for r in records:
        if not (0.0 <= r.raw_signal <= 1.0):
            raise ValueError(f'raw_signal out of bounds for {r.symbol}')
        if not (0.0 <= r.calibrated_signal <= 1.0):
            raise ValueError(f'calibrated_signal out of bounds for {r.symbol}')
    return records


def validate_benchmark_result(result: BenchmarkResult) -> BenchmarkResult:
    if result.candidate_hit_rate is not None and not (0.0 <= result.candidate_hit_rate <= 1.0):
        raise ValueError('candidate_hit_rate out of bounds')
    return result


def validate_signal_usefulness_report(report: SignalUsefulnessReport) -> SignalUsefulnessReport:
    if not (0.0 <= report.usefulness_score <= 1.0):
        raise ValueError('signal usefulness score out of bounds')
    return report


def validate_decision_quality_report(report: DecisionQualityReport) -> DecisionQualityReport:
    if not (0.0 <= report.decision_quality_score <= 1.0):
        raise ValueError('decision quality score out of bounds')
    return report


def validate_portfolio_proposal(proposal: PortfolioProposal) -> PortfolioProposal:
    if not proposal.proposal_id:
        raise ValueError('portfolio proposal id is required')
    running = 0.0
    for p in proposal.positions:
        if not (0.0 <= p.target_weight <= 1.0):
            raise ValueError(f'target weight out of bounds for {p.symbol}')
        if not p.tradable:
            raise ValueError(f'non-tradable entity in portfolio proposal: {p.symbol}')
        running += p.target_weight
    if abs(round(running, 6) - proposal.total_target_weight) > 1e-6:
        raise ValueError('portfolio proposal total_target_weight mismatch')
    return proposal


def validate_risk_control_result(result: RiskControlResult) -> RiskControlResult:
    if not result.controls:
        raise ValueError('risk control result must include controls')
    for control in result.controls:
        if control.status not in {'pass', 'adjusted', 'fail', 'limitation'}:
            raise ValueError(f'invalid control status: {control.status}')
    for p in result.adjusted_positions:
        if not p.tradable:
            raise ValueError(f'non-tradable entity after risk controls: {p.symbol}')
    return result


def validate_portfolio_snapshot_compatibility(
    prior_snapshot: PortfolioSnapshot | None,
    latest_snapshot: PortfolioSnapshot,
) -> PortfolioSnapshot:
    if prior_snapshot is None:
        return latest_snapshot
    prior_symbols = {str(p['symbol']) for p in prior_snapshot.positions}
    latest_symbols = {str(p['symbol']) for p in latest_snapshot.positions}
    for symbol in prior_symbols & latest_symbols:
        prior_id = str(next(p['canonical_entity_id'] for p in prior_snapshot.positions if p['symbol'] == symbol))
        latest_id = str(next(p['canonical_entity_id'] for p in latest_snapshot.positions if p['symbol'] == symbol))
        if prior_id != latest_id:
            raise ValueError(f'invalid entity join in portfolio snapshots for {symbol}')
    return latest_snapshot


def validate_rebalance_actions(actions: list[RebalanceAction]) -> list[RebalanceAction]:
    valid_actions = {'add', 'increase', 'decrease', 'hold', 'remove'}
    for action in actions:
        if action.action not in valid_actions:
            raise ValueError(f'invalid rebalance action {action.action} for {action.symbol}')
        if round(action.target_weight - action.prior_weight, 6) != action.delta_weight:
            raise ValueError(f'rebalance delta mismatch for {action.symbol}')
    return actions


def validate_alert_records(alerts: list[AlertRecord]) -> list[AlertRecord]:
    valid_severity = {'info', 'warning', 'critical'}
    for alert in alerts:
        if alert.severity not in valid_severity:
            raise ValueError(f'invalid alert severity: {alert.severity}')
        if not alert.alert_type:
            raise ValueError('alert_type is required')
    return alerts


def validate_scheduler_status(status: SchedulerStatus) -> SchedulerStatus:
    if status.scheduled_run == status.ad_hoc_run:
        raise ValueError('scheduler status must set exactly one run mode')
    if not status.run_trigger_reason:
        raise ValueError('run_trigger_reason is required')
    if status.next_planned_run is None:
        raise ValueError('next_planned_run is required')
    return status


def validate_freshness_checks(checks: list[FreshnessCheck]) -> list[FreshnessCheck]:
    if not checks:
        raise ValueError('freshness checks cannot be empty')
    for check in checks:
        if check.required and not check.exists and check.status != 'missing_required_artifact':
            raise ValueError(f'invalid required-artifact status for {check.artifact}')
        if check.exists and check.age_minutes is None:
            raise ValueError(f'age_minutes required for existing artifact {check.artifact}')
    return checks


def validate_failure_records(records: list[FailureRecord]) -> list[FailureRecord]:
    valid_classes = {
        'missing_required_artifact',
        'stale_reference_data',
        'stale_runtime_outputs',
        'insufficient_candidate_depth',
        'degraded_internet_sources',
        'validation_failure',
        'scheduler_state_incomplete',
        'portfolio_quality_below_threshold',
        'excessive_alert_severity',
    }
    valid_severity = {'warning', 'critical'}
    for record in records:
        if record.failure_class not in valid_classes:
            raise ValueError(f'invalid failure class: {record.failure_class}')
        if record.severity not in valid_severity:
            raise ValueError(f'invalid failure severity: {record.severity}')
    return records


def validate_phase_completion(records: list[PhaseCompletionRecord]) -> list[PhaseCompletionRecord]:
    if not records:
        raise ValueError('phase completion records cannot be empty')
    phases = {r.phase for r in records}
    for required in {'phase3', 'phase4', 'phase5', 'phase6'}:
        if required not in phases:
            raise ValueError(f'missing phase completion record: {required}')
    return records


def validate_health_status_report(report: HealthStatusReport) -> HealthStatusReport:
    validate_freshness_checks(report.checks)
    validate_failure_records(report.failures)
    validate_phase_completion(report.phase_completion)
    if report.healthy and report.failures:
        raise ValueError('contradictory health state: healthy with failures')
    if report.failed and report.healthy:
        raise ValueError('contradictory health state: failed and healthy')
    if report.failed and not any(f.severity == 'critical' for f in report.failures):
        raise ValueError('failed health state requires critical failure')
    return report


def validate_operating_status_snapshot(snapshot: OperatingStatusSnapshot) -> OperatingStatusSnapshot:
    validate_scheduler_status(snapshot.scheduler_status)
    validate_health_status_report(snapshot.health_status)
    if snapshot.run_record.status != snapshot.health_status.overall_status:
        raise ValueError('run record status must match health overall_status')
    if not snapshot.top_operator_priorities:
        raise ValueError('top_operator_priorities cannot be empty')
    return snapshot


def validate_operating_run_record(record: OperatingRunRecord) -> OperatingRunRecord:
    if not record.run_id:
        raise ValueError('operating run_id is required')
    if record.scheduled_run == record.ad_hoc_run:
        raise ValueError('operating run must be scheduled xor ad_hoc')
    if record.status not in {'healthy', 'degraded', 'failed'}:
        raise ValueError(f'invalid operating run status: {record.status}')
    return record
