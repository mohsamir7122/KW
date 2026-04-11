from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

from .models import CsvExportSpec, DailyExportBundle, ExportMetadata, MarkdownSummary


EXPORT_VERSION = 'phase9.v1'


def _iso_now(mode: str) -> str:
    if mode == 'sample':
        return '2026-04-10T00:00:00Z'
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _required_latest_inputs(root: Path) -> list[Path]:
    return [
        root / 'runtime' / 'latest' / 'dashboard_snapshot.json',
        root / 'runtime' / 'latest' / 'daily_review_latest.json',
        root / 'runtime' / 'latest' / 'consolidated_latest_report.json',
        root / 'runtime' / 'latest' / 'operating_status_latest.json',
        root / 'runtime' / 'latest' / 'portfolio_latest.json',
        root / 'runtime' / 'latest' / 'rebalance_latest.json',
        root / 'runtime' / 'latest' / 'alerts_latest.json',
    ]


def validate_phase9_required_inputs(required_paths: list[Path]) -> list[Path]:
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        raise ValueError('phase9 missing upstream artifacts: ' + ', '.join(str(path) for path in missing))
    return required_paths


def _load_json(path: Path) -> dict[str, object] | list[dict[str, object]]:
    parsed = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return [dict(row) for row in parsed]
    raise ValueError(f'expected JSON object/array in {path}')


