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
