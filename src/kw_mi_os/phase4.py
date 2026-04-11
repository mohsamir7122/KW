from __future__ import annotations

from dataclasses import asdict

from .models import (
    BenchmarkResult,
    CalibratedSignalRecord,
    CalibrationMetadata,
    CandidateOutcomeRecord,
    CandidateRecord,
    DecisionQualityReport,
    EvaluationReport,
    LearningRecord,
    SignalUsefulnessReport,
)

CALIBRATABLE_SIGNALS = (
    'trend_signal',
    'quality_signal',
    'liquidity_signal',
    'value_signal',
    'event_signal',
    'coverage_confidence',
)


def build_calibration_models(
    *,
    snapshot_id: str,
    outcomes: list[CandidateOutcomeRecord],
    learning_records: list[LearningRecord],
    min_samples: int = 3,
) -> tuple[list[CalibratedSignalRecord], list[CalibrationMetadata]]:
    observed = [o for o in outcomes if o.realized_return is not None]
    observed_by_symbol = {o.symbol: o.realized_return for o in observed}

    meta_by_signal: dict[str, CalibrationMetadata] = {}
    for signal_name in CALIBRATABLE_SIGNALS:
        xs: list[float] = []
        ys: list[float] = []
        for lr in learning_records:
            if lr.symbol not in observed_by_symbol:
                continue
            if signal_name not in lr.features:
                continue
            xs.append(float(lr.features[signal_name]))
            ys.append(_bound01(0.5 + (float(observed_by_symbol[lr.symbol]) * 5.0)))

        sample_size = len(xs)
        sparse = sample_size < min_samples
        if sample_size == 0:
            slope = 1.0
            intercept = 0.0
        elif sparse:
            slope = 0.85
            intercept = 0.075
        else:
            x_mean = sum(xs) / sample_size
            y_mean = sum(ys) / sample_size
            denom = sum((x - x_mean) ** 2 for x in xs)
            if denom <= 1e-12:
                slope = 1.0
                intercept = 0.0
            else:
                slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
                intercept = y_mean - slope * x_mean

        limitations: list[str] = []
        if sparse:
            limitations.append('sparse_historical_data')
        if sample_size == 0:
            limitations.append('no_observed_outcomes_for_signal')

        meta_by_signal[signal_name] = CalibrationMetadata(
            signal_name=signal_name,
            sample_size=sample_size,
            method='linear_bounded',
            slope=round(slope, 6),
            intercept=round(intercept, 6),
            bounded_min=0.0,
            bounded_max=1.0,
            sparse_data=sparse,
            limitations=limitations,
        )

    calibrated_records: list[CalibratedSignalRecord] = []
    for lr in sorted(learning_records, key=lambda r: r.symbol):
        raw_signals = {k: _bound01(float(lr.features.get(k, 0.0))) for k in CALIBRATABLE_SIGNALS}
        calibrated_signals = {
            k: _bound01((raw_signals[k] * meta_by_signal[k].slope) + meta_by_signal[k].intercept)
            for k in CALIBRATABLE_SIGNALS
        }
        calibrated_records.append(
            CalibratedSignalRecord(
                symbol=lr.symbol,
                snapshot_id=snapshot_id,
                raw_signals=raw_signals,
                calibrated_signals=calibrated_signals,
                calibration_version='phase4_v1',
            )
        )

    metadata = [meta_by_signal[k] for k in CALIBRATABLE_SIGNALS]
    return calibrated_records, metadata


