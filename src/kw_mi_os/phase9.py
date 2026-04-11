from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from .models import CsvExportSpec, DailyExportBundle, ExportMetadata, MarkdownSummary


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _write_csv(path: Path, rows: list[dict[str, object]]) -> CsvExportSpec:
    columns: list[str] = sorted({key for row in rows for key in row.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, '') for column in columns})
    return CsvExportSpec(
        artifact_name=path.name,
        artifact_path=str(path),
        columns=columns,
        row_count=len(rows),
    )


def _portfolio_rows(portfolio_snapshot: dict[str, object]) -> list[dict[str, object]]:
    positions = portfolio_snapshot.get('positions', [])
    if not isinstance(positions, list):
        return []
    return [dict(row) for row in positions if isinstance(row, dict)]


def build_daily_export_bundle(
    *,
    run_id: str,
    mode: str,
    candidates: list[dict[str, object]],
    portfolio_snapshot: dict[str, object],
    rebalance_actions: list[dict[str, object]],
    alerts: list[dict[str, object]],
    operating_status: dict[str, object],
    reports_dir: Path,
) -> DailyExportBundle:
    reports_dir.mkdir(parents=True, exist_ok=True)
    generated_at_utc = _iso_now()

    canonical_payload = {
        'run_id': run_id,
        'mode': mode,
        'generated_at_utc': generated_at_utc,
        'candidates': candidates,
        'portfolio_snapshot': portfolio_snapshot,
        'rebalance_actions': rebalance_actions,
        'alerts': alerts,
        'operating_status': operating_status,
    }
    canonical_json_path = reports_dir / 'daily_export_latest.json'
    canonical_json_path.write_text(json.dumps(canonical_payload, indent=2, ensure_ascii=False), encoding='utf-8')

    csv_specs = [
        _write_csv(reports_dir / 'candidates_latest.csv', candidates),
        _write_csv(reports_dir / 'portfolio_latest.csv', _portfolio_rows(portfolio_snapshot)),
        _write_csv(reports_dir / 'rebalance_latest.csv', rebalance_actions),
        _write_csv(reports_dir / 'alerts_latest.csv', alerts),
        _write_csv(reports_dir / 'operating_status_latest.csv', [operating_status]),
    ]

    summary_lines = [
        '# Kuwait Market Intelligence - Daily Summary',
        '',
        f'- Run ID: `{run_id}`',
        f'- Mode: `{mode}`',
        f'- Generated at (UTC): `{generated_at_utc}`',
        f'- Candidates: `{len(candidates)}`',
        f'- Portfolio positions: `{len(_portfolio_rows(portfolio_snapshot))}`',
        f'- Rebalance actions: `{len(rebalance_actions)}`',
        f'- Alerts: `{len(alerts)}`',
        '',
        '## Operating Status',
        f"- Status: `{operating_status.get('operating_status', 'unknown')}`",
        f"- Health: `{operating_status.get('health_status', 'unknown')}`",
        f"- Scheduler: `{operating_status.get('scheduler_status', 'unknown')}`",
    ]
    summary_path = reports_dir / 'daily_summary.md'
    summary_path.write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')
    markdown = MarkdownSummary(
        artifact_path=str(summary_path),
        title='Kuwait Market Intelligence - Daily Summary',
        sections=['run_overview', 'operating_status'],
        line_count=len(summary_lines),
    )

    metadata = ExportMetadata(
        phase='phase9',
        run_id=run_id,
        mode=mode,
        generated_at_utc=generated_at_utc,
        source_artifacts=[
            'runtime/latest/candidates_latest.json',
            'runtime/latest/portfolio_latest.json',
            'runtime/latest/rebalance_latest.json',
            'runtime/latest/alerts_latest.json',
            'runtime/latest/operating_status_latest.json',
        ],
        published_artifacts=[
            str(canonical_json_path),
            str(summary_path),
            *[spec.artifact_path for spec in csv_specs],
            str(reports_dir / 'export_metadata.json'),
        ],
        scheduler_friendly=True,
        notes=[
            'Stable latest filenames in reports/ support scheduler pickup and downstream ingestion.',
            'Exports are JSON + CSV + Markdown only (no presentation formats).',
        ],
    )
    metadata_path = reports_dir / 'export_metadata.json'
    metadata_path.write_text(json.dumps(asdict(metadata), indent=2, ensure_ascii=False), encoding='utf-8')

    return DailyExportBundle(
        run_id=run_id,
        mode=mode,
        generated_at_utc=generated_at_utc,
        canonical_json_path=str(canonical_json_path),
        csv_exports=csv_specs,
        markdown_summary=markdown,
        metadata=metadata,
    )
