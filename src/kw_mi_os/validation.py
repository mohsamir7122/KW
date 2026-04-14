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
    DashboardSnapshot,
    DailyReviewSummary,
    EvaluationReport,
    EntityType,
    PortfolioProposal,
    PortfolioSnapshot,
    RebalanceAction,
    RiskControlResult,
    HistoricalSnapshotRecord,
    LearningRecord,
    ListingStatus,
    MarketDataQualityReport,
    MarketDataRow,
    MarketDataSnapshot,
    MarketSourceStatus,
    OperatingRunRecord,
    OperatingStatusSnapshot,
    ConsolidatedLatestReport,
    DailyExportBundle,
    DailyRolloutReport,
    ExportMetadata,
    MarkdownSummary,
    OperatorVerdict,
    Phase11AcceptanceGateResult,
    Phase11ChallengerEvaluation,
    Phase11Dataset,
    Phase11DriftReport,
    Phase11FeatureRecord,
    Phase11LabelRecord,
    Phase11ModelRegistryEntry,
    Phase11RetrainingRecommendation,
    ReportingMetadata,
    RolloutHistory,
    RolloutMetadata,
    ReviewChecklist,
    SignoffRecommendation,
    FreshnessCheck,
    FailureRecord,
    PhaseCompletionRecord,
    HealthStatusReport,
    SchedulerStatus,
    QuarterlyRecord,
    RunManifestModel,
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


def validate_operating_run_record(record: OperatingRunRecord) -> OperatingRunRecord:
    if record.duration_seconds < 0:
        raise ValueError('run duration cannot be negative')
    if not record.run_id:
        raise ValueError('run_id is required')
    return record


def validate_scheduler_status(status: SchedulerStatus) -> SchedulerStatus:
    if status.queue_depth < 0:
        raise ValueError('scheduler queue depth cannot be negative')
    if not status.last_run_id:
        raise ValueError('scheduler last_run_id is required')
    return status


def validate_freshness_checks(checks: list[FreshnessCheck]) -> list[FreshnessCheck]:
    for check in checks:
        if check.observed_age_seconds < 0:
            raise ValueError(f'invalid observed_age_seconds for {check.artifact}')
        if check.status not in {'fresh', 'stale'}:
            raise ValueError(f'invalid freshness status for {check.artifact}')
    return checks


def validate_failure_records(records: list[FailureRecord]) -> list[FailureRecord]:
    for failure in records:
        if failure.severity not in {'warning', 'critical'}:
            raise ValueError(f'invalid failure severity {failure.severity}')
    return records


def validate_phase_completion(records: list[PhaseCompletionRecord]) -> list[PhaseCompletionRecord]:
    for record in records:
        if record.status not in {'completed', 'skipped', 'failed'}:
            raise ValueError(f'invalid phase status {record.status}')
    return records


def validate_health_status_report(report: HealthStatusReport) -> HealthStatusReport:
    if report.overall_status not in {'healthy', 'degraded', 'failed'}:
        raise ValueError('invalid overall health status')
    validate_scheduler_status(report.scheduler)
    validate_freshness_checks(report.freshness_checks)
    validate_failure_records(report.failures)
    validate_phase_completion(report.phase_completion)
    return report


def validate_operating_status_snapshot(snapshot: OperatingStatusSnapshot) -> OperatingStatusSnapshot:
    if snapshot.operating_status not in {'healthy', 'degraded', 'failed'}:
        raise ValueError('invalid operating status')
    if snapshot.scheduler_status not in {'ready', 'not_ready'}:
        raise ValueError('invalid scheduler status')
    return snapshot


def validate_dashboard_snapshot(snapshot: DashboardSnapshot) -> DashboardSnapshot:
    if snapshot.status_bucket not in {'healthy', 'degraded', 'failed'}:
        raise ValueError('invalid dashboard status_bucket')
    required_sections = (
        snapshot.decision_quality_summary,
        snapshot.benchmark_summary,
        snapshot.portfolio_summary,
        snapshot.rebalance_summary,
        snapshot.alert_summary,
    )
    if any(not section for section in required_sections):
        raise ValueError('dashboard snapshot missing required summary sections')
    return snapshot


def validate_daily_review_summary(summary: DailyReviewSummary) -> DailyReviewSummary:
    if summary.system_state not in {'healthy', 'degraded', 'failed'}:
        raise ValueError('invalid daily review system_state')
    if summary.system_state == 'failed' and summary.run_completed_successfully:
        raise ValueError('contradictory summary state: failed cannot be successful')
    if not summary.inspect_first:
        raise ValueError('daily review inspect_first cannot be empty')
    return summary


