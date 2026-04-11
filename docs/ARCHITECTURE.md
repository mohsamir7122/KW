# Architecture Hardening + Phase 6 Scheduling/Monitoring Operating Loop

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

## New Phase 5 modules
- `phase5.py`: builds deterministic portfolio proposals from validated candidates + calibrated outputs, applies explicit risk controls, plans rebalance actions, and emits structured alerts.

## New Phase 6 modules
- `phase6.py`: builds scheduler-ready run records, freshness checks, health classification, failure classification, and machine-readable operating snapshots.

## Boundary rules
- Governance emits trust and contribution eligibility only.
- Ranking consumes validated signal + trust once (no double counting).
- Evaluation uses validated historical snapshots only (no ad hoc joins).
- Learning and source growth outputs are observational artifacts only (no direct ranking feedback in this phase).
- Phase 4 calibration is bounded and explicitly sparse-data limited; it never bypasses governance/ranking boundaries.
- Phase 5 portfolio construction is downstream-only: it consumes validated upstream outputs and never mutates ranking/governance semantics.
- Phase 6 is operational-only: it consumes prior artifacts and publishes operating health/scheduler state without changing ranking/governance/portfolio semantics.

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
16. Build portfolio proposal with explainable inclusion/exclusion reasons.
17. Apply explicit auditable risk controls (weights, liquidity, decision quality, tradability, turnover, cash buffer).
18. Build rebalance plan versus latest prior snapshot with canonical fail-closed joins.
19. Generate structured alerts and operational summary artifacts.
20. Enrich `runtime/latest/run_manifest.json` with Phase 5 validations/writes.
21. Build Phase 6 scheduler status (`scheduled_run`, `ad_hoc_run`, `last_successful_run`, `next_planned_run`, `run_trigger_reason`).
22. Run freshness + artifact presence checks and classify healthy/degraded/failed states.
23. Publish Phase 6 health/failure/freshness/operating artifacts and append operating run history.
24. Enrich `runtime/latest/run_manifest.json` with Phase 6 validations/writes.

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
- `runtime/latest/portfolio_latest.json`: risk-adjusted portfolio snapshot.
- `runtime/latest/rebalance_latest.json`: machine-readable rebalance actions (`add/increase/decrease/hold/remove`).
- `runtime/latest/alerts_latest.json`: latest structured alerts with severity.
- `runtime/quality/portfolio_quality_report.json`: portfolio quality score and bucket (`high/moderate/weak`).
- `runtime/quality/risk_control_report.json`: full auditable risk-control result with bindings/limitations.
- `runtime/quality/alert_report.json`: summarized alert report.
- `runtime/learning/portfolio_decision_history.json`: rolling portfolio decision history for learning/audit.
- `runtime/latest/operating_status_latest.json`: latest full operating snapshot.
- `runtime/latest/health_status_latest.json`: health status for scheduler/operator.
- `runtime/latest/scheduler_status_latest.json`: scheduler-ready status fields.
- `runtime/quality/operating_status_report.json`: explainable operating report.
- `runtime/quality/health_report.json`: explainable health report.
- `runtime/quality/failure_report.json`: typed failure/degraded conditions.
- `runtime/quality/freshness_report.json`: freshness checks for critical runtime artifacts.
- `runtime/learning/operating_run_history.json`: rolling operating run history.

## Remaining later-phase work
- richer multi-horizon outcome windows and event-aligned attribution.
- broader evidence classes and live source adapters.
- model training/selection pipelines built on Phase 3 learning records.
- live brokerage execution, cron infrastructure, and cloud deployment (intentionally out of scope for Phase 6).