def build_signal_usefulness_report(
    *,
    snapshot_id: str,
    learning_records: list[LearningRecord],
    calibration_metadata: list[CalibrationMetadata],
) -> SignalUsefulnessReport:
    signal_usefulness: dict[str, dict[str, float | int | str | bool]] = {}
    metadata_by_signal = {m.signal_name: m for m in calibration_metadata}

    for signal in CALIBRATABLE_SIGNALS:
        xs: list[float] = []
        ys: list[float] = []
        for lr in learning_records:
            if signal not in lr.features:
                continue
            if 'realized_return' not in lr.outcome:
                continue
            xs.append(float(lr.features[signal]))
            ys.append(float(lr.outcome['realized_return']))
        corr = _correlation(xs, ys)
        usefulness_score = round(abs(corr), 6)
        sign = 'positive' if corr >= 0 else 'negative'
        sparse = metadata_by_signal[signal].sparse_data

        signal_usefulness[signal] = {
            'sample_size': len(xs),
            'correlation_to_realized_return': round(corr, 6),
            'usefulness_score': usefulness_score,
            'direction': sign,
            'sparse_data': sparse,
            'interpretation': 'informative' if usefulness_score >= 0.2 else 'weak',
        }

    ranking = sorted(CALIBRATABLE_SIGNALS, key=lambda s: float(signal_usefulness[s]['usefulness_score']), reverse=True)
    limitations = []
    if any(bool(signal_usefulness[s]['sparse_data']) for s in CALIBRATABLE_SIGNALS):
        limitations.append('signal_usefulness_partially_sparse')

    return SignalUsefulnessReport(
        snapshot_id=snapshot_id,
        signal_usefulness=signal_usefulness,
        ranking=ranking,
        limitations=limitations,
    )


