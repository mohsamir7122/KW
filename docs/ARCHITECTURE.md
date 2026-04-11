# Architecture Hardening + Phase 4 Calibration and Decision Quality Foundations

## Phase 2 core modules (preserved)
- `signal_engine.py`: produces bounded signal vector per tradable equity.
- `evidence_normalization.py`: resolves entities then normalizes evidence into governed records.
- `candidate_assembly.py`: produces publishable candidate and exclusion artifacts with explanations.

## Phase 3 modules (preserved)
- `historical_snapshot.py`: builds deterministic, point-in-time historical snapshots from validated quarterly + normalized evidence inputs.
- `evaluation.py`: tracks candidate outcomes and emits machine-readable evaluation metrics with explicit limitations.
- `learning.py`: emits governed learning-ready feature/outcome bundles from observed candidate outcomes.
- `source_growth.py`: emits governed observational source growth artifacts (coverage/participation/acceptance-rejection/eligibility summaries).

## New Phase 4 modules
- `phase4.py`: calibration, benchmark, signal usefulness, and decision-quality construction on top of evaluated historical outputs.
- `models.py` (extended): typed models for `CalibratedSignalRecord`, `CalibrationMetadata`, `BenchmarkResult`, `SignalUsefulnessReport`, `DecisionQualityReport`.
- `validation.py` (extended): fail-closed validators for calibration bounds/metadata integrity, benchmark consistency, decision-quality report structure, and signal usefulness integrity.

## Boundary rules
- Governance emits trust and contribution eligibility only.
- Ranking consumes validated signal + trust once (no double counting).
- Evaluation uses validated historical snapshots only (no ad hoc joins).
- Calibration is explicit and published as artifacts; raw signal values are preserved and never overwritten.
- Benchmark outputs are observational comparisons only and do not silently rewrite ranking scores.
- Learning/source-growth remain observational artifacts only (no direct ranking feedback in this phase).

## End-to-end flow (`run_phase.py --sample-mode`)
1. Validate universe + quarterly inputs.
2. Normalize evidence (quarantine invalid/context entities).
3. Compute signals and governance outputs.
4. Assemble publishable candidates/exclusions/explanations/quality.
5. Build historical snapshot (`as_of_date`) and validate it.
6. Track candidate outcomes with canonical joins.
7. Generate evaluation report + quality summary.
8. Publish learning artifacts to `runtime/learning`.
9. Compute calibrated signal artifacts from observed outcomes + learning records.
10. Compute benchmark results against simple auditable baselines.
11. Compute decision-quality and signal-usefulness reports.
12. Publish quality/learning/latest Phase 4 artifacts and enrich `runtime/latest/run_manifest.json`.

## Phase 4 philosophy and limitations
- Calibration is bounded (`[0,1]`) and deterministic in sample mode.
- Sparse historical data is explicitly flagged in calibration metadata and propagated into decision-quality limitations.
- Benchmarks are simple and auditable (`equal_weight`, `top_liquidity`, `high_coverage`, `raw_score_pre_calibration`) and are not institutional-grade backtests.
- Decision quality is an interpretable confidence layer, not a hidden ranking override.

## Runtime semantics additions
- `runtime/learning/calibrated_signals.json`: raw-vs-calibrated signal records + calibration metadata.
- `runtime/learning/signal_usefulness_report.json`: interpretable historical usefulness scores and ranking for supported signals.
- `runtime/quality/benchmark_report.json`: machine-readable benchmark comparisons and limitations.
- `runtime/quality/decision_quality_report.json`: machine-readable confidence/evidence/alignment/risk/benchmark summaries.
- `runtime/latest/benchmark_latest.json` and `runtime/latest/decision_quality_latest.json`: latest snapshots for downstream consumers.

## Evaluation limitations (explicit by design)
- This is walk-forward scaffolding, not a full institutional backtester.
- Report includes explicit limitations when outcomes are partially or fully unavailable.
- Sample mode uses deterministic observed-outcome stubs for reproducibility.

## Remaining later-phase work
- richer multi-horizon outcome windows and event-aligned attribution.
- broader evidence classes and live source adapters.
- model training/selection pipelines built on Phase 3/4 learning and calibration artifacts.
