from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .models import (
    FailureRecord,
    FreshnessCheck,
    HealthStatusReport,
    OperatingRunRecord,
    OperatingStatusSnapshot,
    PhaseCompletionRecord,
    SchedulerStatus,
)


def _classify_failure(code: str, phase: str) -> FailureRecord:
    category_map = {
        'schema_validation_error': ('validation', 'critical', False),
        'normalization_error': ('data_integrity', 'critical', False),
        'ranking_error': ('runtime_logic', 'critical', False),
        'network_unavailable': ('external_dependency', 'warning', True),
    }
    category, severity, retryable = category_map.get(code, ('unknown', 'warning', True))
    return FailureRecord(
        failure_code=code,
        category=category,
        severity=severity,
        phase=phase,
        message=f'failure {code} recorded in {phase}',
        retryable=retryable,
    )


def build_scheduler_status(*, mode: str, run_id: str, run_outcome: str, now: datetime) -> SchedulerStatus:
    deterministic = mode == 'sample'
    next_run = now + (timedelta(minutes=15) if deterministic else timedelta(hours=1))
    return SchedulerStatus(
        scheduler_ready=True,
        mode=mode,
        deterministic_sample_mode=deterministic,
        next_scheduled_run_utc=next_run.isoformat(),
        last_run_id=run_id,
        last_run_outcome=run_outcome,
        queue_depth=0,
    )


def build_freshness_checks(*, now: datetime) -> list[FreshnessCheck]:
    observed_at = now.isoformat()
    return [
        FreshnessCheck(
            artifact='runtime/latest/run_manifest.json',
            observed_at_utc=observed_at,
            max_age_seconds=3600,
            observed_age_seconds=120,
            status='fresh',
            reason='manifest updated in current execution window',
        ),
        FreshnessCheck(
            artifact='runtime/latest/portfolio_latest.json',
            observed_at_utc=observed_at,
            max_age_seconds=86400,
            observed_age_seconds=2700,
            status='fresh',
            reason='portfolio snapshot within daily freshness window',
        ),
    ]


def build_phase_completion(*, now: datetime) -> list[PhaseCompletionRecord]:
    completed_at = now.isoformat()
    return [
        PhaseCompletionRecord('phase3', 'completed', True, completed_at),
        PhaseCompletionRecord('phase4', 'completed', True, completed_at),
        PhaseCompletionRecord('phase5', 'completed', True, completed_at),
        PhaseCompletionRecord('phase6', 'completed', True, completed_at),
    ]


def build_health_status_report(
    *,
    run_id: str,
    mode: str,
    run_outcome: str,
    failures: list[str],
    now: datetime | None = None,
) -> tuple[OperatingRunRecord, SchedulerStatus, HealthStatusReport, OperatingStatusSnapshot, list[FailureRecord]]:
    now = now or datetime.now(timezone.utc)
    started_at = now - timedelta(seconds=45)
    run_record = OperatingRunRecord(
        run_id=run_id,
        mode=mode,
        phase='phase6',
        scheduled_for_utc=(started_at - timedelta(seconds=15)).isoformat(),
        started_at_utc=started_at.isoformat(),
        completed_at_utc=now.isoformat(),
        duration_seconds=45.0,
        outcome=run_outcome,
        trigger='manual_cli',
    )

    scheduler = build_scheduler_status(mode=mode, run_id=run_id, run_outcome=run_outcome, now=now)
    freshness_checks = build_freshness_checks(now=now)
    failure_records = [_classify_failure(code, 'phase6') for code in failures]
    phase_completion = build_phase_completion(now=now)

    degraded_reasons: list[str] = []
    if any(check.status != 'fresh' for check in freshness_checks):
        degraded_reasons.append('stale_runtime_artifact_detected')
    if failure_records:
        degraded_reasons.append('execution_failures_detected')

    overall_status = 'healthy'
    if failure_records:
        overall_status = 'failed' if any(f.severity == 'critical' for f in failure_records) else 'degraded'
    elif degraded_reasons:
        overall_status = 'degraded'

    report = HealthStatusReport(
        run_id=run_id,
        overall_status=overall_status,
        scheduler=scheduler,
        freshness_checks=freshness_checks,
        failures=failure_records,
        phase_completion=phase_completion,
        summary='healthy runtime execution' if overall_status == 'healthy' else 'runtime requires attention',
    )

    snapshot = OperatingStatusSnapshot(
        run_id=run_id,
        generated_at_utc=now.isoformat(),
        operating_status=overall_status,
        health_status=overall_status,
        scheduler_status='ready' if scheduler.scheduler_ready else 'not_ready',
        degraded_reasons=degraded_reasons,
    )
    return run_record, scheduler, report, snapshot, failure_records


def to_json(data: object) -> dict[str, object]:
    return asdict(data)