def build_benchmark_results(
    *,
    candidates: list[CandidateRecord],
    outcomes: list[CandidateOutcomeRecord],
    calibrated_records: list[CalibratedSignalRecord],
) -> list[BenchmarkResult]:
    observed_map = {r.symbol: r.realized_return for r in outcomes if r.realized_return is not None}
    observed_candidates = [c for c in candidates if c.symbol in observed_map]
    candidate_avg = _average([observed_map[c.symbol] for c in observed_candidates])

    all_observed_returns = list(observed_map.values())
    top_liquidity_symbols = sorted(calibrated_records, key=lambda r: r.raw_signals['liquidity_signal'], reverse=True)[:max(1, len(calibrated_records) // 2)]
    top_liquidity_returns = [observed_map[r.symbol] for r in top_liquidity_symbols if r.symbol in observed_map]

    high_cov_symbols = [r.symbol for r in calibrated_records if r.raw_signals['coverage_confidence'] >= 0.75]
    high_cov_returns = [observed_map[s] for s in high_cov_symbols if s in observed_map]

    raw_score_symbols = [c.symbol for c in sorted(candidates, key=lambda c: c.base_signal, reverse=True)[: max(1, len(candidates) // 2)]]
    raw_score_returns = [observed_map[s] for s in raw_score_symbols if s in observed_map]

    benchmarks = {
        'equal_weight_tradable_observed': all_observed_returns,
        'top_liquidity_observed': top_liquidity_returns,
        'high_coverage_observed': high_cov_returns,
        'raw_score_pre_calibration': raw_score_returns,
    }

    results: list[BenchmarkResult] = []
    for name, returns in benchmarks.items():
        bench_avg = _average(returns)
        limitations: list[str] = []
        status = 'ok'
        if candidate_avg is None or bench_avg is None:
            status = 'insufficient_data'
            limitations.append('observed_outcomes_missing_for_comparison')
        if len(returns) < 2:
            limitations.append('small_benchmark_sample')

        delta = None if (candidate_avg is None or bench_avg is None) else round(candidate_avg - bench_avg, 6)
        results.append(
            BenchmarkResult(
                benchmark_name=name,
                candidate_average_return=round(candidate_avg, 6) if candidate_avg is not None else None,
                benchmark_average_return=round(bench_avg, 6) if bench_avg is not None else None,
                relative_return_delta=delta,
                observed_candidate_count=len(observed_candidates),
                observed_benchmark_count=len(returns),
                status=status,
                limitations=limitations,
            )
        )

    return results


def build_decision_quality_report(
    *,
    snapshot_id: str,
    candidates: list[CandidateRecord],
    explanations_by_symbol: dict[str, dict],
    calibration_metadata: list[CalibrationMetadata],
    benchmark_results: list[BenchmarkResult],
    evaluation_report: EvaluationReport,
    calibrated_records: list[CalibratedSignalRecord],
) -> DecisionQualityReport:
    candidate_count = len(candidates)
    evidence_counts = [int(explanations_by_symbol.get(c.symbol, {}).get('evidence_summary', {}).get('count', 0)) for c in candidates]
    avg_evidence = round(sum(evidence_counts) / candidate_count, 6) if candidate_count else 0.0

    penalties = [float(explanations_by_symbol.get(c.symbol, {}).get('missing_data_penalties', 0.0)) for c in candidates]
    avg_penalty = round(sum(penalties) / candidate_count, 6) if candidate_count else 0.0

    sparse_ratio = sum(1 for m in calibration_metadata if m.sparse_data) / len(calibration_metadata) if calibration_metadata else 1.0
    positive_bench = [b for b in benchmark_results if (b.relative_return_delta or 0.0) > 0]
    benchmark_support_ratio = len(positive_bench) / len(benchmark_results) if benchmark_results else 0.0

    alignments = []
    for r in calibrated_records:
        deltas = [r.calibrated_signals[s] - r.raw_signals[s] for s in CALIBRATABLE_SIGNALS]
        if not deltas:
            continue
        pos = sum(1 for d in deltas if d > 0)
        neg = sum(1 for d in deltas if d < 0)
        alignments.append(abs(pos - neg) / len(deltas))
    signal_alignment = round(sum(alignments) / len(alignments), 6) if alignments else 0.0

    quality_score = (
        0.30 * min(1.0, avg_evidence / 3.0)
        + 0.20 * (evaluation_report.hit_rate or 0.0)
        + 0.20 * benchmark_support_ratio
        + 0.15 * signal_alignment
        + 0.15 * (1.0 - min(1.0, avg_penalty / 0.2))
    )
    quality_score *= (1.0 - (0.35 * sparse_ratio))
    quality_score = round(_bound01(quality_score), 6)

    if quality_score >= 0.67:
        band = 'high'
    elif quality_score >= 0.45:
        band = 'moderate'
    else:
        band = 'weak'

    benchmark_avg_delta = [b.relative_return_delta for b in benchmark_results if b.relative_return_delta is not None]
    bench_delta = round(sum(benchmark_avg_delta) / len(benchmark_avg_delta), 6) if benchmark_avg_delta else 0.0

    limitations = list(evaluation_report.limitations)
    if sparse_ratio > 0:
        limitations.append('calibration_evidence_sparse')

    return DecisionQualityReport(
        snapshot_id=snapshot_id,
        decision_quality_score=quality_score,
        confidence_band=band,
        evidence_strength_summary={
            'candidate_count': candidate_count,
            'average_evidence_count': avg_evidence,
            'observed_outcomes': evaluation_report.observed_count,
            'assessment': 'strong' if avg_evidence >= 2 else 'limited',
        },
        signal_alignment_summary={
            'alignment_score': signal_alignment,
            'assessment': 'aligned' if signal_alignment >= 0.5 else 'conflicted',
        },
        missing_data_risk_summary={
            'average_penalty': avg_penalty,
            'assessment': 'material' if avg_penalty >= 0.08 else 'contained',
        },
        benchmark_relative_summary={
            'positive_benchmarks': len(positive_bench),
            'benchmark_count': len(benchmark_results),
            'average_relative_return_delta': bench_delta,
            'assessment': 'supportive' if bench_delta > 0 else 'not_supportive',
        },
        limitations=sorted(set(limitations)),
    )


def calibration_artifact_to_json(
    records: list[CalibratedSignalRecord],
    metadata: list[CalibrationMetadata],
) -> dict[str, object]:
    return {
        'calibration_version': 'phase4_v1',
        'records': [asdict(r) for r in records],
        'metadata': [asdict(m) for m in metadata],
    }


def benchmark_results_to_json(results: list[BenchmarkResult]) -> dict[str, object]:
    return {'benchmarks': [asdict(r) for r in results]}


def decision_quality_to_json(report: DecisionQualityReport) -> dict[str, object]:
    return asdict(report)


def signal_usefulness_to_json(report: SignalUsefulnessReport) -> dict[str, object]:
    return asdict(report)


def _bound01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _correlation(xs: list[float], ys: list[float]) -> float:
    if not xs or len(xs) != len(ys):
        return 0.0
    n = len(xs)
    if n < 2:
        return 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = sum((x - x_mean) ** 2 for x in xs)
    den_y = sum((y - y_mean) ** 2 for y in ys)
    denom = (den_x * den_y) ** 0.5
    if denom <= 1e-12:
        return 0.0
    return num / denom
