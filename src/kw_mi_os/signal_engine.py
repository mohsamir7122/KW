from __future__ import annotations

from .models import SignalInput, SignalOutput


def _bound01(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 4)


def _safe(value: float | None, default: float) -> tuple[float, bool]:
    if value is None:
        return default, True
    return float(value), False


def compute_signals(inputs: list[SignalInput]) -> dict[str, SignalOutput]:
    outputs: dict[str, SignalOutput] = {}
    for row in inputs:
        miss = 0
        trend_raw, m = _safe(row.price_return_30d, 0.0); miss += int(m)
        quality_raw, m = _safe(row.profit_margin, 0.0); miss += int(m)
        liquidity_raw, m = _safe(row.avg_daily_value, 0.0); miss += int(m)
        value_raw, m = _safe(row.pe_ratio, 25.0); miss += int(m)
        event_raw, m = _safe(row.event_intensity, 0.0); miss += int(m)
        cov_raw, m = _safe(row.evidence_coverage, 0.0); miss += int(m)

        trend = _bound01(0.5 + trend_raw)
        quality = _bound01(quality_raw)
        liquidity = _bound01(liquidity_raw / 10_000_000)
        value = _bound01(1.0 - (value_raw / 40.0))
        event = _bound01(event_raw)
        coverage = _bound01(cov_raw)
        penalty = round(min(0.25, miss * 0.03), 4)

        outputs[row.symbol] = SignalOutput(
            symbol=row.symbol,
            trend_signal=trend,
            quality_signal=quality,
            liquidity_signal=liquidity,
            value_signal=value,
            event_signal=event,
            coverage_confidence=coverage,
            missing_data_penalty=penalty,
        )
    return outputs
