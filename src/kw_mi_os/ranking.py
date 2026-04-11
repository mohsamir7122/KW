from __future__ import annotations

from .models import CandidateRecord, GovernanceOutput, SignalOutput, UniverseRecord


def rank_candidates(
    tradable_universe: list[UniverseRecord],
    signal_by_symbol: dict[str, SignalOutput],
    trust_by_symbol: dict[str, GovernanceOutput],
) -> list[CandidateRecord]:
    ranked: list[CandidateRecord] = []
    for row in tradable_universe:
        sym = row.symbol
        sig = signal_by_symbol.get(sym)
        if sig is None:
            continue
        base_signal = (
            0.24 * sig.trend_signal
            + 0.20 * sig.quality_signal
            + 0.18 * sig.liquidity_signal
            + 0.16 * sig.value_signal
            + 0.12 * sig.event_signal
            + 0.10 * sig.coverage_confidence
        ) - sig.missing_data_penalty
        base_signal = round(max(0.0, base_signal), 4)
        trust_score = float(trust_by_symbol.get(sym, GovernanceOutput(source=sym, trust_score=1.0, contribution_score=0.0)).trust_score)
        final_score = round(base_signal * trust_score, 4)  # trust applied exactly once
        ranked.append(
            CandidateRecord(
                symbol=sym,
                base_signal=base_signal,
                trust_score=round(trust_score, 4),
                final_score=final_score,
                reason='included:signal_engine_ranked',
            )
        )
    ranked.sort(key=lambda c: (-c.final_score, c.symbol))
    return ranked
