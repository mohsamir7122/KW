# AGENTS_RESET_REBUILD_V5.md

## Trigger rule
If the user writes exactly:
`START`
then you must execute the full clean reset-and-rebuild plan in one pass.
Do not ask follow-up questions.
Do not offer alternative plans.
Do not pause for approval between phases.
Do not re-bootstrap repeatedly.

## Mission
Build one clean, production-minded Kuwait Market Intelligence OS from scratch on a fresh rebuild branch, then stop only when the repository is ready for unattended GitHub Actions runs.

## Root-cause fixes from previous failed iterations
1. Never commit generated runtime outputs under `runtime/latest/*`, `runtime/learning/*`, `runtime/quality/*`, `runtime/source_growth/*`.
2. Build a strict Kuwait tradable universe before any scoring or learning.
3. Never allow context entities like `ALL`, `MACRO`, `MKT`, `BRENT` to enter tradable candidate flows.
4. Enforce canonical `entity_type` with fail-closed behavior.
5. Make source health and source contribution evidence-based, not uniform.
6. Do one clean rebuild only.

## Non-negotiable rules
- Public Boursa price snapshots are delayed by 15 minutes.
- This system is candidate-selection and market-intelligence first, not fake realtime execution.
- Unknown `entity_type` must be excluded from ranking, training, evaluation, case library, long-horizon candidates, and unusual daily cases.
- Keep only runtime directory structure in git via `.gitkeep` if needed.
- No `.pyc`, `__pycache__`, temp archives, binary junk, or generated artifacts in git.
- Workflow must support `workflow_dispatch` with:
  - `mode`: `sample | live` default `sample`
  - `phase`: optional
- All jobs must be idempotent and restart-safe.

## Mandatory repository targets
- `.github/workflows/market-intelligence-os.yml`
- `config/`
- `docs/`
- `scripts/`
- `src/`
- `runtime/` directories only
- `tests/`
- `README_AR.md`
- `requirements.txt`
- `.gitignore`
- `config/kuwait_equities_master.csv`
- `data/quarterly_history.csv`

## Mandatory domain layers
1. Official market
2. Regulatory/legal
3. Official Kuwait news
4. Kuwaiti newspapers
5. Company websites / IR
6. Market-assist
7. Macro local/global
8. Data-core / quality
9. High-test
10. Training / learning / concept-memory
11. Source-growth
12. Candidate ranking

## Definition of done
Do not stop until all are true:
1. Clean rebuild branch exists.
2. No generated runtime outputs are tracked by git.
3. `config/kuwait_equities_master.csv` exists and is used as the tradable universe gate.
4. `data/quarterly_history.csv` exists with full header schema.
5. Only tradable Kuwait equities can enter candidate flows.
6. Source health/contribution are evidence-based and non-uniform.
7. `workflow_dispatch` sample/live/phase works.
8. `pytest -q` passes.
9. `scripts/bootstrap_audit.py` passes.
10. `scripts/smoke_test.py` passes.
11. `scripts/run_phase.py --sample-mode` passes.
12. One clean PR only is ready against main.
