from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from .models import (
    AlertRecord,
    CandidateRecord,
    CalibratedSignalRecord,
    DecisionQualityReport,
    PortfolioProposal,
    PortfolioQualityReport,
    PortfolioSnapshot,
    ProposedPosition,
    RebalanceAction,
    RiskControlCheck,
    RiskControlResult,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_weights(positions: list[ProposedPosition], total_target: float) -> list[ProposedPosition]:
    if not positions:
        return []
    current_total = sum(p.target_weight for p in positions)
    if current_total <= 0:
        return []
    scale = total_target / current_total
    normalized: list[ProposedPosition] = []
    for p in positions:
        normalized.append(
            ProposedPosition(
                symbol=p.symbol,
                canonical_entity_id=p.canonical_entity_id,
                target_weight=round(p.target_weight * scale, 6),
                rank=p.rank,
                final_score=p.final_score,
                calibrated_signal=p.calibrated_signal,
                decision_quality_score=p.decision_quality_score,
                liquidity_signal=p.liquidity_signal,
                tradable=p.tradable,
                inclusion_reason=p.inclusion_reason,
            )
        )
    return normalized


def _portfolio_quality_bucket(score: float) -> str:
    if score >= 0.75:
        return 'high'
    if score >= 0.5:
        return 'moderate'
    return 'weak'


def construct_portfolio_proposal(
    candidates: list[CandidateRecord],
    calibrated_signals: list[CalibratedSignalRecord],
    decision_quality_score: float,
    liquidity_by_symbol: dict[str, float],
    tradable_symbols: set[str],
    *,
    min_inclusion_quality: float,
    max_holdings: int,
    target_invested_weight: float = 1.0,
) -> PortfolioProposal:
    calibrated_by_symbol = {c.symbol: c for c in calibrated_signals}
    positions: list[ProposedPosition] = []
    excluded: list[dict[str, object]] = []

    ranked = sorted(candidates, key=lambda c: (-c.final_score, c.symbol))
    for idx, candidate in enumerate(ranked, start=1):
        cal = calibrated_by_symbol.get(candidate.symbol)
        if cal is None:
            excluded.append({'symbol': candidate.symbol, 'reason': 'missing_calibrated_signal'})
            continue
        if candidate.final_score < min_inclusion_quality:
            excluded.append({'symbol': candidate.symbol, 'reason': 'below_min_inclusion_quality', 'value': candidate.final_score})
            continue
        tradable = candidate.symbol in tradable_symbols
        if not tradable:
            excluded.append({'symbol': candidate.symbol, 'reason': 'non_tradable'})
            continue
        liquidity_signal = liquidity_by_symbol.get(candidate.symbol)
        if liquidity_signal is None:
            excluded.append({'symbol': candidate.symbol, 'reason': 'missing_liquidity_signal'})
            continue
        positions.append(
            ProposedPosition(
                symbol=candidate.symbol,
                canonical_entity_id=f'KW:{candidate.symbol}',
                target_weight=round(candidate.final_score, 6),
                rank=idx,
                final_score=round(candidate.final_score, 6),
                calibrated_signal=round(cal.calibrated_signal, 6),
                decision_quality_score=round(decision_quality_score, 6),
                liquidity_signal=round(liquidity_signal, 6),
                tradable=tradable,
                inclusion_reason='selected_from_validated_ranked_candidates',
            )
        )

    selected = positions[:max_holdings]
    for dropped in positions[max_holdings:]:
        excluded.append({'symbol': dropped.symbol, 'reason': 'max_holdings_cap'})

    normalized = _normalize_weights(selected, target_invested_weight)
    quality_score = 0.0
    if normalized:
        quality_score = round(sum(p.calibrated_signal * p.target_weight for p in normalized), 6)

    report = PortfolioQualityReport(
        portfolio_quality_score=quality_score,
        quality_bucket=_portfolio_quality_bucket(quality_score),
        included_count=len(normalized),
        excluded_count=len(excluded),
        average_decision_quality=round(decision_quality_score, 6),
        limitations=[
            'insufficient_candidate_depth' if len(normalized) < max_holdings else 'none'
        ] if len(normalized) < max_holdings else [],
    )

    return PortfolioProposal(
        proposal_id=f'portfolio_proposal_{datetime.now(timezone.utc).strftime("%Y%m%d")}',
        generated_at_utc=_now_iso(),
        positions=normalized,
        excluded_candidates=excluded,
        max_holdings=max_holdings,
        min_inclusion_quality=min_inclusion_quality,
        total_target_weight=round(sum(p.target_weight for p in normalized), 6),
        quality_report=report,
    )


def apply_risk_controls(
    proposal: PortfolioProposal,
    prior_snapshot: PortfolioSnapshot | None,
    *,
    max_single_position_weight: float,
    max_total_active_positions: int,
    min_liquidity_signal: float,
    min_decision_quality_signal: float,
    turnover_cap: float,
    cash_buffer: float,
) -> RiskControlResult:
    checks: list[RiskControlCheck] = []
    adjusted = list(proposal.positions)

    before_symbols = {p.symbol for p in adjusted}
    adjusted = [p for p in adjusted if p.tradable]
    removed_non_tradable = sorted(before_symbols - {p.symbol for p in adjusted})
    checks.append(
        RiskControlCheck(
            control_name='minimum_tradability_gate',
            status='pass' if not removed_non_tradable else 'adjusted',
            binding=bool(removed_non_tradable),
            details={'removed_symbols': removed_non_tradable},
        )
    )

    liquidity_removed = [p.symbol for p in adjusted if p.liquidity_signal < min_liquidity_signal]
    adjusted = [p for p in adjusted if p.liquidity_signal >= min_liquidity_signal]
    checks.append(
        RiskControlCheck(
            control_name='minimum_liquidity_gate',
            status='pass' if not liquidity_removed else 'adjusted',
            binding=bool(liquidity_removed),
            details={'removed_symbols': sorted(liquidity_removed), 'threshold': min_liquidity_signal},
        )
    )

    dq_removed = [p.symbol for p in adjusted if p.calibrated_signal < min_decision_quality_signal]
    adjusted = [p for p in adjusted if p.calibrated_signal >= min_decision_quality_signal]
    checks.append(
        RiskControlCheck(
            control_name='minimum_decision_quality_gate',
            status='pass' if not dq_removed else 'adjusted',
            binding=bool(dq_removed),
            details={'removed_symbols': sorted(dq_removed), 'threshold': min_decision_quality_signal},
        )
    )

    if len(adjusted) > max_total_active_positions:
        kept = sorted(adjusted, key=lambda p: (-p.target_weight, p.symbol))[:max_total_active_positions]
        removed = sorted({p.symbol for p in adjusted} - {p.symbol for p in kept})
        adjusted = kept
        checks.append(
            RiskControlCheck(
                control_name='max_total_active_positions',
                status='adjusted',
                binding=True,
                details={'removed_symbols': removed, 'max_total_active_positions': max_total_active_positions},
            )
        )
    else:
        checks.append(
            RiskControlCheck(
                control_name='max_total_active_positions',
                status='pass',
                binding=False,
                details={'active_positions': len(adjusted), 'max_total_active_positions': max_total_active_positions},
            )
        )

    capped: list[ProposedPosition] = []
    cap_bindings: list[str] = []
    for p in adjusted:
        capped_weight = min(p.target_weight, max_single_position_weight)
        if capped_weight < p.target_weight:
            cap_bindings.append(p.symbol)
        capped.append(
            ProposedPosition(
                symbol=p.symbol,
                canonical_entity_id=p.canonical_entity_id,
                target_weight=round(capped_weight, 6),
                rank=p.rank,
                final_score=p.final_score,
                calibrated_signal=p.calibrated_signal,
                decision_quality_score=p.decision_quality_score,
                liquidity_signal=p.liquidity_signal,
                tradable=p.tradable,
                inclusion_reason=p.inclusion_reason,
            )
        )
    adjusted = capped
    checks.append(
        RiskControlCheck(
            control_name='max_single_position_weight',
            status='pass' if not cap_bindings else 'adjusted',
            binding=bool(cap_bindings),
            details={'capped_symbols': sorted(cap_bindings), 'max_single_position_weight': max_single_position_weight},
        )
    )

    target_weight_after_buffer = _clamp(1.0 - cash_buffer, 0.0, 1.0)
    adjusted = _normalize_weights(adjusted, target_weight_after_buffer)

    turnover = None
    if prior_snapshot is None:
        checks.append(
            RiskControlCheck(
                control_name='turnover_cap',
                status='limitation',
                binding=False,
                details={'reason': 'missing_prior_portfolio_snapshot'},
            )
        )
    else:
        prior_weights = {str(p['symbol']): float(p['weight']) for p in prior_snapshot.positions}
        new_weights = {p.symbol: p.target_weight for p in adjusted}
        symbols = set(prior_weights) | set(new_weights)
        turnover = round(sum(abs(new_weights.get(sym, 0.0) - prior_weights.get(sym, 0.0)) for sym in symbols), 6)
        if turnover > turnover_cap:
            scale = turnover_cap / turnover if turnover > 0 else 0.0
            interpolated: list[ProposedPosition] = []
            for p in adjusted:
                prior_weight = prior_weights.get(p.symbol, 0.0)
                new_weight = prior_weight + (p.target_weight - prior_weight) * scale
                interpolated.append(
                    ProposedPosition(
                        symbol=p.symbol,
                        canonical_entity_id=p.canonical_entity_id,
                        target_weight=round(new_weight, 6),
                        rank=p.rank,
                        final_score=p.final_score,
                        calibrated_signal=p.calibrated_signal,
                        decision_quality_score=p.decision_quality_score,
                        liquidity_signal=p.liquidity_signal,
                        tradable=p.tradable,
                        inclusion_reason=p.inclusion_reason,
                    )
                )
            adjusted = _normalize_weights(interpolated, target_weight_after_buffer)
            turnover = turnover_cap
            checks.append(
                RiskControlCheck(
                    control_name='turnover_cap',
                    status='adjusted',
                    binding=True,
                    details={'turnover': turnover, 'turnover_cap': turnover_cap},
                )
            )
        else:
            checks.append(
                RiskControlCheck(
                    control_name='turnover_cap',
                    status='pass',
                    binding=False,
                    details={'turnover': turnover, 'turnover_cap': turnover_cap},
                )
            )

    residual = round(max(0.0, 1.0 - sum(p.target_weight for p in adjusted)), 6)
    risk_adjusted_snapshot = PortfolioSnapshot(
        snapshot_id=f'portfolio_snapshot_{datetime.now(timezone.utc).strftime("%Y%m%d")}',
        as_of_utc=_now_iso(),
        positions=[{'symbol': p.symbol, 'canonical_entity_id': p.canonical_entity_id, 'weight': p.target_weight} for p in adjusted],
        residual_cash_weight=residual,
    )

    return RiskControlResult(
        proposal_id=proposal.proposal_id,
        controls=checks,
        adjusted_positions=adjusted,
        residual_cash_weight=residual,
        turnover=turnover,
        status='pass' if all(c.status in {'pass', 'limitation'} for c in checks) else 'adjusted',
        risk_adjusted_snapshot=risk_adjusted_snapshot,
    )


def plan_rebalance(
    prior_snapshot: PortfolioSnapshot | None,
    target_snapshot: PortfolioSnapshot,
) -> list[RebalanceAction]:
    if prior_snapshot is None:
        return [
            RebalanceAction(
                symbol=pos['symbol'],
                canonical_entity_id=pos['canonical_entity_id'],
                action='add',
                prior_weight=0.0,
                target_weight=float(pos['weight']),
                delta_weight=round(float(pos['weight']), 6),
                reason='new_portfolio_position_without_prior_snapshot',
            )
            for pos in target_snapshot.positions
        ]

    prior_by_symbol = {str(p['symbol']): p for p in prior_snapshot.positions}
    target_by_symbol = {str(p['symbol']): p for p in target_snapshot.positions}

    for symbol in set(prior_by_symbol) & set(target_by_symbol):
        prior_id = str(prior_by_symbol[symbol]['canonical_entity_id'])
        target_id = str(target_by_symbol[symbol]['canonical_entity_id'])
        if prior_id != target_id:
            raise ValueError(f'invalid_entity_join_for_rebalance:{symbol}')

    actions: list[RebalanceAction] = []
    for symbol in sorted(set(prior_by_symbol) | set(target_by_symbol)):
        prior = prior_by_symbol.get(symbol)
        target = target_by_symbol.get(symbol)
        prior_weight = float(prior['weight']) if prior else 0.0
        target_weight = float(target['weight']) if target else 0.0
        delta = round(target_weight - prior_weight, 6)

        if prior is None and target is not None:
            action = 'add'
            reason = 'entered_target_portfolio'
            canonical_id = str(target['canonical_entity_id'])
        elif prior is not None and target is None:
            action = 'remove'
            reason = 'not_in_target_after_controls'
            canonical_id = str(prior['canonical_entity_id'])
        elif abs(delta) <= 1e-6:
            action = 'hold'
            reason = 'no_material_weight_change'
            canonical_id = str(target['canonical_entity_id'])
        elif delta > 0:
            action = 'increase'
            reason = 'target_weight_above_prior_weight'
            canonical_id = str(target['canonical_entity_id'])
        else:
            action = 'decrease'
            reason = 'target_weight_below_prior_weight'
            canonical_id = str(target['canonical_entity_id'])

        actions.append(
            RebalanceAction(
                symbol=symbol,
                canonical_entity_id=canonical_id,
                action=action,
                prior_weight=round(prior_weight, 6),
                target_weight=round(target_weight, 6),
                delta_weight=delta,
                reason=reason,
            )
        )
    return actions


def build_alerts(
    decision_quality: DecisionQualityReport,
    proposal: PortfolioProposal,
    risk: RiskControlResult,
    rebalance_actions: list[RebalanceAction],
    benchmark_excess_return: float,
) -> list[AlertRecord]:
    alerts: list[AlertRecord] = []

    if proposal.quality_report.quality_bucket == 'weak':
        alerts.append(AlertRecord('portfolio_quality_degraded', 'warning', 'Portfolio quality bucket is weak.', {'quality_score': proposal.quality_report.portfolio_quality_score}))
    if decision_quality.decision_quality_score < 0.5:
        alerts.append(AlertRecord('decision_quality_below_threshold', 'warning', 'Decision quality is below minimum threshold.', {'decision_quality_score': decision_quality.decision_quality_score}))
    if benchmark_excess_return < 0:
        alerts.append(AlertRecord('benchmark_underperformance_warning', 'warning', 'Benchmark excess return is negative.', {'excess_return': benchmark_excess_return}))
    if len(proposal.positions) < proposal.max_holdings:
        alerts.append(AlertRecord('insufficient_candidate_depth', 'info', 'Portfolio has fewer positions than max holdings cap.', {'included_count': len(proposal.positions), 'max_holdings': proposal.max_holdings}))

    if any(c.control_name == 'turnover_cap' and c.binding for c in risk.controls):
        alerts.append(AlertRecord('excessive_turnover_warning', 'warning', 'Turnover cap is binding.', {'turnover': risk.turnover}))
    if any(c.binding for c in risk.controls if c.status == 'adjusted'):
        alerts.append(AlertRecord('constraint_binding_heavily', 'info', 'One or more constraints adjusted the proposal.', {'binding_controls': [c.control_name for c in risk.controls if c.binding]}))
    if decision_quality.limitations:
        alerts.append(AlertRecord('sparse_history_limitation_warning', 'info', 'Decision quality report contains limitations.', {'limitations': decision_quality.limitations}))

    missing_data_risk = sum(1 for e in proposal.excluded_candidates if 'missing' in str(e.get('reason', '')))
    if missing_data_risk > 0:
        alerts.append(AlertRecord('missing_data_risk_elevated', 'warning', 'Missing data exclusions were detected in portfolio construction.', {'missing_data_exclusions': missing_data_risk}))

    if not alerts:
        alerts.append(AlertRecord('portfolio_operating_state_nominal', 'info', 'No critical portfolio or risk alerts raised.', {'rebalance_actions': len(rebalance_actions)}))

    return alerts


def alerts_to_json(alerts: list[AlertRecord]) -> list[dict[str, object]]:
    return [asdict(a) for a in alerts]
