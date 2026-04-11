from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from .models import (
    FailureRecord,
    FreshnessCheck,
    HealthStatusReport,
    OperatingRunRecord,
    OperatingStatusSnapshot,
    PhaseCompletionRecord,
    SchedulerStatus,
)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _sample_now(mode: str) -> datetime:
    if mode == 'sample':
        return datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _status_from_failures(failures: list[FailureRecord]) -> tuple[str, bool, bool, bool, bool]:
    critical = [f for f in failures if f.severity == 'critical']
    warnings = [f for f in failures if f.severity == 'warning']
    if critical:
        return ('failed', False, False, True, True)
    if warnings:
        return ('degraded', False, True, False, True)
    return ('healthy', True, False, False, False)


def _check_artifact(path: Path, now: datetime, stale_threshold_minutes: int, required: bool) -> FreshnessCheck:
    if not path.exists():
        status = 'missing_required_artifact' if required else 'missing_optional_artifact'
        return FreshnessCheck(
            artifact=str(path),
            exists=False,
            updated_at_utc=None,
            age_minutes=None,
            stale_threshold_minutes=stale_threshold_minutes,
            status=status,
            required=required,
        )
    updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = max(0.0, (now - updated).total_seconds() / 60.0)
    stale = age > stale_threshold_minutes
    return FreshnessCheck(
        artifact=str(path),
        exists=True,
        updated_at_utc=updated.isoformat(),
        age_minutes=round(age, 3),
        stale_threshold_minutes=stale_threshold_minutes,
        status='stale' if stale else 'fresh',
        required=required,
    )


