from __future__ import annotations

from .models import GovernanceOutput, SourceClass, SourceEvidenceRecord

OFFICIAL_BONUS_BY_CLASS: dict[SourceClass, float] = {
    SourceClass.official_exchange: 0.04,
    SourceClass.regulated_filing: 0.03,
    SourceClass.major_financial_media: 0.01,
    SourceClass.local_press: 0.0,
    SourceClass.secondary_aggregator: -0.01,
    SourceClass.macro_context_only: -0.02,
}


def source_health(record: SourceEvidenceRecord) -> float:
    bonus = OFFICIAL_BONUS_BY_CLASS.get(record.source_class, 0.0)
    score = (
        0.35 * record.parser_success
        + 0.30 * record.completeness
        + 0.25 * record.freshness
        - 0.20 * record.conflict_penalty
        + bonus
    )
    return round(max(0.0, min(1.0, score)), 4)


def contribution_eligibility(record: SourceEvidenceRecord) -> bool:
    return record.impacted_tradable and record.source_class != SourceClass.macro_context_only


def governance_outputs(records: list[SourceEvidenceRecord]) -> dict[str, GovernanceOutput]:
    outputs: dict[str, GovernanceOutput] = {}
    for rec in records:
        trust = source_health(rec)
        contribution = rec.impact if contribution_eligibility(rec) else 0.0
        outputs[rec.source] = GovernanceOutput(
            source=rec.source,
            trust_score=trust,
            contribution_score=round(max(0.0, contribution), 4),
        )
    return outputs