def validate_review_checklist(checklist: ReviewChecklist) -> ReviewChecklist:
    if not checklist.ordered:
        raise ValueError('review checklist must be ordered')
    if not checklist.items:
        raise ValueError('review checklist requires items')
    valid_severity = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
    last_priority = 0
    last_severity_weight = 99
    for item in checklist.items:
        if item.severity not in valid_severity:
            raise ValueError(f'invalid checklist severity {item.severity}')
        if item.priority <= last_priority:
            raise ValueError('checklist priorities must be strictly increasing')
        if valid_severity[item.severity] > last_severity_weight:
            raise ValueError('checklist severity must be non-increasing by priority')
        last_priority = item.priority
        last_severity_weight = valid_severity[item.severity]
    return checklist


def validate_reporting_metadata(metadata: ReportingMetadata) -> ReportingMetadata:
    if metadata.phase != 'phase7':
        raise ValueError('reporting metadata phase must be phase7')
    if not metadata.upstream_inputs:
        raise ValueError('reporting metadata upstream_inputs required')
    if not metadata.generated_outputs:
        raise ValueError('reporting metadata generated_outputs required')
    return metadata


def validate_consolidated_latest_report(report: ConsolidatedLatestReport) -> ConsolidatedLatestReport:
    required = [report.dashboard_snapshot, report.daily_review_summary, report.operator_checklist, report.reporting_metadata]
    if any(not section for section in required):
        raise ValueError('consolidated latest report missing required section')
    return report


def validate_phase7_required_inputs(required_paths: list[Path]) -> list[Path]:
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        missing_text = ', '.join(str(path) for path in missing)
        raise ValueError(f'phase7 missing upstream artifacts: {missing_text}')
    return required_paths


def validate_operator_verdict(verdict: OperatorVerdict) -> OperatorVerdict:
    if verdict.verdict_status not in {'approved', 'caution', 'reject'}:
        raise ValueError('invalid verdict_status')
    if verdict.signoff_recommendation not in {
        'approve_today_output',
        'review_with_caution_before_signoff',
        'reject_until_manual_resolution',
    }:
        raise ValueError('invalid signoff_recommendation')
    if not verdict.required_manual_checks:
        raise ValueError('required_manual_checks cannot be empty')
    if verdict.verdict_status == 'approved' and verdict.escalation_needed:
        raise ValueError('approved verdict cannot require escalation')
    return verdict


def validate_signoff_recommendation(signoff: SignoffRecommendation) -> SignoffRecommendation:
    if signoff.verdict_status not in {'approved', 'caution', 'reject'}:
        raise ValueError('invalid signoff verdict status')
    if signoff.verdict_status == 'approved' and signoff.recommendation != 'approve_today_output':
        raise ValueError('approved verdict must map to approve_today_output')
    if signoff.verdict_status == 'caution' and signoff.recommendation != 'review_with_caution_before_signoff':
        raise ValueError('caution verdict must map to review_with_caution_before_signoff')
    if signoff.verdict_status == 'reject' and signoff.recommendation != 'reject_until_manual_resolution':
        raise ValueError('reject verdict must map to reject_until_manual_resolution')
    if signoff.approved_for_next_cycle and signoff.verdict_status != 'approved':
        raise ValueError('only approved verdict can be approved_for_next_cycle')
    return signoff


def validate_daily_rollout_report(report: DailyRolloutReport) -> DailyRolloutReport:
    if report.run_mode not in {'sample', 'live'}:
        raise ValueError('invalid rollout run_mode')
    if report.health_state not in {'healthy', 'degraded', 'failed'}:
        raise ValueError('invalid rollout health_state')
    if report.operator_verdict not in {'approved', 'caution', 'reject'}:
        raise ValueError('invalid rollout operator_verdict')
    if report.operator_verdict == 'approved' and report.health_state == 'failed':
        raise ValueError('approved rollout cannot be failed')
    if report.operator_verdict == 'reject' and report.signoff_recommendation != 'reject_until_manual_resolution':
        raise ValueError('reject rollout must require manual resolution')
    if not report.inspect_first:
        raise ValueError('rollout inspect_first cannot be empty')
    return report


def validate_rollout_history(history: RolloutHistory) -> RolloutHistory:
    if history.window_days != 30:
        raise ValueError('rollout history must use 30-day window')
    if len(history.records) > history.window_days:
        raise ValueError('rollout history exceeds window')
    last_key = ''
    seen_keys: set[str] = set()
    for row in history.records:
        if row.health_state not in {'healthy', 'degraded', 'failed'}:
            raise ValueError('invalid rollout history health_state')
        compound = f'{row.run_date}:{row.run_mode}'
        if compound in seen_keys:
            raise ValueError('duplicate rollout history day+mode entry')
        seen_keys.add(compound)
        if compound < last_key:
            raise ValueError('rollout history must be sorted by run_date')
        last_key = compound
    return history