def build_phase6_status(
    *,
    root: Path,
    mode: str,
    phase: str,
    internet_status: str,
    validations: list[str],
    warnings: list[str],
    manifest_run_id: str,
    manifest_created_at: str,
) -> tuple[OperatingRunRecord, SchedulerStatus, HealthStatusReport, OperatingStatusSnapshot, list[FailureRecord], list[FreshnessCheck]]:
    now = _sample_now(mode)
    trigger_reason = 'scheduled_run' if mode == 'sample' else 'ad_hoc_run'
    scheduled_run = mode == 'sample'
    ad_hoc_run = not scheduled_run

    history_path = root / 'runtime' / 'learning' / 'operating_run_history.json'
    last_successful_run = None
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding='utf-8'))
        if history:
            last_successful_run = str(history[-1].get('completed_at_utc'))

    next_planned = (now + timedelta(hours=24)).isoformat()
    if mode == 'sample':
        next_planned = '2026-04-12T00:00:00+00:00'

    scheduler_status = SchedulerStatus(
        scheduler_ready=True,
        deterministic_sample_mode=(mode == 'sample'),
        last_successful_run=last_successful_run,
        next_planned_run=next_planned,
        run_trigger_reason=trigger_reason,
        scheduled_run=scheduled_run,
        ad_hoc_run=ad_hoc_run,
    )

    required_checks = [
        _check_artifact(root / 'runtime' / 'latest' / 'candidates_latest.json', now, 24 * 60, True),
        _check_artifact(root / 'runtime' / 'latest' / 'evaluation_latest.json', now, 24 * 60, True),
        _check_artifact(root / 'runtime' / 'latest' / 'decision_quality_latest.json', now, 24 * 60, True),
        _check_artifact(root / 'runtime' / 'latest' / 'portfolio_latest.json', now, 24 * 60, True),
        _check_artifact(root / 'runtime' / 'latest' / 'alerts_latest.json', now, 6 * 60, True),
        _check_artifact(root / 'runtime' / 'latest' / 'run_manifest.json', now, 6 * 60, True),
    ]

    failures: list[FailureRecord] = []
    for check in required_checks:
        if not check.exists and check.required:
            failures.append(FailureRecord('missing_required_artifact', 'critical', check.artifact, 'Required runtime artifact missing.', 'Regenerate upstream phases before production run.'))
        if check.status == 'stale':
            failures.append(FailureRecord('stale_runtime_outputs', 'warning', check.artifact, 'Runtime artifact is stale.', 'Inspect data pipeline freshness and rerun sample/live pipeline.'))

    if internet_status != 'ok':
        failures.append(FailureRecord('degraded_internet_sources', 'warning', None, 'At least one upstream internet source is degraded/unavailable.', 'Inspect ingestion source reachability and fallback quality.'))

    if any(v.startswith('phase5_') for v in validations):
        portfolio_output_status = 'available'
    else:
        portfolio_output_status = 'missing'
        failures.append(FailureRecord('portfolio_quality_below_threshold', 'warning', 'runtime/quality/portfolio_quality_report.json', 'Portfolio outputs not validated in current run.', 'Run full phase pipeline before scheduling production loop.'))

    phase_completion = [
        PhaseCompletionRecord('phase3', (root / 'runtime' / 'learning' / 'evaluation_snapshot.json').exists(), 'runtime/learning/evaluation_snapshot.json'),
        PhaseCompletionRecord('phase4', (root / 'runtime' / 'quality' / 'decision_quality_report.json').exists(), 'runtime/quality/decision_quality_report.json'),
        PhaseCompletionRecord('phase5', (root / 'runtime' / 'latest' / 'portfolio_latest.json').exists(), 'runtime/latest/portfolio_latest.json'),
        PhaseCompletionRecord('phase6', True, 'runtime/latest/operating_status_latest.json'),
    ]

    if not all(p.completed for p in phase_completion[:-1]):
        failures.append(FailureRecord('scheduler_state_incomplete', 'critical', None, 'Prior phase completion state is incomplete.', 'Recover missing phase outputs before scheduling automated runs.'))

    alerts_path = root / 'runtime' / 'latest' / 'alerts_latest.json'
    alerts = []
    if alerts_path.exists():
        alerts = list(json.loads(alerts_path.read_text(encoding='utf-8')))
    severity_counts = {'critical': 0, 'warning': 0, 'info': 0}
    for alert in alerts:
        severity = str(alert.get('severity', 'info'))
        if severity in severity_counts:
            severity_counts[severity] += 1
    if severity_counts['critical'] > 0:
        failures.append(FailureRecord('excessive_alert_severity', 'warning', str(alerts_path), 'Critical alerts detected in latest alert stream.', 'Investigate critical alerts before trusting automation.'))

    if not validations:
        failures.append(FailureRecord('validation_failure', 'critical', None, 'Validation summary is empty.', 'Ensure validation pipeline executes before publishing status artifacts.'))

    overall_status, healthy, degraded, failed, degraded_mode = _status_from_failures(failures)

    health = HealthStatusReport(
        overall_status=overall_status,
        healthy=healthy,
        degraded=degraded,
        failed=failed,
        degraded_mode=degraded_mode,
        input_freshness_status='ok' if all(c.status == 'fresh' for c in required_checks if c.exists) else 'degraded',
        artifact_presence_status='ok' if all(c.exists for c in required_checks if c.required) else 'failed',
        validation_status='ok' if validations else 'failed',
        phase_completion_status='ok' if all(p.completed for p in phase_completion[:-1]) else 'failed',
        internet_status=internet_status,
        portfolio_output_status=portfolio_output_status,
        alert_summary={'total_alerts': len(alerts), 'severity_counts': severity_counts},
        checks=required_checks,
        failures=failures,
        phase_completion=phase_completion,
    )

    run_record = OperatingRunRecord(
        run_id=manifest_run_id,
        mode=mode,
        trigger_reason=trigger_reason,
        scheduled_run=scheduled_run,
        ad_hoc_run=ad_hoc_run,
        started_at_utc=manifest_created_at,
        completed_at_utc=now.isoformat(),
        status=overall_status,
    )

    priorities = [f"{f.failure_class}: {f.message}" for f in failures[:5]]
    if not priorities:
        priorities = ['No operator action required; system health is green.']

    snapshot = OperatingStatusSnapshot(
        run_record=run_record,
        scheduler_status=scheduler_status,
        health_status=health,
        top_operator_priorities=priorities,
        latest_manifest_run_id=manifest_run_id,
    )

    return run_record, scheduler_status, health, snapshot, failures, required_checks


def to_json(data: object) -> dict[str, object]:
    return asdict(data)
