from __future__ import annotations

from datetime import datetime, timezone

from .entity_resolution import resolve_to_canonical_symbol
from .models import NormalizedEvidenceRecord


def _freshness_bucket(ts: datetime) -> str:
    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if age_hours <= 24:
        return 'fresh'
    if age_hours <= 72:
        return 'stale'
    return 'old'


def normalize_evidence(
    raw_rows: list[dict], known_symbols: set[str], aliases: dict[str, str] | None = None
) -> tuple[list[NormalizedEvidenceRecord], list[dict]]:
    normalized: list[NormalizedEvidenceRecord] = []
    quarantined: list[dict] = []

    for row in raw_rows:
        resolution = resolve_to_canonical_symbol(str(row.get('symbol', '')), known_symbols, aliases)
        if resolution.canonical_symbol is None:
            quarantined.append({'symbol': row.get('symbol', ''), 'blocked_by': resolution.reason})
            continue

        ts = row.get('timestamp')
        if isinstance(ts, str):
            ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            ts_dt = datetime.now(timezone.utc)

        rec = NormalizedEvidenceRecord(
            canonical_entity_id=f'KW:{resolution.canonical_symbol}',
            symbol=resolution.canonical_symbol,
            source_name=str(row.get('source_name', 'unknown')),
            source_type=str(row.get('source_type', 'unknown')),
            evidence_type=str(row.get('evidence_type', 'news')),
            polarity=float(row.get('polarity', 0.0)),
            confidence=max(0.0, min(1.0, float(row.get('confidence', 0.0)))),
            tradable_impact=max(0.0, float(row.get('tradable_impact', 0.0))),
            timestamp=ts_dt,
            freshness_bucket=_freshness_bucket(ts_dt),
            source_reference=str(row.get('source_reference', '')),
        )
        normalized.append(rec)
    return normalized, quarantined