def build_daily_export_bundle(*, root: Path, mode: str) -> tuple[DailyExportBundle, list[CsvExportSpec], MarkdownSummary]:
    validate_phase9_required_inputs(_required_latest_inputs(root))

    reports_dir = root / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = root / 'runtime' / 'latest' / 'run_manifest.json'
    manifest = dict(_load_json(manifest_path)) if manifest_path.exists() else {}
    dashboard = dict(_load_json(root / 'runtime' / 'latest' / 'dashboard_snapshot.json'))
    daily_review = dict(_load_json(root / 'runtime' / 'latest' / 'daily_review_latest.json'))
    consolidated = dict(_load_json(root / 'runtime' / 'latest' / 'consolidated_latest_report.json'))
    operating = dict(_load_json(root / 'runtime' / 'latest' / 'operating_status_latest.json'))
    portfolio = dict(_load_json(root / 'runtime' / 'latest' / 'portfolio_latest.json'))
    rebalance = list(_load_json(root / 'runtime' / 'latest' / 'rebalance_latest.json'))
    alerts = list(_load_json(root / 'runtime' / 'latest' / 'alerts_latest.json'))

    verdict: dict[str, object] | None = None
    signoff: dict[str, object] | None = None
    verdict_path = root / 'runtime' / 'latest' / 'operator_verdict_latest.json'
    signoff_path = root / 'runtime' / 'latest' / 'signoff_recommendation_latest.json'
    if verdict_path.exists():
        verdict = dict(_load_json(verdict_path))
    if signoff_path.exists():
        signoff = dict(_load_json(signoff_path))

    exported_files = [
        'reports/daily_export_latest.json',
        'reports/daily_summary.md',
        'reports/candidates_latest.csv',
        'reports/portfolio_latest.csv',
        'reports/rebalance_latest.csv',
        'reports/alerts_latest.csv',
        'reports/operating_status_latest.csv',
        'reports/export_metadata.json',
    ]
    metadata = ExportMetadata(
        phase='phase9',
        export_version=EXPORT_VERSION,
        mode=mode,
        export_timestamp_utc=_iso_now(mode),
        source_run_timestamp_utc=str(manifest.get('created_at_utc')) if manifest.get('created_at_utc') else None,
        source_manifest_reference='runtime/latest/run_manifest.json',
        phase_coverage=['phase7', 'phase8', 'phase9'],
        exported_files=exported_files,
        warnings_limitations=[
            'CSV exports are analysis-friendly flattened views; JSON remains canonical.',
            'In CI/sandbox execution, local reports/ persistence may be ephemeral between jobs.',
        ],
        deterministic_sample_mode=(mode == 'sample'),
    )

    bundle = DailyExportBundle(
        run_id=str(dashboard.get('run_id', 'unknown_run')),
        mode=mode,
        dashboard_snapshot=dashboard,
        daily_review_summary=daily_review,
        consolidated_latest_report=consolidated,
        operating_status_summary=operating,
        portfolio_latest=portfolio,
        rebalance_latest=rebalance,
        alerts_latest=alerts,
        operator_verdict=verdict,
        signoff_recommendation=signoff,
        export_metadata=metadata,
    )

    candidate_rows = [
        {
            'symbol': str(row.get('symbol', '')),
            'final_score': row.get('final_score', ''),
            'trust_score': row.get('trust_score', ''),
            'reason': str(row.get('reason', '')),
        }
        for row in dashboard.get('top_candidates', [])
        if isinstance(row, dict)
    ]

    portfolio_rows = [
        {
            'snapshot_id': str(portfolio.get('snapshot_id', '')),
            'as_of_utc': str(portfolio.get('as_of_utc', '')),
            'symbol': str(row.get('symbol', '')),
            'canonical_entity_id': str(row.get('canonical_entity_id', '')),
            'weight': row.get('weight', ''),
        }
        for row in portfolio.get('positions', [])
        if isinstance(row, dict)
    ]

    rebalance_rows = [
        {
            'symbol': str(row.get('symbol', '')),
            'canonical_entity_id': str(row.get('canonical_entity_id', '')),
            'action': str(row.get('action', '')),
            'prior_weight': row.get('prior_weight', ''),
            'target_weight': row.get('target_weight', ''),
            'delta_weight': row.get('delta_weight', ''),
            'reason': str(row.get('reason', '')),
        }
        for row in rebalance
    ]

    alert_rows = [
        {
            'severity': str(row.get('severity', '')),
            'alert_type': str(row.get('alert_type', '')),
            'message': str(row.get('message', '')),
        }
        for row in alerts
    ]

    operating_rows = [
        {
            'run_id': str(operating.get('run_id', '')),
            'generated_at_utc': str(operating.get('generated_at_utc', '')),
            'operating_status': str(operating.get('operating_status', '')),
            'health_status': str(operating.get('health_status', '')),
            'scheduler_status': str(operating.get('scheduler_status', '')),
            'degraded_reasons': '|'.join(str(v) for v in operating.get('degraded_reasons', [])),
        }
    ]

    csv_specs = [
        CsvExportSpec('candidates_latest', 'reports/candidates_latest.csv', ['symbol', 'final_score', 'trust_score', 'reason'], len(candidate_rows)),
        CsvExportSpec('portfolio_latest', 'reports/portfolio_latest.csv', ['snapshot_id', 'as_of_utc', 'symbol', 'canonical_entity_id', 'weight'], len(portfolio_rows)),
        CsvExportSpec('rebalance_latest', 'reports/rebalance_latest.csv', ['symbol', 'canonical_entity_id', 'action', 'prior_weight', 'target_weight', 'delta_weight', 'reason'], len(rebalance_rows)),
        CsvExportSpec('alerts_latest', 'reports/alerts_latest.csv', ['severity', 'alert_type', 'message'], len(alert_rows)),
        CsvExportSpec('operating_status_latest', 'reports/operating_status_latest.csv', ['run_id', 'generated_at_utc', 'operating_status', 'health_status', 'scheduler_status', 'degraded_reasons'], len(operating_rows)),
    ]

    summary_sections = [
        'Executive Summary',
        'Dashboard Snapshot',
        'Daily Review Summary',
        'Operating Status / Health',
        'Portfolio & Rebalance',
        'Alerts',
        'Operator Verdict / Signoff',
        'Export Metadata',
    ]
    summary_text = '\n'.join([
        '# Daily Market Intelligence Summary',
        '',
        '## Executive Summary',
        f"- Run ID: `{bundle.run_id}`",
        f"- Mode: `{mode}`",
        f"- Operator-ready: `{consolidated.get('operator_ready')}`",
        '',
        '## Dashboard Snapshot',
        f"- Status bucket: `{dashboard.get('status_bucket')}`",
        f"- Decision quality score: `{dashboard.get('decision_quality_summary', {}).get('score')}`",
        f"- Benchmark excess return: `{dashboard.get('benchmark_summary', {}).get('excess_return')}`",
        '',
        '## Daily Review Summary',
        f"- System state: `{daily_review.get('system_state')}`",
        f"- Human summary: {daily_review.get('human_summary')}",
        '',
        '## Operating Status / Health',
        f"- Operating status: `{operating.get('operating_status')}`",
        f"- Scheduler status: `{operating.get('scheduler_status')}`",
        '',
        '## Portfolio & Rebalance',
        f"- Position count: `{len(portfolio.get('positions', []))}`",
        f"- Rebalance actions: `{len(rebalance)}`",
        '',
        '## Alerts',
        f"- Alert count: `{len(alerts)}`",
        f"- Critical alerts: `{sum(1 for row in alerts if row.get('severity') == 'critical')}`",
        '',
        '## Operator Verdict / Signoff',
        f"- Verdict: `{(verdict or {}).get('verdict_status', 'not_available')}`",
        f"- Signoff recommendation: `{(signoff or {}).get('recommendation', 'not_available')}`",
        '',
        '## Export Metadata',
        f"- Export timestamp UTC: `{metadata.export_timestamp_utc}`",
        f"- Source manifest: `{metadata.source_manifest_reference}`",
        f"- Export version: `{metadata.export_version}`",
    ])

    return bundle, csv_specs, MarkdownSummary(
        output_path='reports/daily_summary.md',
        content=summary_text,
        sections=summary_sections,
    )


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, '') for header in headers})


