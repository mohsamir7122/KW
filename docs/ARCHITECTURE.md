# Architecture Hardening + Phase 3 Historical Evaluation Foundations

## Phase 2 core modules (preserved)
- `signal_engine.py`: produces bounded signal vector per tradable equity.
- `evidence_normalization.py`: resolves entities then normalizes evidence into governed records.
- `candidate_assembly.py`: produces publishable candidate and exclusion artifacts with explanations.

## New Phase 3 modules
- `historical_snapshot.py`: builds deterministic, point-in-time historical snapshots from validated quarterly + normalized evidence inputs.
- `evaluation.py`: tracks candidate outcomes and emits machine-readable evaluation metrics with explicit limitations.
- `learning.py`: emits governed learning-ready feature/outcome bundles from observed candidate outcomes.
- `source_growth.py`: emits governed observational source growth artifacts (coverage/participation/acceptance-rejection/eligibility summaries).

## Boundary rules
- Governance emits trust and contribution eligibility only.
- Ranking consumes validated signal + trust once (no double counting).
- Evaluation uses validated historical snapshots only (no ad hoc joins).
- Learning and source growth outputs are observational artifacts only (no direct ranking feedback in this phase).

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

## Evaluation limitations (explicit by design)
- This is walk-forward scaffolding, not a full institutional backtester.
- Report includes explicit limitations when outcomes are partially or fully unavailable.
- Sample mode uses deterministic observed-outcome stubs for reproducibility.

## Runtime semantics additions
- `runtime/learning`: evaluation snapshots, candidate outcomes, and learning records only.
- `runtime/source_growth`: governed source coverage/performance observation artifacts only.

## Remaining later-phase work
- richer multi-horizon outcome windows and event-aligned attribution.
- broader evidence classes and live source adapters.
- model training/selection pipelines built on Phase 3 learning records.
