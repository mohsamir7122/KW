from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import (
    AlertRecord,
    BenchmarkResult,
    CandidateRecord,
    ConsolidatedLatestReport,
    DailyReviewSummary,
    DashboardSnapshot,
    DecisionQualityReport,
    HealthStatusReport,
    OperatingStatusSnapshot,
    PortfolioSnapshot,
    RebalanceAction,
    ReportingMetadata,
    ReviewChecklist,
    ReviewChecklistItem,
)


def _to_health_bucket(health_status: str) -> str:
    if health_status == 'failed':
        return 'failed'
    if health_status == 'degraded':
        return 'degraded'
    return 'healthy'


def _alert_weight(severity: str) -> int:
    return {'critical': 3, 'warning': 2, 'info': 1}.get(severity, 0)


def build_dashboard_snapshot(
    *,
    run_id: str,
    mode: str,
    operating_status: OperatingStatusSnapshot,
    health_report: HealthStatusReport,
    candidates: list[CandidateRecord],
    decision_quality: DecisionQualityReport,
    benchmark: BenchmarkResult,
    portfolio: PortfolioSnapshot,
    rebalance_actions: list[RebalanceAction],
    alerts: list[AlertRecord],
) -> DashboardSnapshot:
    top_candidates = [
        {
            'symbol': c.symbol,
            'final_score': round(c.final_score, 6),
            'trust_score': round(c.trust_score, 6),
            'reason': c.reason,
        }
        for c in sorted(candidates, key=lambda row: (-row.final_score, row.symbol))[:5]
    ]
    portfolio_symbols = [str(p.get('symbol')) for p in portfolio.positions]
    critical_alert_count = sum(1 for a in alerts if a.severity == 'critical')
    warning_alert_count = sum(1 for a in alerts if a.severity == 'warning')

    return DashboardSnapshot(
        run_id=run_id,
        mode=mode,
        operating_status=operating_status.operating_status,
        health_status=health_report.overall_status,
        status_bucket=_to_health_bucket(health_report.overall_status),
        top_candidates=top_candidates,
        decision_quality_summary={
            'score': round(decision_quality.decision_quality_score, 6),
            'summary': decision_quality.summary,
            'confidence_band': dict(decision_quality.confidence_band),
        },
        benchmark_summary={
            'excess_return': round(benchmark.excess_return, 6),
            'candidate_return_mean': round(benchmark.candidate_return_mean, 6),
            'baseline_return_mean': round(benchmark.baseline_return_mean, 6),
            'summary': benchmark.summary,
        },
        portfolio_summary={
            'snapshot_id': portfolio.snapshot_id,
            'position_count': len(portfolio.positions),
            'residual_cash_weight': round(portfolio.residual_cash_weight, 6),
            'symbols': portfolio_symbols,
        },
        rebalance_summary={
            'action_count': len(rebalance_actions),
            'actions_by_type': {
                action_type: sum(1 for action in rebalance_actions if action.action == action_type)
                for action_type in ['add', 'increase', 'decrease', 'hold', 'remove']
            },
        },
        alert_summary={
            'total_alerts': len(alerts),
            'critical_alert_count': critical_alert_count,
            'warning_alert_count': warning_alert_count,
            'top_alerts': [
                {'severity': a.severity, 'alert_type': a.alert_type, 'message': a.message}
                for a in sorted(alerts, key=lambda a: (-_alert_weight(a.severity), a.alert_type))[:5]
            ],
        },
    )


def build_daily_review_summary(
    *,
    dashboard: DashboardSnapshot,
    health_report: HealthStatusReport,
    alerts: list[AlertRecord],
    rebalance_actions: list[RebalanceAction],
) -> DailyReviewSummary:
    run_completed_successfully = dashboard.status_bucket != 'failed'
    important_rebalance = [
        asdict(action)
        for action in rebalance_actions
        if action.action in {'add', 'remove', 'increase', 'decrease'}
    ]
    critical_alerts = [asdict(a) for a in alerts if a.severity == 'critical']
    degraded_reasons = list(dashboard.alert_summary.get('top_alerts', [])) if dashboard.status_bucket == 'degraded' else []

    first_checks: list[str] = [
        'Confirm run completion and health status',
        'Review critical alerts and degraded conditions',
        'Inspect portfolio and rebalance deltas',
    ]

    return DailyReviewSummary(
        run_id=dashboard.run_id,
        run_completed_successfully=run_completed_successfully,
        system_state=dashboard.status_bucket,
        health_summary=health_report.summary,
        important_portfolio_changes=important_rebalance[:5],
        material_alerts=critical_alerts[:5],
        decision_quality_acceptable=dashboard.decision_quality_summary['score'] >= 0.45,
        benchmark_context_acceptable=dashboard.benchmark_summary['excess_return'] >= -0.05,
        degraded_reasons=degraded_reasons,
        inspect_first=first_checks,
        human_summary=(
            'Run completed with healthy operating context.'
            if dashboard.status_bucket == 'healthy'
            else 'Run completed with issues. Prioritize alerts and degraded checks.'
        ),
    )


