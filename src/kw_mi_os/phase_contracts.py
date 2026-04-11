from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseContract:
    name: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    idempotent: bool
    failure_modes: tuple[str, ...]


PHASE_CONTRACTS: dict[str, PhaseContract] = {
    'ingest': PhaseContract(
        name='ingest',
        reads=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        writes=('runtime/latest/run_manifest.json',),
        idempotent=True,
        failure_modes=('schema_validation_error', 'internet_fetch_unavailable'),
    ),
    'score': PhaseContract(
        name='score',
        reads=('runtime/latest/run_manifest.json', 'runtime/quality/explanations.json'),
        writes=('runtime/candidates/candidates.json', 'runtime/quality/quality_report.json'),
        idempotent=True,
        failure_modes=('missing_signal', 'missing_evidence', 'ranking_error'),
    ),
    'all': PhaseContract(
        name='all',
        reads=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        writes=(
            'runtime/candidates/candidates.json',
            'runtime/quality/exclusions.json',
            'runtime/quality/explanations.json',
            'runtime/quality/quality_report.json',
            'runtime/latest/candidates_latest.json',
            'runtime/latest/run_manifest.json',
        ),
        idempotent=True,
        failure_modes=('schema_validation_error', 'normalization_error', 'ranking_error'),
    ),
}
