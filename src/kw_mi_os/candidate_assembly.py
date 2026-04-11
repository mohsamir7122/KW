from __future__ import annotations

from .explainability import explain_candidate, explain_exclusion
from .models import (
    CandidateRecord,
    ExclusionRecord,
    GovernanceOutput,
    NormalizedEvidenceRecord,
    QualityReport,
    SignalOutput,
    UniverseRecord,
)


def assemble_candidates(
    tradable: list[UniverseRecord],
    signals: dict[str, SignalOutput],
    governance_by_symbol: dict[str, GovernanceOutput],
    evidence: list[NormalizedEvidenceRecord],
    run_id: str,
) -> tuple[list[CandidateRecord], list[ExclusionRecord], list[dict], QualityReport]:
    ev_count: dict[str, int] = {}
    for e in evidence:
        ev_count[e.symbol] = ev_count.get(e.symbol, 0) + 1

    candidates: list[CandidateRecord] = []
    exclusions: list[ExclusionRecord] = []
    explanations: list[dict] = []

    for u in tradable:
        sig = signals.get(u.symbol)
        if sig is None:
            exclusions.append(ExclusionRecord(symbol=u.symbol, blocked_by='signal_engine', reason='missing_signal'))
            explanations.append(explain_exclusion(u.symbol, 'missing_signal').to_dict())
            continue
        trust = governance_by_symbol.get(u.symbol, GovernanceOutput(source=u.symbol, trust_score=1.0, contribution_score=0.0)).trust_score
        signal_mix = (
            0.24 * sig.trend_signal
            + 0.20 * sig.quality_signal
            + 0.18 * sig.liquidity_signal
            + 0.16 * sig.value_signal
            + 0.12 * sig.event_signal
            + 0.10 * sig.coverage_confidence
        ) - sig.missing_data_penalty
        final = round(max(0.0, signal_mix) * trust, 4)
        if ev_count.get(u.symbol, 0) == 0:
            exclusions.append(ExclusionRecord(symbol=u.symbol, blocked_by='evidence', reason='no_normalized_evidence'))
            explanations.append(explain_exclusion(u.symbol, 'no_normalized_evidence').to_dict())
            continue
        candidate = CandidateRecord(
            symbol=u.symbol,
            base_signal=round(max(0.0, signal_mix), 4),
            trust_score=round(trust, 4),
            final_score=final,
            reason='included:validated_signal_and_governance',
        )
        candidates.append(candidate)
        exp = explain_candidate(candidate).to_dict()
        exp['included_or_excluded'] = 'included'
        exp['top_contributing_signals'] = {
            'trend_signal': sig.trend_signal,
            'quality_signal': sig.quality_signal,
            'liquidity_signal': sig.liquidity_signal,
        }
        exp['trust_contribution_summary'] = {'trust_score': trust}
        exp['evidence_summary'] = {'count': ev_count.get(u.symbol, 0)}
        exp['missing_data_penalties'] = sig.missing_data_penalty
        exp['final_score_composition'] = {'base_signal': candidate.base_signal, 'trust': candidate.trust_score, 'final': candidate.final_score}
        explanations.append(exp)

    candidates.sort(key=lambda c: (-c.final_score, c.symbol))
    quality = QualityReport(
        run_id=run_id,
        candidate_count=len(candidates),
        exclusion_count=len(exclusions),
        validation_checks=['candidate_schema', 'exclusion_schema', 'explainability_schema'],
    )
    return candidates, exclusions, explanations, quality