def build_review_checklist(summary: DailyReviewSummary, dashboard: DashboardSnapshot) -> ReviewChecklist:
    items = [
        ReviewChecklistItem('confirm_run_completed', 'Confirm latest run completed', 'critical', 1, summary.run_completed_successfully, 'Run completion gate for operator trust.'),
        ReviewChecklistItem('confirm_health_status', 'Confirm health status is not failed', 'critical', 2, summary.system_state != 'failed', f"Current health bucket: {summary.system_state}"),
        ReviewChecklistItem('inspect_critical_alerts', 'Inspect critical alerts', 'critical', 3, len(summary.material_alerts) == 0, 'Critical alerts dominate daily operator attention.'),
        ReviewChecklistItem('inspect_degraded_conditions', 'Inspect degraded conditions', 'high', 4, summary.system_state != 'degraded', 'Degraded runs require explicit review before acceptance.'),
        ReviewChecklistItem('review_top_candidates', 'Review top candidates and exclusions', 'high', 5, len(dashboard.top_candidates) > 0, 'Validate selection outputs remain plausible.'),
        ReviewChecklistItem('review_portfolio_changes', 'Review portfolio changes', 'high', 6, len(summary.important_portfolio_changes) > 0, 'Position changes drive practical investment impact.'),
        ReviewChecklistItem('review_rebalance_actions', 'Review rebalance actions', 'medium', 7, dashboard.rebalance_summary['action_count'] > 0, 'Action plan should be auditable before execution.'),
        ReviewChecklistItem('review_decision_quality', 'Review decision-quality score', 'medium', 8, summary.decision_quality_acceptable, 'Low decision quality weakens confidence in outputs.'),
        ReviewChecklistItem('review_benchmark_context', 'Review benchmark-relative summary', 'medium', 9, summary.benchmark_context_acceptable, 'Benchmark context helps qualify confidence.'),
        ReviewChecklistItem('review_freshness_warnings', 'Review stale/freshness warnings', 'low', 10, summary.system_state == 'healthy', 'Freshness issues can invalidate otherwise good outputs.'),
    ]
    return ReviewChecklist(
        run_id=summary.run_id,
        ordered=True,
        checklist_type='daily_review',
        items=items,
    )


def build_reporting_metadata(
    *,
    mode: str,
    upstream_inputs: list[str],
    generated_outputs: list[str],
    deterministic: bool,
) -> ReportingMetadata:
    return ReportingMetadata(
        phase='phase7',
        mode=mode,
        deterministic_sample_mode=deterministic,
        upstream_inputs=sorted(upstream_inputs),
        generated_outputs=sorted(generated_outputs),
        explainability_notes=[
            'Daily summary is derived from validated Phase 3-6 outputs only.',
            'Checklist priority is severity-first and deterministic.',
            'No ranking, portfolio, or monitoring logic is mutated in Phase 7.',
        ],
    )


def build_consolidated_latest_report(
    *,
    dashboard: DashboardSnapshot,
    summary: DailyReviewSummary,
    checklist: ReviewChecklist,
    metadata: ReportingMetadata,
) -> ConsolidatedLatestReport:
    return ConsolidatedLatestReport(
        run_id=dashboard.run_id,
        dashboard_snapshot=asdict(dashboard),
        daily_review_summary=asdict(summary),
        operator_checklist=asdict(checklist),
        reporting_metadata=asdict(metadata),
        operator_ready=(
            summary.run_completed_successfully
            and summary.system_state != 'failed'
            and len(summary.material_alerts) == 0
        ),
    )


def to_json(data: Any) -> dict[str, object]:
    return asdict(data)
