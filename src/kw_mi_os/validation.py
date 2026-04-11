from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .models import (
    BenchmarkResult,
    CalibratedSignalRecord,
    CalibrationMetadata,
    CandidateRecord,
    CandidateOutcomeRecord,
    DecisionQualityReport,
    EvaluationReport,
    EntityType,
    HistoricalSnapshotRecord,
    LearningRecord,
    ListingStatus,
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
