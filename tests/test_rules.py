from pathlib import Path
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kw_mi_os.evidence_normalization import normalize_evidence
from kw_mi_os.governance import governance_outputs
from kw_mi_os.ingestion import FetchResult, SourceCatalogEntry, fetch_json
from kw_mi_os.models import SignalInput, SourceClass, SourceEvidenceRecord
from kw_mi_os.phase_contracts import PHASE_CONTRACTS
from kw_mi_os.ranking import rank_candidates
from kw_mi_os.signal_engine import compute_signals
from kw_mi_os.universe import load_tradable_universe
from kw_mi_os.validation import validate_manifest, validate_quarterly, validate_universe


def test_signal_computation_bounds_and_missing_penalty():
    signals = compute_signals([SignalInput('NBK', None, 0.3, 5_000_000, 15, 0.5, 0.9)])
    s = signals['NBK']
    assert 0 <= s.trend_signal <= 1
    assert 0 <= s.quality_signal <= 1
    assert s.missing_data_penalty > 0


def test_entity_resolution_rejects_context_in_normalization():
    normalized, quarantined = normalize_evidence([
        {'symbol': 'MACRO', 'source_name': 'x', 'source_type': 'macro_context_only', 'evidence_type': 'macro', 'polarity': 0, 'confidence': 0.5, 'tradable_impact': 0.3, 'timestamp': '2026-04-10T00:00:00Z'}
    ], {'NBK'})
    assert normalized == []
    assert quarantined and quarantined[0]['blocked_by'] == 'context_entity'


def test_governance_boundary_macro_no_contribution():
    outputs = governance_outputs([
        SourceEvidenceRecord(source='macro', source_class=SourceClass.macro_context_only, parser_success=1, completeness=1, freshness=1, conflict_penalty=0, impacted_tradable=True, impact=4)
    ])
    assert outputs['macro'].contribution_score == 0.0


def test_ranking_no_double_counting_of_trust():
    universe = load_tradable_universe(ROOT / 'config/kuwait_equities_master.csv')
    signals = compute_signals([SignalInput('NBK', 0.1, 0.3, 8_000_000, 12, 0.7, 0.9)])
    gov = {'NBK': governance_outputs([
        SourceEvidenceRecord(source='NBK', source_class=SourceClass.official_exchange, parser_success=1, completeness=1, freshness=1, conflict_penalty=0, impacted_tradable=True, impact=1)
    ])['NBK']}
    ranked = rank_candidates(universe, signals, gov)
    nbk = [r for r in ranked if r.symbol == 'NBK'][0]
    assert nbk.final_score == round(nbk.base_signal * nbk.trust_score, 4)


def test_phase_contracts_defined_and_idempotent():
    assert set(PHASE_CONTRACTS.keys()) == {'all', 'ingest', 'score'}
    assert all(v.idempotent for v in PHASE_CONTRACTS.values())


def test_run_phase_publishes_required_artifacts():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    required = [
        ROOT / 'runtime/candidates/candidates.json',
        ROOT / 'runtime/quality/exclusions.json',
        ROOT / 'runtime/quality/explanations.json',
        ROOT / 'runtime/quality/quality_report.json',
        ROOT / 'runtime/latest/candidates_latest.json',
        ROOT / 'runtime/latest/run_manifest.json',
    ]
    for p in required:
        assert p.exists()


def test_run_phase_manifest_enriched():
    subprocess.check_call(['python', 'scripts/run_phase.py', '--sample-mode'])
    manifest_path = ROOT / 'runtime/latest/run_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    validate_manifest(manifest)
    assert manifest['internet_fetch_status'] in {'ok', 'fallback_unavailable'}
    assert 'signal_bounds' in manifest['validations']


def test_runtime_git_tracking_policy_only_gitkeep():
    tracked = subprocess.check_output(['git', 'ls-files', 'runtime']).decode().strip().splitlines()
    assert all(p.endswith('.gitkeep') for p in tracked)


def test_reference_data_validation_passes():
    assert len(validate_universe(ROOT / 'config/kuwait_equities_master.csv')) >= 4
    assert len(validate_quarterly(ROOT / 'data/quarterly_history.csv')) >= 3


def test_negative_path_malformed_universe(tmp_path: Path):
    bad = tmp_path / 'bad.csv'
    bad.write_text('symbol,broken\nNBK,x\n', encoding='utf-8')
    with pytest.raises(ValueError):
        validate_universe(bad)


def test_ingestion_fallback_behavior(monkeypatch):
    def fake_urlopen(*args, **kwargs):  # noqa: ARG001
        raise OSError('network down')

    import kw_mi_os.ingestion as ingestion

    monkeypatch.setattr(ingestion, 'urlopen', fake_urlopen)
    result = fetch_json(SourceCatalogEntry('x', SourceClass.official_exchange, 'https://example.com'))
    assert isinstance(result, FetchResult)
    assert result.status == 'fallback_unavailable'
