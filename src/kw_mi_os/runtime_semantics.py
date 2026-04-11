from __future__ import annotations

RUNTIME_SEMANTICS: dict[str, str] = {
    'runtime/candidates': 'validated candidate-level outputs for current run/phase',
    'runtime/latest': 'latest canonical snapshots and final state views',
    'runtime/quality': 'validation reports, integrity checks, exception reports, audit summaries',
    'runtime/learning': 'learning-ready structured feedback/evaluation snapshots only',
    'runtime/source_growth': 'governed source performance and coverage tracking artifacts only',
}
