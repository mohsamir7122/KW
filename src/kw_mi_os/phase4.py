from __future__ import annotations

from dataclasses import asdict
from math import sqrt
from statistics import median

from .models import (
    BenchmarkResult,
    CalibratedSignalRecord,
    CalibrationMetadata,
    CandidateOutcomeRecord,
    DecisionQualityReport,
    SignalUsefulnessReport,
)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _wilson_band(successes: int, n: int, z: float = 1.96) -> dict[str, float]:
    if n == 0:
        return {'low': 0.0, 'high': 0.0}
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = (z * sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / denom
    return {'low': round(_clamp(center - margin, 0.0, 1.0), 4), 'high': round(_clamp(center + margin, 0.0, 1.0), 4)}


def calibrate_signals(snapshot_id: str, outcomes: list[CandidateOutcomeRecord]) -> tuple[CalibrationMetadata, list[CalibratedSignalRecord]]:
    observed = [o for o in outcomes if o.realized_return is not None and o.publish_score > 0]
    calibration_ratios = [_clamp((o.realized_return / o.publish_score), -1.5, 1.5) for o in observed]
    raw_factor = median(calibration_ratios) if calibration_ratios else 1.0

    sample_size = len(observed)
    sparse = sample_size < 5
    shrinkage = min(sample_size / 5.0, 1.0)
    calibration_factor = 1.0 + (raw_factor - 1.0) * shrinkage
    calibration_factor = _clamp(calibration_factor, 0.7, 1.3)

    calibrated_records = [
        CalibratedSignalRecord(
            symbol=o.symbol,
            snapshot_id=snapshot_id,
            raw_signal=round(o.publish_score, 6),
            calibrated_signal=round(_clamp(o.publish_score * calibration_factor, 0.0, 1.0), 6),
            observed_return=o.realized_return,
            evaluable=o.evaluable,
            outcome_status=o.outcome_status,
        )
        for o in outcomes
    ]

    hit_count = sum(1 for o in observed if o.realized_return is not None and o.realized_return > 0)
    limitations: list[str] = []
    if sparse:
        limitations.append('sparse_data_calibration_shrinkage_applied')
    if not observed:
        limitations.append('no_observed_outcomes_default_identity_calibration')

    metadata = CalibrationMetadata(
        method='bounded_median_ratio_with_shrinkage',
        sample_size=len(outcomes),
        effective_sample_size=sample_size,
        sparse_data_limited=sparse,
        calibration_factor=round(calibration_factor, 6),
        confidence_band=_wilson_band(hit_count, sample_size),
        limitations=limitations,
    )
    return metadata, calibrated_records


def build_benchmark_result(snapshot_id: str, outcomes: list[CandidateOutcomeRecord]) -> BenchmarkResult:
    observed = [o for o in outcomes if o.realized_return is not None]
    observed_returns = [o.realized_return for o in observed if o.realized_return is not None]
    candidate_mean = sum(observed_returns) / len(observed_returns) if observed_returns else 0.0

    baseline = [0.0 for _ in observed_returns]
    baseline_mean = sum(baseline) / len(baseline) if baseline else 0.0

    cand_hits = sum(1 for v in observed_returns if v > 0)
    base_hits = 0
    band = _wilson_band(cand_hits, len(observed_returns))

    limitations: list[str] = []
    if not observed_returns:
        limitations.append('benchmark_has_no_observed_returns')
    if len(observed_returns) < 5:
        limitations.append('benchmark_sparse_sample_low_statistical_power')

    return BenchmarkResult(
        snapshot_id=snapshot_id,
        candidate_return_mean=round(candidate_mean, 6),
        baseline_return_mean=round(baseline_mean, 6),
        excess_return=round(candidate_mean - baseline_mean, 6),
        candidate_hit_rate=round(cand_hits / len(observed_returns), 6) if observed_returns else None,
        baseline_hit_rate=round(base_hits / len(observed_returns), 6) if observed_returns else None,
        confidence_band=band,
        summary='Candidate observed-return mean compared to zero-return auditable baseline.',
        limitations=limitations,
    )


def build_signal_usefulness_report(
    snapshot_id: str,
    calibrated_records: list[CalibratedSignalRecord],
) -> SignalUsefulnessReport:
    observed = [r for r in calibrated_records if r.observed_return is not None]

    raw_acc = None
    cal_acc = None
    if observed:
        raw_hits = sum(1 for r in observed if (r.raw_signal >= 0.5) == (r.observed_return > 0))
        cal_hits = sum(1 for r in observed if (r.calibrated_signal >= 0.5) == (r.observed_return > 0))
        raw_acc = raw_hits / len(observed)
        cal_acc = cal_hits / len(observed)

    usefulness = cal_acc if cal_acc is not None else 0.0
    lift = (cal_acc - raw_acc) if (cal_acc is not None and raw_acc is not None) else 0.0

    limitations: list[str] = []
    if len(observed) < 5:
        limitations.append('signal_usefulness_sparse_sample')

    return SignalUsefulnessReport(
        snapshot_id=snapshot_id,
        sample_size=len(observed),
        usefulness_score=round(usefulness, 6),
        directional_accuracy_raw=round(raw_acc, 6) if raw_acc is not None else None,
        directional_accuracy_calibrated=round(cal_acc, 6) if cal_acc is not None else None,
        calibration_lift=round(lift, 6),
        per_signal_summary={
            'publish_score': {
                'observations': float(len(observed)),
                'directional_accuracy_raw': float(round(raw_acc or 0.0, 6)),
                'directional_accuracy_calibrated': float(round(cal_acc or 0.0, 6)),
            }
        },
        limitations=limitations,
    )


def build_decision_quality_report(
    snapshot_id: str,
    benchmark: BenchmarkResult,
    usefulness: SignalUsefulnessReport,
    calibration: CalibrationMetadata,
) -> DecisionQualityReport:
    benchmark_component = _clamp((benchmark.excess_return + 0.1) / 0.2, 0.0, 1.0)
    usefulness_component = usefulness.usefulness_score
    confidence_width = calibration.confidence_band['high'] - calibration.confidence_band['low']
    confidence_component = _clamp(1.0 - confidence_width, 0.0, 1.0)

    score = round(0.45 * benchmark_component + 0.35 * usefulness_component + 0.2 * confidence_component, 6)
    limitations = list(dict.fromkeys(benchmark.limitations + usefulness.limitations + calibration.limitations))

    summary = (
        f'Decision quality={score:.3f}; excess_return={benchmark.excess_return:.4f}; '
        f'usefulness={usefulness.usefulness_score:.3f}; sparse_data={calibration.sparse_data_limited}.'
    )
    return DecisionQualityReport(
        snapshot_id=snapshot_id,
        decision_quality_score=score,
        confidence_band=calibration.confidence_band,
        benchmark_comparison={
            'candidate_return_mean': benchmark.candidate_return_mean,
            'baseline_return_mean': benchmark.baseline_return_mean,
            'excess_return': benchmark.excess_return,
        },
        signal_usefulness={
            'usefulness_score': usefulness.usefulness_score,
            'calibration_lift': usefulness.calibration_lift,
        },
        summary=summary,
        limitations=limitations,
    )


def calibrated_records_to_json(metadata: CalibrationMetadata, records: list[CalibratedSignalRecord]) -> dict[str, object]:
    return {
        'metadata': asdict(metadata),
        'records': [asdict(r) for r in records],
    }