def write_daily_exports(*, root: Path, bundle: DailyExportBundle, markdown: MarkdownSummary) -> list[str]:
    reports_dir = root / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    daily_export_path = reports_dir / 'daily_export_latest.json'
    metadata_path = reports_dir / 'export_metadata.json'
    summary_path = reports_dir / 'daily_summary.md'

    daily_export_path.write_text(json.dumps(asdict(bundle), indent=2), encoding='utf-8')
    metadata_path.write_text(json.dumps(asdict(bundle.export_metadata), indent=2), encoding='utf-8')
    summary_path.write_text(markdown.content.strip() + '\n', encoding='utf-8')

    dashboard = bundle.dashboard_snapshot
    portfolio = bundle.portfolio_latest
    rebalance = bundle.rebalance_latest
    alerts = bundle.alerts_latest
    operating = bundle.operating_status_summary

    _write_csv(
        reports_dir / 'candidates_latest.csv',
        ['symbol', 'final_score', 'trust_score', 'reason'],
        [
            {
                'symbol': str(row.get('symbol', '')),
                'final_score': row.get('final_score', ''),
                'trust_score': row.get('trust_score', ''),
                'reason': str(row.get('reason', '')),
            }
            for row in dashboard.get('top_candidates', [])
            if isinstance(row, dict)
        ],
    )
    _write_csv(
        reports_dir / 'portfolio_latest.csv',
        ['snapshot_id', 'as_of_utc', 'symbol', 'canonical_entity_id', 'weight'],
        [
            {
                'snapshot_id': str(portfolio.get('snapshot_id', '')),
                'as_of_utc': str(portfolio.get('as_of_utc', '')),
                'symbol': str(row.get('symbol', '')),
                'canonical_entity_id': str(row.get('canonical_entity_id', '')),
                'weight': row.get('weight', ''),
            }
            for row in portfolio.get('positions', [])
            if isinstance(row, dict)
        ],
    )
    _write_csv(
        reports_dir / 'rebalance_latest.csv',
        ['symbol', 'canonical_entity_id', 'action', 'prior_weight', 'target_weight', 'delta_weight', 'reason'],
        [
            {
                'symbol': str(row.get('symbol', '')),
                'canonical_entity_id': str(row.get('canonical_entity_id', '')),
                'action': str(row.get('action', '')),
                'prior_weight': row.get('prior_weight', ''),
                'target_weight': row.get('target_weight', ''),
                'delta_weight': row.get('delta_weight', ''),
                'reason': str(row.get('reason', '')),
            }
            for row in rebalance
            if isinstance(row, dict)
        ],
    )
    _write_csv(
        reports_dir / 'alerts_latest.csv',
        ['severity', 'alert_type', 'message'],
        [
            {
                'severity': str(row.get('severity', '')),
                'alert_type': str(row.get('alert_type', '')),
                'message': str(row.get('message', '')),
            }
            for row in alerts
            if isinstance(row, dict)
        ],
    )
    _write_csv(
        reports_dir / 'operating_status_latest.csv',
        ['run_id', 'generated_at_utc', 'operating_status', 'health_status', 'scheduler_status', 'degraded_reasons'],
        [{
            'run_id': str(operating.get('run_id', '')),
            'generated_at_utc': str(operating.get('generated_at_utc', '')),
            'operating_status': str(operating.get('operating_status', '')),
            'health_status': str(operating.get('health_status', '')),
            'scheduler_status': str(operating.get('scheduler_status', '')),
            'degraded_reasons': '|'.join(str(v) for v in operating.get('degraded_reasons', [])),
        }],
    )

    return [
        'reports/daily_export_latest.json',
        'reports/daily_summary.md',
        'reports/candidates_latest.csv',
        'reports/portfolio_latest.csv',
        'reports/rebalance_latest.csv',
        'reports/alerts_latest.csv',
        'reports/operating_status_latest.csv',
        'reports/export_metadata.json',
    ]