def validate_rollout_metadata(metadata: RolloutMetadata) -> RolloutMetadata:
    if metadata.phase != 'phase8':
        raise ValueError('rollout metadata phase must be phase8')
    if metadata.history_window_days != 30:
        raise ValueError('rollout metadata history window must be 30')
    if not metadata.upstream_inputs or not metadata.generated_outputs:
        raise ValueError('rollout metadata requires upstream_inputs and generated_outputs')
    return metadata


def validate_phase8_required_inputs(required_paths: list[Path]) -> list[Path]:
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        missing_text = ', '.join(str(path) for path in missing)
        raise ValueError(f'phase8 missing upstream artifacts: {missing_text}')
    return required_paths


def validate_export_metadata(metadata: ExportMetadata) -> ExportMetadata:
    if metadata.phase != 'phase9':
        raise ValueError('export metadata phase must be phase9')
    if not metadata.export_version:
        raise ValueError('export metadata requires export_version')
    if metadata.mode not in {'sample', 'live'}:
        raise ValueError('export metadata mode must be sample|live')
    if not metadata.exported_files:
        raise ValueError('export metadata requires exported_files')
    if not metadata.source_manifest_reference.endswith('run_manifest.json'):
        raise ValueError('export metadata source_manifest_reference must reference run_manifest.json')
    return metadata


def validate_markdown_summary(summary: MarkdownSummary) -> MarkdownSummary:
    required_sections = [
        'Executive Summary',
        'Dashboard Snapshot',
        'Daily Review Summary',
        'Operating Status / Health',
        'Portfolio & Rebalance',
        'Alerts',
        'Operator Verdict / Signoff',
        'Export Metadata',
    ]
    if not summary.content.strip():
        raise ValueError('markdown summary cannot be empty')
    for section in required_sections:
        if f'## {section}' not in summary.content:
            raise ValueError(f'markdown summary missing section: {section}')
    return summary


def validate_daily_export_bundle(bundle: DailyExportBundle) -> DailyExportBundle:
    if not bundle.run_id:
        raise ValueError('daily export bundle requires run_id')
    if not bundle.dashboard_snapshot or not bundle.daily_review_summary or not bundle.consolidated_latest_report:
        raise ValueError('daily export bundle missing required report sections')
    if not bundle.operating_status_summary or not bundle.portfolio_latest:
        raise ValueError('daily export bundle missing operating/portfolio summaries')
    validate_export_metadata(bundle.export_metadata)
    summary_state = str(bundle.daily_review_summary.get('system_state', ''))
    operating_state = str(bundle.operating_status_summary.get('operating_status', ''))
    if summary_state and operating_state and summary_state != operating_state:
        raise ValueError('daily export contradiction: summary system_state != operating operating_status')
    return bundle


def validate_csv_export(path: Path, required_headers: list[str]) -> None:
    if not path.exists():
        raise ValueError(f'missing csv export: {path}')
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        if headers != required_headers:
            raise ValueError(f'csv headers mismatch for {path}: expected {required_headers} got {headers}')
        for index, row in enumerate(reader, start=2):
            if set(row.keys()) != set(required_headers):
                raise ValueError(f'csv row/column mismatch for {path} at line {index}')


def validate_market_source_statuses(statuses: list[MarketSourceStatus]) -> list[MarketSourceStatus]:
    if not statuses:
        raise ValueError('market source statuses cannot be empty')
    for status in statuses:
        if not status.source_name:
            raise ValueError('market source_name is required')
        if status.rows_fetched < 0:
            raise ValueError('market rows_fetched cannot be negative')
    return statuses


def validate_market_data_rows(rows: list[MarketDataRow]) -> list[MarketDataRow]:
    if not rows:
        raise ValueError('market data rows cannot be empty')
    seen: set[str] = set()
    for row in rows:
        if not row.symbol or not row.company_name:
            raise ValueError('market row missing symbol/company_name')
        if not row.canonical_entity_id.startswith('KW:'):
            raise ValueError(f'market row unresolved canonical mapping for {row.symbol}')
        if row.last_price <= 0:
            raise ValueError(f'market row invalid last_price for {row.symbol}')
        if row.symbol in seen:
            raise ValueError(f'market row duplicate symbol {row.symbol}')
        seen.add(row.symbol)
    return rows


