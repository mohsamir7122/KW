from __future__ import annotations

from dataclasses import asdict

from .models import CandidateOutcomeRecord, LearningRecord


def build_learning_records(
    *,
    snapshot_id: str,
    outcomes: list[CandidateOutcomeRecord],
    explanations_by_symbol: dict[str, dict],
) -> list[LearningRecord]:
    records: list[LearningRecord] = []
    for outcome in outcomes:
        if outcome.outcome_status != 'candidate_outcome_observed' or outcome.realized_return is None:
            continue
        exp = explanations_by_symbol.get(outcome.symbol, {})
        factors = exp.get('contributing_factors', {}) if isinstance(exp.get('contributing_factors', {}), dict) else {}
        signals = exp.get('top_contributing_signals', {}) if isinstance(exp.get('top_contributing_signals', {}), dict) else {}

        features = {
            'base_signal': float(factors.get('base_signal', 0.0)),
            'trust_score': float(factors.get('trust_score', outcome.publish_trust_score)),
            'missing_data_penalty': float(exp.get('missing_data_penalties', outcome.publish_missing_data_penalty)),
            'trend_signal': float(signals.get('trend_signal', 0.0)),
            'quality_signal': float(signals.get('quality_signal', 0.0)),
            'liquidity_signal': float(signals.get('liquidity_signal', 0.0)),
            'publish_rank': float(outcome.publish_rank),
        }

        records.append(
            LearningRecord(
                symbol=outcome.symbol,
                snapshot_id=snapshot_id,
                features=features,
                outcome={
                    'realized_return': float(outcome.realized_return),
                    'direction_result': str(outcome.direction_result or 'unknown'),
                },
            )
        )

    records.sort(key=lambda r: r.symbol)
    return records


def learning_records_to_json(records: list[LearningRecord]) -> list[dict]:
    return [asdict(r) for r in records]
