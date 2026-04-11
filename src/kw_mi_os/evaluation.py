from __future__ import annotations

from dataclasses import asdict

from .models import CandidateOutcomeRecord, CandidateRecord, EvaluationReport, HistoricalSnapshotRecord


def track_candidate_outcomes(
    *,
    candidates: list[CandidateRecord],
    snapshot: HistoricalSnapshotRecord,
    observed_outcomes_by_symbol: dict[str, float],
    explanations_by_symbol: dict[str, dict],
) -> list[CandidateOutcomeRecord]:
    snapshot_symbols = {x.symbol for x in snapshot.equity_state}
    ranked_candidates = sorted(candidates, key=lambda c: (-c.final_score, c.symbol))

    records: list[CandidateOutcomeRecord] = []
    for idx, candidate in enumerate(ranked_candidates, start=1):
        if candidate.symbol not in snapshot_symbols:
            raise ValueError(f'invalid entity join: {candidate.symbol} missing from historical snapshot')

        explanation = explanations_by_symbol.get(candidate.symbol, {})
        penalty = float(explanation.get('missing_data_penalties', 0.0))

        realized_return = observed_outcomes_by_symbol.get(candidate.symbol)
        outcome_status = 'candidate_outcome_observed' if realized_return is not None else 'candidate_outcome_unavailable'
        direction_result = None
        if realized_return is not None:
            direction_result = 'hit' if realized_return >= 0 else 'miss'

        records.append(
            CandidateOutcomeRecord(
                symbol=candidate.symbol,
                canonical_entity_id=f'KW:{candidate.symbol}',
                published=True,
                evaluable=True,
                outcome_status=outcome_status,
                publish_rank=idx,
                publish_score=candidate.final_score,
                realized_return=realized_return,
                direction_result=direction_result,
                publish_trust_score=candidate.trust_score,
                publish_missing_data_penalty=penalty,
            )
        )
    return records


def generate_evaluation_report(
    *,
    snapshot: HistoricalSnapshotRecord,
    outcomes: list[CandidateOutcomeRecord],
    explanations_by_symbol: dict[str, dict],
) -> EvaluationReport:
    observed = [r for r in outcomes if r.outcome_status == 'candidate_outcome_observed' and r.realized_return is not None]
    hits = [r for r in observed if r.direction_result == 'hit']
    misses = [r for r in observed if r.direction_result == 'miss']

    rank_groups: dict[str, list[float]] = {'top_3': [], 'rank_4_10': [], 'rank_11_plus': []}
    for r in observed:
        if r.publish_rank <= 3:
            rank_groups['top_3'].append(r.realized_return or 0.0)
        elif r.publish_rank <= 10:
            rank_groups['rank_4_10'].append(r.realized_return or 0.0)
        else:
            rank_groups['rank_11_plus'].append(r.realized_return or 0.0)

    rank_summary = {
        k: round(sum(v) / len(v), 6) if v else 0.0
        for k, v in rank_groups.items()
    }

    signal_summary = {
        'hit': _summarize_signals(hits, explanations_by_symbol),
        'miss': _summarize_signals(misses, explanations_by_symbol),
    }

    trust_weighted = {
        'hit_avg_trust': round(sum(r.publish_trust_score for r in hits) / len(hits), 6) if hits else 0.0,
        'miss_avg_trust': round(sum(r.publish_trust_score for r in misses) / len(misses), 6) if misses else 0.0,
    }

    penalty_impact = {
        'observed_avg_missing_penalty': round(sum(r.publish_missing_data_penalty for r in observed) / len(observed), 6) if observed else 0.0,
        'hit_avg_missing_penalty': round(sum(r.publish_missing_data_penalty for r in hits) / len(hits), 6) if hits else 0.0,
        'miss_avg_missing_penalty': round(sum(r.publish_missing_data_penalty for r in misses) / len(misses), 6) if misses else 0.0,
    }

    limitations: list[str] = []
    if not observed:
        limitations.append('no_observed_outcomes_available')
    if observed and len(observed) < len(outcomes):
        limitations.append('partial_outcome_availability')
    if len(snapshot.coverage_symbols) < len(outcomes):
        limitations.append('snapshot_coverage_limited')

    return EvaluationReport(
        snapshot_id=snapshot.snapshot_id,
        evaluated_count=len(outcomes),
        observed_count=len(observed),
        unavailable_count=len(outcomes) - len(observed),
        hit_rate=round(len(hits) / len(observed), 6) if observed else None,
        average_realized_return=round(sum(r.realized_return or 0.0 for r in observed) / len(observed), 6) if observed else None,
        rank_position_summary=rank_summary,
        signal_contribution_summary=signal_summary,
        trust_weighted_quality_summary=trust_weighted,
        missing_data_penalty_impact_summary=penalty_impact,
        limitations=limitations,
    )


def outcome_records_to_json(records: list[CandidateOutcomeRecord]) -> list[dict]:
    return [asdict(r) for r in records]


def _summarize_signals(records: list[CandidateOutcomeRecord], explanations_by_symbol: dict[str, dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    count = 0
    for r in records:
        exp = explanations_by_symbol.get(r.symbol, {})
        top_signals = exp.get('top_contributing_signals', {})
        if not isinstance(top_signals, dict):
            continue
        count += 1
        for k, v in top_signals.items():
            totals[k] = totals.get(k, 0.0) + float(v)

    if count == 0:
        return {}
    return {k: round(v / count, 6) for k, v in sorted(totals.items())}