def validate_market_quality_report(report: MarketDataQualityReport) -> MarketDataQualityReport:
    if report.rows_total < 0 or report.unique_symbols < 0:
        raise ValueError('market quality row counts must be non-negative')
    if report.ready_for_downstream and report.validation_failures:
        raise ValueError('market quality cannot be ready_for_downstream with validation_failures')
    return report


def validate_market_data_snapshot(snapshot: MarketDataSnapshot) -> MarketDataSnapshot:
    if not snapshot.snapshot_id:
        raise ValueError('market snapshot_id is required')
    validate_market_source_statuses(snapshot.sources)
    validate_market_quality_report(snapshot.quality)
    if snapshot.quality.ready_for_downstream:
        validate_market_data_rows(snapshot.rows)
    return snapshot


def validate_phase11_feature_store(records: list[Phase11FeatureRecord]) -> list[Phase11FeatureRecord]:
    if not records:
        raise ValueError('phase11 feature store cannot be empty')
    for record in records:
        if not record.symbol or not record.as_of_date:
            raise ValueError('phase11 feature row missing symbol/as_of_date')
        if not record.features:
            raise ValueError('phase11 feature row requires features')
    return records


def validate_phase11_label_store(records: list[Phase11LabelRecord]) -> list[Phase11LabelRecord]:
    if not records:
        raise ValueError('phase11 label store cannot be empty')
    required = {'label_1d', 'label_5d', 'label_20d'}
    for record in records:
        if set(record.labels.keys()) != required:
            raise ValueError('phase11 label store requires 1d/5d/20d labels')
    return records


def validate_phase11_dataset(dataset: Phase11Dataset) -> Phase11Dataset:
    if dataset.row_count < 3:
        raise ValueError('phase11 dataset requires at least 3 rows')
    if dataset.horizons != ('1d', '5d', '20d'):
        raise ValueError('phase11 dataset horizons must be 1d/5d/20d')
    for split in ('train', 'validation', 'test'):
        if split not in dataset.temporal_split or not dataset.temporal_split[split]:
            raise ValueError(f'phase11 dataset missing temporal split: {split}')
    if not dataset.leakage_checks.get('label_keys_not_in_features', False):
        raise ValueError('phase11 leakage check failed: label keys present in features')
    if not dataset.leakage_checks.get('strict_time_order', False):
        raise ValueError('phase11 leakage check failed: non-strict time order')
    return dataset


def validate_phase11_challenger_evaluation(report: Phase11ChallengerEvaluation) -> Phase11ChallengerEvaluation:
    if report.evaluation_scope != 'challenger_only':
        raise ValueError('phase11 evaluation must be challenger_only')
    if report.return_lift != round(report.challenger_return - report.baseline_return, 6):
        raise ValueError('phase11 challenger return_lift mismatch')
    return report


def validate_phase11_acceptance_gates(gates: Phase11AcceptanceGateResult) -> Phase11AcceptanceGateResult:
    expected = gates.minimum_lift_passed and gates.directional_accuracy_passed and gates.max_drawdown_passed
    if gates.accepted != expected:
        raise ValueError('phase11 acceptance gates inconsistent')
    return gates


def validate_phase11_registry_entry(entry: Phase11ModelRegistryEntry) -> Phase11ModelRegistryEntry:
    if entry.acceptance_status not in {'accepted', 'rejected'}:
        raise ValueError('phase11 registry acceptance_status invalid')
    if entry.auto_promotion:
        raise ValueError('phase11 forbids auto_promotion')
    if entry.promotion_state != 'manual_review_required':
        raise ValueError('phase11 promotion_state must be manual_review_required')
    return entry


def validate_phase11_drift_report(report: Phase11DriftReport) -> Phase11DriftReport:
    if report.max_feature_drift < 0:
        raise ValueError('phase11 drift cannot be negative')
    if not report.per_feature_drift:
        raise ValueError('phase11 per_feature_drift cannot be empty')
    return report


def validate_phase11_retraining_recommendation(
    recommendation: Phase11RetrainingRecommendation,
) -> Phase11RetrainingRecommendation:
    if recommendation.recommendation not in {'schedule_retraining', 'monitor_only'}:
        raise ValueError('phase11 retraining recommendation invalid')
    if recommendation.should_retrain and recommendation.recommendation != 'schedule_retraining':
        raise ValueError('phase11 retraining recommendation mismatch')
    if not recommendation.should_retrain and recommendation.recommendation != 'monitor_only':
        raise ValueError('phase11 retraining recommendation mismatch')
    return recommendation
