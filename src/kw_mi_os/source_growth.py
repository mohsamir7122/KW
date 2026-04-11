from __future__ import annotations

from dataclasses import asdict

from .models import HistoricalSnapshotRecord, NormalizedEvidenceRecord, SourceGrowthRecord


def build_source_growth_record(
    *,
    snapshot: HistoricalSnapshotRecord,
    evidence: list[NormalizedEvidenceRecord],
    quarantined: list[dict],
    candidate_symbols: list[str],
) -> SourceGrowthRecord:
    evidence_sorted = sorted(evidence, key=lambda e: (e.source_name, e.symbol))

    coverage: dict[str, set[str]] = {}
    participation: dict[str, int] = {}
    accepted: dict[str, int] = {}
    rejected: dict[str, int] = {}
    eligible: dict[str, list[float]] = {}

    candidate_set = set(candidate_symbols)

    for row in evidence_sorted:
        coverage.setdefault(row.source_name, set()).add(row.symbol)
        accepted[row.source_name] = accepted.get(row.source_name, 0) + 1
        if row.symbol in candidate_set:
            participation[row.source_name] = participation.get(row.source_name, 0) + 1
        eligible.setdefault(row.source_name, []).append(row.tradable_impact)

    for q in quarantined:
        src = str(q.get('source_name', 'unknown_source'))
        rejected[src] = rejected.get(src, 0) + 1

    coverage_over_time = [
        {
            'as_of_date': snapshot.as_of_date.isoformat(),
            'source_name': source,
            'covered_symbol_count': len(symbols),
        }
        for source, symbols in sorted(coverage.items())
    ]

    acceptance_rejection = {
        s: {
            'accepted': accepted.get(s, 0),
            'rejected': rejected.get(s, 0),
        }
        for s in sorted(set(accepted) | set(rejected))
    }

    eligibility_summary = {
        s: round(sum(vals) / len(vals), 6)
        for s, vals in sorted(eligible.items())
        if vals
    }

    return SourceGrowthRecord(
        snapshot_id=snapshot.snapshot_id,
        as_of_date=snapshot.as_of_date,
        source_coverage_over_time=coverage_over_time,
        source_participation_in_candidates=dict(sorted(participation.items())),
        source_acceptance_rejection_counts=acceptance_rejection,
        source_contribution_eligibility_summary=eligibility_summary,
    )


def source_growth_to_json(record: SourceGrowthRecord) -> dict:
    return asdict(record)
