from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseContract:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    idempotent: bool
    failure_modes: tuple[str, ...]


PHASE_CONTRACTS: dict[str, PhaseContract] = {
    'ingest': PhaseContract(
        name='ingest',
        inputs=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        outputs=('runtime/latest/run_manifest.json',),
        reads=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        writes=('runtime/latest/run_manifest.json',),
        idempotent=True,
        failure_modes=('schema_validation_error', 'internet_fetch_unavailable'),
    ),
    'score': PhaseContract(
        name='score',
        inputs=('runtime/latest/run_manifest.json', 'runtime/quality/explanations.json'),
        outputs=('runtime/candidates/candidates.json', 'runtime/quality/quality_report.json'),
        reads=('runtime/latest/run_manifest.json', 'runtime/quality/explanations.json'),
        writes=('runtime/candidates/candidates.json', 'runtime/quality/quality_report.json'),
        idempotent=True,
        failure_modes=('missing_signal', 'missing_evidence', 'ranking_error'),
    ),
    'phase3': PhaseContract(
        name='phase3',
        inputs=(
            'runtime/candidates/candidates.json',
            'runtime/quality/explanations.json',
            'data/quarterly_history.csv',
        ),
        outputs=(
            'runtime/learning/evaluation_snapshot.json',
            'runtime/learning/candidate_outcomes.json',
            'runtime/learning/learning_records.json',
            'runtime/learning/calibrated_signals.json',
            'runtime/learning/signal_usefulness_report.json',
            'runtime/source_growth/source_growth_report.json',
            'runtime/quality/evaluation_quality_report.json',
            'runtime/quality/benchmark_report.json',
            'runtime/quality/decision_quality_report.json',
            'runtime/latest/evaluation_latest.json',
            'runtime/latest/benchmark_latest.json',
            'runtime/latest/decision_quality_latest.json',
        ),
        reads=(
            'runtime/candidates/candidates.json',
            'runtime/quality/explanations.json',
            'data/quarterly_history.csv',
            'runtime/latest/run_manifest.json',
        ),
        writes=(
            'runtime/learning/evaluation_snapshot.json',
            'runtime/learning/candidate_outcomes.json',
            'runtime/learning/learning_records.json',
            'runtime/learning/calibrated_signals.json',
            'runtime/learning/signal_usefulness_report.json',
            'runtime/source_growth/source_growth_report.json',
            'runtime/quality/evaluation_quality_report.json',
            'runtime/quality/benchmark_report.json',
            'runtime/quality/decision_quality_report.json',
            'runtime/latest/evaluation_latest.json',
            'runtime/latest/benchmark_latest.json',
            'runtime/latest/decision_quality_latest.json',
            'runtime/latest/run_manifest.json',
        ),
        idempotent=True,
        failure_modes=(
            'invalid_historical_snapshot',
            'invalid_entity_join',
            'missing_outcome_context',
            'evaluation_validation_error',
        ),
    ),
    'all': PhaseContract(
        name='all',
        inputs=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        outputs=(
            'runtime/candidates/candidates.json',
            'runtime/quality/exclusions.json',
            'runtime/quality/explanations.json',
            'runtime/quality/quality_report.json',
            'runtime/learning/evaluation_snapshot.json',
            'runtime/learning/candidate_outcomes.json',
            'runtime/learning/learning_records.json',
            'runtime/learning/calibrated_signals.json',
            'runtime/learning/signal_usefulness_report.json',
            'runtime/source_growth/source_growth_report.json',
            'runtime/quality/evaluation_quality_report.json',
            'runtime/quality/benchmark_report.json',
            'runtime/quality/decision_quality_report.json',
            'runtime/latest/evaluation_latest.json',
            'runtime/latest/benchmark_latest.json',
            'runtime/latest/decision_quality_latest.json',
            'runtime/latest/candidates_latest.json',
            'runtime/latest/run_manifest.json',
        ),
        reads=('config/kuwait_equities_master.csv', 'data/quarterly_history.csv'),
        writes=(
            'runtime/candidates/candidates.json',
            'runtime/quality/exclusions.json',
            'runtime/quality/explanations.json',
            'runtime/quality/quality_report.json',
            'runtime/learning/evaluation_snapshot.json',
            'runtime/learning/candidate_outcomes.json',
            'runtime/learning/learning_records.json',
            'runtime/learning/calibrated_signals.json',
            'runtime/learning/signal_usefulness_report.json',
            'runtime/source_growth/source_growth_report.json',
            'runtime/quality/evaluation_quality_report.json',
            'runtime/quality/benchmark_report.json',
            'runtime/quality/decision_quality_report.json',
            'runtime/latest/evaluation_latest.json',
            'runtime/latest/benchmark_latest.json',
            'runtime/latest/decision_quality_latest.json',
            'runtime/latest/candidates_latest.json',
            'runtime/latest/run_manifest.json',
        ),
        idempotent=True,
        failure_modes=(
            'schema_validation_error',
            'normalization_error',
            'ranking_error',
            'invalid_historical_snapshot',
            'invalid_entity_join',
        ),
    ),
}
