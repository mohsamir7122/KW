# Architecture Hardening + Phase 2 Signal Engine

## New Phase 2 modules
- `signal_engine.py`: produces bounded signal vector per tradable equity.
- `evidence_normalization.py`: resolves entities then normalizes evidence into governed records.
- `candidate_assembly.py`: produces publishable candidate and exclusion artifacts with explanations.

## Boundary rules
- Governance emits trust and contribution eligibility only.
- Ranking consumes validated signal + trust once (no double counting).
- Candidate assembly composes publishable outputs and quality metadata.

## Publishing flow
1. Validate universe + quarterly inputs.
2. Normalize evidence (quarantine invalid/context entities).
3. Compute signals.
4. Compute governance outputs.
5. Assemble candidates/exclusions/explanations/quality.
6. Publish runtime artifacts and manifest.

## Remaining later-phase work
- richer live market factors
- broader evidence classes
- learning/source_growth governed outputs in dedicated phases
