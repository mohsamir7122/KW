# Architecture Hardening + Phase 4 Decision-Quality Layer

## Phase 2 core modules (preserved)
- `signal_engine.py`: produces bounded signal vector per tradable equity.
- `evidence_normalization.py`: resolves entities then normalizes evidence into governed records.
- `candidate_assembly.py`: produces publishable candidate and exclusion artifacts with explanations.

## New Phase 3 modules
- `historical_snapshot.py`: builds deterministic, point-in-time historical snapshots from validated quarterly + normalized evidence inputs.
- `evaluation.py`: tracks candidate outcomes and emits machine-readable evaluation metrics with explicit limitations.
- `learning.py`: emits governed learning-ready feature/outcome bundles from observed candidate outcomes.
- `source_growth.py`: emits governed observational source growth artifacts (coverage/participation/acceptance-rejection/eligibility summaries).

## New Phase 4 modules
- `phase4.py`: provides bounded calibration, benchmarking, signal usefulness scoring, and decision-quality reporting with confidence bands.

## Boundary rules
- Governance emits trust and contribution eligibility only.
- Ranking consumes validated signal + trust once (no double counting).
- Evaluation uses validated historical snapshots only (no ad hoc joins).
- Learning and source growth outputs are observational artifacts only (no direct ranking feedback in this phase).
- Phase 4 calibration is bounded and explicitly sparse-data limited; it never bypasses governance/ranking boundaries.

## End-to-end flow (`run_phase.py --sample-mode`)
1. Validate universe + quarterly inputs.
2. Normalize evidence (quarantine invalid/context entities).
3. Compute signals and governance outputs.
4. Assemble publishable candidates/exclusions/explanations/quality.
5. Build historical snapshot (`as_of_date`) and validate it.
6. Track candidate outcomes with canonical joins.
7. Generate evaluation report + quality summary.
8. Publish learning artifacts to `runtime/learning`.
9. Publish source growth report to `runtime/source_growth`.
10. Enrich `runtime/latest/run_manifest.json` with Phase 3 validations/writes.
11. Build bounded calibrated signal artifact (`raw_signal` and `calibrated_signal` separated explicitly).
12. Build auditable benchmark report versus a simple zero-return baseline.
13. Build signal usefulness report from observed outcomes.
14. Build decision-quality report with confidence bands and interpretable summary.
15. Enrich `runtime/latest/run_manifest.json` with Phase 4 validations/writes.

## Evaluation limitations (explicit by design)
- This is walk-forward scaffolding, not a full institutional backtester.
- Report includes explicit limitations when outcomes are partially or fully unavailable.
- Sample mode uses deterministic observed-outcome stubs for reproducibility.

## Runtime semantics additions
- `runtime/learning`: evaluation snapshots, candidate outcomes, and learning records only.
- `runtime/source_growth`: governed source coverage/performance observation artifacts only.
- `runtime/learning/calibrated_signals.json`: calibration metadata + raw/calibrated signal records.
- `runtime/learning/signal_usefulness_report.json`: usefulness and directional-accuracy diagnostics.
- `runtime/quality/benchmark_report.json`: benchmark comparison artifact.
- `runtime/quality/decision_quality_report.json`: decision-quality score/report.
- `runtime/latest/benchmark_latest.json` and `runtime/latest/decision_quality_latest.json`: latest snapshots for Phase 4 quality outputs.

## Remaining later-phase work
- richer multi-horizon outcome windows and event-aligned attribution.
- broader evidence classes and live source adapters.
- model training/selection pipelines built on Phase 3 learning records.
