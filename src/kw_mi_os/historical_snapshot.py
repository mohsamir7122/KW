from __future__ import annotations

from datetime import date

from .models import (
    HistoricalEquityState,
    HistoricalEvidenceState,
    HistoricalSnapshotRecord,
    NormalizedEvidenceRecord,
    QuarterlyRecord,
)


def build_historical_snapshot(
    *,
    snapshot_id: str,
    as_of_date: date,
    quarterly_records: list[QuarterlyRecord],
    evidence_records: list[NormalizedEvidenceRecord],
) -> HistoricalSnapshotRecord:
    if not snapshot_id.strip():
        raise ValueError('snapshot_id is required')

    if not quarterly_records:
        raise ValueError('historical snapshot requires quarterly_records')
    if not evidence_records:
        raise ValueError('historical snapshot requires evidence_records')

    equity_state: list[HistoricalEquityState] = []
    for q in sorted(quarterly_records, key=lambda r: (r.symbol, r.quarter_end, r.filing_date), reverse=True):
        if q.quarter_end > as_of_date:
            raise ValueError(f'quarter_end {q.quarter_end.isoformat()} exceeds as_of_date {as_of_date.isoformat()}')
        if q.filing_date > as_of_date:
            raise ValueError(f'filing_date {q.filing_date.isoformat()} exceeds as_of_date {as_of_date.isoformat()}')
        if any(e.symbol == q.symbol for e in equity_state):
            continue
        equity_state.append(
            HistoricalEquityState(
                symbol=q.symbol,
                quarter_end=q.quarter_end,
                fiscal_period=q.fiscal_period,
                filing_date=q.filing_date,
                net_profit=q.net_profit,
                eps=q.eps,
                total_equity=q.total_equity,
            )
        )

    if not equity_state:
        raise ValueError('no equity_state available for as_of_date')

    evidence_state = [
        HistoricalEvidenceState(
            canonical_entity_id=e.canonical_entity_id,
            symbol=e.symbol,
            source_name=e.source_name,
            source_type=e.source_type,
            evidence_type=e.evidence_type,
            polarity=e.polarity,
            confidence=e.confidence,
            timestamp=e.timestamp,
        )
        for e in sorted(evidence_records, key=lambda r: (r.symbol, r.source_name, r.timestamp.isoformat(), r.source_reference))
        if e.timestamp.date() <= as_of_date
    ]

    if not evidence_state:
        raise ValueError('no evidence_state available for as_of_date')

    coverage_symbols = sorted({r.symbol for r in equity_state}.intersection({r.symbol for r in evidence_state}))
    if not coverage_symbols:
        raise ValueError('snapshot has no symbol coverage overlap between equity and evidence state')

    return HistoricalSnapshotRecord(
        snapshot_id=snapshot_id,
        as_of_date=as_of_date,
        equity_state=sorted(equity_state, key=lambda r: r.symbol),
        evidence_state=evidence_state,
        coverage_symbols=coverage_symbols,
    )
