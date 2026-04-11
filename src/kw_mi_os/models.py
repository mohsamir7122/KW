from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class EntityType(str, Enum):
    kuwait_listed_equity = 'kuwait_listed_equity'
    context_macro = 'context_macro'
    unknown = 'unknown'


class ListingStatus(str, Enum):
    listed = 'listed'
    suspended = 'suspended'
    delisted = 'delisted'
    active = 'active'


class SourceClass(str, Enum):
    official_exchange = 'official_exchange'
    regulated_filing = 'regulated_filing'
    major_financial_media = 'major_financial_media'
    local_press = 'local_press'
    secondary_aggregator = 'secondary_aggregator'
    macro_context_only = 'macro_context_only'


@dataclass(frozen=True)
class UniverseRecord:
    symbol: str
    arabic_name: str
    english_name: str
    sector: str
    market: str
    listing_status: ListingStatus
    entity_type: EntityType
    tradable_flag: bool
    sec_code: int
    isin: str
    source_primary: str
    source_secondary: str
    verified_at_utc: datetime


@dataclass(frozen=True)
class QuarterlyRecord:
    symbol: str
    quarter_end: date
    fiscal_period: str
    filing_date: date
    revenue: float
    operating_profit: float
    net_profit: float
    eps: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    cash_from_operations: float
    capex: float
    dividend_flag: bool
    buyback_flag: bool
    material_event_flag: bool
    source_primary: str
    source_secondary: str
    verified_at_utc: datetime


@dataclass(frozen=True)
class SourceEvidenceRecord:
    source: str
    source_class: SourceClass
    parser_success: float
    completeness: float
    freshness: float
    conflict_penalty: float
    impacted_tradable: bool
    impact: float


@dataclass(frozen=True)
class GovernanceOutput:
    source: str
    trust_score: float
    contribution_score: float


@dataclass(frozen=True)
class SignalInput:
    symbol: str
    price_return_30d: float | None
    profit_margin: float | None
    avg_daily_value: float | None
    pe_ratio: float | None
    event_intensity: float | None
    evidence_coverage: float | None


@dataclass(frozen=True)
class SignalOutput:
    symbol: str
    trend_signal: float
    quality_signal: float
    liquidity_signal: float
    value_signal: float
    event_signal: float
    coverage_confidence: float
    missing_data_penalty: float


@dataclass(frozen=True)
class NormalizedEvidenceRecord:
    canonical_entity_id: str
    symbol: str
    source_name: str
    source_type: str
    evidence_type: str
    polarity: float
    confidence: float
    tradable_impact: float
    timestamp: datetime
    freshness_bucket: str
    source_reference: str


@dataclass(frozen=True)
class CandidateRecord:
    symbol: str
    base_signal: float
    trust_score: float
    final_score: float
    reason: str


@dataclass(frozen=True)
class ExclusionRecord:
    symbol: str
    blocked_by: str
    reason: str


@dataclass(frozen=True)
class QualityReport:
    run_id: str
    candidate_count: int
    exclusion_count: int
    validation_checks: list[str]


@dataclass(frozen=True)
class RunManifestModel:
    run_id: str
    created_at_utc: datetime
    mode: str
    phase: str
    git_commit: str
    internet_fetch_status: str
    files_read: list[str]
    files_written: list[str]
    input_checksums: dict[str, str]
    validations: list[str]
    warnings: list[str]
    failures: list[str]


@dataclass(frozen=True)
class HistoricalEquityState:
    symbol: str
    quarter_end: date
    fiscal_period: str
    filing_date: date
    net_profit: float
    eps: float
    total_equity: float


@dataclass(frozen=True)
class HistoricalEvidenceState:
    canonical_entity_id: str
    symbol: str
    source_name: str
    source_type: str
    evidence_type: str
    polarity: float
    confidence: float
    timestamp: datetime


@dataclass(frozen=True)
class HistoricalSnapshotRecord:
    snapshot_id: str
    as_of_date: date
    equity_state: list[HistoricalEquityState]
    evidence_state: list[HistoricalEvidenceState]
    coverage_symbols: list[str]


@dataclass(frozen=True)
class CandidateOutcomeRecord:
    symbol: str
    canonical_entity_id: str
    published: bool
    evaluable: bool
    outcome_status: str
    publish_rank: int
    publish_score: float
    realized_return: float | None
    direction_result: str | None
    publish_trust_score: float
    publish_missing_data_penalty: float


