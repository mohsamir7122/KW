from __future__ import annotations

from dataclasses import asdict

from .models import DailyRolloutReport, OperatorVerdict, RolloutDayRecord, RolloutHistory, RolloutMetadata, SignoffRecommendation


def _ranked_issues(*, health_state: str, total_alerts: int, critical_alerts: int, warning_alerts: int, decision_quality_score: float) -> list[str]:
    issues: list[str] = []
    if health_state == 'failed':
        issues.append('health_state_failed')
    elif health_state == 'degraded':
        issues.append('health_state_degraded')
    if critical_alerts > 0:
        issues.append('critical_alerts_present')
    if warning_alerts > 0:
        issues.append('warning_alerts_present')
    if total_alerts == 0:
        issues.append('no_operational_alerts_reported')
    if decision_quality_score < 0.45:
        issues.append('decision_quality_below_threshold')
    return issues[:5]


def build_operator_verdict(
    *,
    run_id: str,
    health_state: str,
    decision_quality_score: float,
    benchmark_excess_return: float,
    alert_summary: dict[str, int],
    degraded_reasons: list[str],
    daily_inspect_first: list[str],
) -> OperatorVerdict:
    critical = int(alert_summary.get('critical_alert_count', 0))
    warnings = int(alert_summary.get('warning_alert_count', 0))

    status = 'approved'
    if health_state == 'failed' or critical > 0:
        status = 'reject'
    elif health_state == 'degraded' or warnings > 0 or decision_quality_score < 0.5:
        status = 'caution'

    signoff = {
        'approved': 'approve_today_output',
        'caution': 'review_with_caution_before_signoff',
        'reject': 'reject_until_manual_resolution',
    }[status]

    top_risks = _ranked_issues(
        health_state=health_state,
        total_alerts=int(alert_summary.get('total_alerts', 0)),
        critical_alerts=critical,
        warning_alerts=warnings,
        decision_quality_score=decision_quality_score,
    )
    if benchmark_excess_return < 0:
        top_risks = (top_risks + ['negative_benchmark_excess_return'])[:5]

    positives: list[str] = []
    if health_state == 'healthy':
        positives.append('health_state_healthy')
    if critical == 0:
        positives.append('no_critical_alerts')
    if decision_quality_score >= 0.5:
        positives.append('decision_quality_above_threshold')
    if benchmark_excess_return >= 0:
        positives.append('non_negative_benchmark_excess_return')

    checks = list(dict.fromkeys(daily_inspect_first + [
        'Validate latest run manifest and phase validations',
        'Review top risks and remediation owners',
    ]))[:6]

    escalation = status == 'reject' or health_state == 'failed'
    rationale = (
        f"verdict={status}; health={health_state}; critical_alerts={critical}; "
        f"warning_alerts={warnings}; decision_quality={decision_quality_score:.4f}; "
        f"degraded_reasons={','.join(sorted(degraded_reasons)) if degraded_reasons else 'none'}"
    )

    return OperatorVerdict(
        run_id=run_id,
        verdict_status=status,
        signoff_recommendation=signoff,
        top_risks=top_risks,
        top_positive_signals=positives[:5],
        required_manual_checks=checks,
        escalation_needed=escalation,
        rationale=rationale,
    )


def build_signoff_recommendation(*, verdict: OperatorVerdict) -> SignoffRecommendation:
    approved_for_next_cycle = verdict.verdict_status == 'approved' and not verdict.escalation_needed
    return SignoffRecommendation(
        run_id=verdict.run_id,
        recommendation=verdict.signoff_recommendation,
        verdict_status=verdict.verdict_status,
        approved_for_next_cycle=approved_for_next_cycle,
        required_manual_checks=list(verdict.required_manual_checks),
        priority_inspection_order=list(verdict.top_risks or verdict.required_manual_checks[:3]),
        notes=[
            'Phase 8 consumes upstream validated outputs only.',
            'Any reject verdict requires manual operator resolution before next live cycle.',
        ],
    )


def build_daily_rollout_report(
    *,
    run_id: str,
    run_date: str,
    run_mode: str,
    run_completion_status: str,
    health_state: str,
    alert_summary: dict[str, int],
    top_issues: list[str],
    portfolio_rebalance_present: bool,
    decision_quality_present: bool,
    verdict: OperatorVerdict,
) -> DailyRolloutReport:
    return DailyRolloutReport(
        run_id=run_id,
        run_date=run_date,
        run_mode=run_mode,
        run_completion_status=run_completion_status,
        health_state=health_state,
        degraded_or_failed=health_state in {'degraded', 'failed'},
        top_issues=top_issues[:5],
        portfolio_rebalance_present=portfolio_rebalance_present,
        decision_quality_present=decision_quality_present,
        alert_summary={
            'total_alerts': int(alert_summary.get('total_alerts', 0)),
            'critical_alert_count': int(alert_summary.get('critical_alert_count', 0)),
            'warning_alert_count': int(alert_summary.get('warning_alert_count', 0)),
        },
        operator_verdict=verdict.verdict_status,
        signoff_recommendation=verdict.signoff_recommendation,
        verdict_rationale=verdict.rationale,
        inspect_first=list(verdict.required_manual_checks)[:5],
    )


def append_rollout_history(*, existing: list[dict[str, object]], report: DailyRolloutReport, window_days: int = 30) -> RolloutHistory:
    record = RolloutDayRecord(
        run_date=report.run_date,
        run_mode=report.run_mode,
        run_completion_status=report.run_completion_status,
        health_state=report.health_state,
        degraded_or_failed=report.degraded_or_failed,
        top_issues=list(report.top_issues),
        operator_verdict=report.operator_verdict,
        signoff_recommendation=report.signoff_recommendation,
        portfolio_rebalance_present=report.portfolio_rebalance_present,
        decision_quality_present=report.decision_quality_present,
        alert_summary=dict(report.alert_summary),
        run_id=report.run_id,
    )

    parsed = [RolloutDayRecord(**row) for row in existing]
    without_same_day = [row for row in parsed if not (row.run_date == record.run_date and row.run_mode == record.run_mode)]
    updated = sorted(without_same_day + [record], key=lambda row: (row.run_date, row.run_mode))[-window_days:]

    return RolloutHistory(
        window_days=window_days,
        records=updated,
        latest_run_id=record.run_id,
        latest_run_date=record.run_date,
    )


def build_rollout_metadata(*, mode: str, upstream_inputs: list[str], generated_outputs: list[str], deterministic: bool) -> RolloutMetadata:
    return RolloutMetadata(
        phase='phase8',
        mode=mode,
        deterministic_sample_mode=deterministic,
        upstream_inputs=sorted(upstream_inputs),
        generated_outputs=sorted(generated_outputs),
        history_window_days=30,
        persistence_limitation_note=(
            'In CI/sandbox execution, runtime artifacts may be ephemeral across jobs. '
            'Scheduled workflow still publishes downloadable artifacts for audit continuity.'
        ),
    )


def to_json(data: object) -> dict[str, object]:
    return asdict(data)