@dataclass(frozen=True)
class EvaluationReport:
    snapshot_id: str
    evaluated_count: int
    observed_count: int
    unavailable_count: int
    hit_rate: float | None
    average_realized_return: float | None
    rank_position_summary: dict[str, float]
    signal_contribution_summary: dict[str, dict[str, float]]
    trust_weighted_quality_summary: dict[str, float]
    missing_data_penalty_impact_summary: dict[str, float]
    limitations: list[str]


@dataclass(frozen=True)
class LearningRecord:
    symbol: str
    snapshot_id: str
    features: dict[str, float]
    outcome: dict[str, float | str]


@dataclass(frozen=True)
class SourceGrowthRecord:
    snapshot_id: str
    as_of_date: date
    source_coverage_over_time: list[dict[str, object]]
    source_participation_in_candidates: dict[str, int]
    source_acceptance_rejection_counts: dict[str, dict[str, int]]
    source_contribution_eligibility_summary: dict[str, float]


@dataclass(frozen=True)
class CalibrationMetadata:
    method: str
    sample_size: int
    effective_sample_size: int
    sparse_data_limited: bool
    calibration_factor: float
    confidence_band: dict[str, float]
    limitations: list[str]


@dataclass(frozen=True)
class CalibratedSignalRecord:
    symbol: str
    snapshot_id: str
    raw_signal: float
    calibrated_signal: float
    observed_return: float | None
    evaluable: bool
    outcome_status: str


@dataclass(frozen=True)
class BenchmarkResult:
    snapshot_id: str
    candidate_return_mean: float
    baseline_return_mean: float
    excess_return: float
    candidate_hit_rate: float | None
    baseline_hit_rate: float | None
    confidence_band: dict[str, float]
    summary: str
    limitations: list[str]


@dataclass(frozen=True)
class SignalUsefulnessReport:
    snapshot_id: str
    sample_size: int
    usefulness_score: float
    directional_accuracy_raw: float | None
    directional_accuracy_calibrated: float | None
    calibration_lift: float
    per_signal_summary: dict[str, dict[str, float]]
    limitations: list[str]


@dataclass(frozen=True)
class DecisionQualityReport:
    snapshot_id: str
    decision_quality_score: float
    confidence_band: dict[str, float]
    benchmark_comparison: dict[str, float]
    signal_usefulness: dict[str, float]
    summary: str
    limitations: list[str]


@dataclass(frozen=True)
class ProposedPosition:
    symbol: str
    canonical_entity_id: str
    target_weight: float
    rank: int
    final_score: float
    calibrated_signal: float
    decision_quality_score: float
    liquidity_signal: float
    tradable: bool
    inclusion_reason: str


@dataclass(frozen=True)
class PortfolioQualityReport:
    portfolio_quality_score: float
    quality_bucket: str
    included_count: int
    excluded_count: int
    average_decision_quality: float
    limitations: list[str]


@dataclass(frozen=True)
class PortfolioProposal:
    proposal_id: str
    generated_at_utc: str
    positions: list[ProposedPosition]
    excluded_candidates: list[dict[str, object]]
    max_holdings: int
    min_inclusion_quality: float
    total_target_weight: float
    quality_report: PortfolioQualityReport


@dataclass(frozen=True)
class RiskControlCheck:
    control_name: str
    status: str
    binding: bool
    details: dict[str, object]


@dataclass(frozen=True)
class PortfolioSnapshot:
    snapshot_id: str
    as_of_utc: str
    positions: list[dict[str, object]]
    residual_cash_weight: float


@dataclass(frozen=True)
class RiskControlResult:
    proposal_id: str
    controls: list[RiskControlCheck]
    adjusted_positions: list[ProposedPosition]
    residual_cash_weight: float
    turnover: float | None
    status: str
    risk_adjusted_snapshot: PortfolioSnapshot


@dataclass(frozen=True)
class RebalanceAction:
    symbol: str
    canonical_entity_id: str
    action: str
    prior_weight: float
    target_weight: float
    delta_weight: float
    reason: str


@dataclass(frozen=True)
class AlertRecord:
    alert_type: str
    severity: str
    message: str
    context: dict[str, object]
