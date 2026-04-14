from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import math


HORIZONS = (1, 5, 20)


@dataclass(frozen=True)
class LearningRow:
    canonical_entity_id: str
    symbol: str
    as_of_date: str
    raw_signal: float
    calibrated_signal: float
    trust_score: float
    governance_signal: float
    decision_quality: float
    benchmark_context: float
    portfolio_weight: float
    rebalance_delta: float
    alert_count: float
    health_flag: float
    source_confidence: float
    label_return_1d: float
    label_return_5d: float
    label_return_20d: float
    label_up_1d: int
    label_up_5d: int
    label_up_20d: int


def _safe_float(v: object, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def build_learning_rows_from_history(*, decision_history: list[dict[str, object]]) -> list[LearningRow]:
    rows: list[LearningRow] = []
    for record in decision_history:
        as_of_date = str(record.get('as_of_date', ''))
        if not as_of_date:
            continue
        symbols = record.get('symbols', [])
        if not isinstance(symbols, list):
            continue
        for entry in symbols:
            if not isinstance(entry, dict):
                continue
            labels = entry.get('observed_outcomes', {})
            if not isinstance(labels, dict):
                continue
            if any(f'return_{h}d' not in labels for h in HORIZONS):
                continue
            r1 = _safe_float(labels['return_1d'])
            r5 = _safe_float(labels['return_5d'])
            r20 = _safe_float(labels['return_20d'])
            rows.append(
                LearningRow(
                    canonical_entity_id=str(entry.get('canonical_entity_id', '')),
                    symbol=str(entry.get('symbol', '')),
                    as_of_date=as_of_date,
                    raw_signal=_safe_float(entry.get('raw_signal')),
                    calibrated_signal=_safe_float(entry.get('calibrated_signal')),
                    trust_score=_safe_float(entry.get('trust_score')),
                    governance_signal=_safe_float(entry.get('governance_signal')),
                    decision_quality=_safe_float(entry.get('decision_quality')),
                    benchmark_context=_safe_float(entry.get('benchmark_context')),
                    portfolio_weight=_safe_float(entry.get('portfolio_weight')),
                    rebalance_delta=_safe_float(entry.get('rebalance_delta')),
                    alert_count=_safe_float(entry.get('alert_count')),
                    health_flag=_safe_float(entry.get('health_flag')),
                    source_confidence=_safe_float(entry.get('source_confidence')),
                    label_return_1d=r1,
                    label_return_5d=r5,
                    label_return_20d=r20,
                    label_up_1d=1 if r1 > 0 else 0,
                    label_up_5d=1 if r5 > 0 else 0,
                    label_up_20d=1 if r20 > 0 else 0,
                )
            )
    rows.sort(key=lambda r: (r.as_of_date, r.symbol))
    return rows


def build_feature_label_store(rows: list[LearningRow]) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
    feature_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    for row in rows:
        row_dict = asdict(row)
        feature_rows.append({k: v for k, v in row_dict.items() if not k.startswith('label_')})
        label_rows.append(
            {
                'canonical_entity_id': row.canonical_entity_id,
                'symbol': row.symbol,
                'as_of_date': row.as_of_date,
                'label_return_1d': row.label_return_1d,
                'label_return_5d': row.label_return_5d,
                'label_return_20d': row.label_return_20d,
                'label_up_1d': row.label_up_1d,
                'label_up_5d': row.label_up_5d,
                'label_up_20d': row.label_up_20d,
            }
        )
    feature_schema = ','.join(sorted(feature_rows[0].keys())) if feature_rows else ''
    schema_hash = hashlib.sha256(feature_schema.encode('utf-8')).hexdigest()
    return feature_rows, label_rows, schema_hash


def temporal_split(rows: list[LearningRow]) -> dict[str, list[LearningRow]]:
    ordered = sorted(rows, key=lambda r: (r.as_of_date, r.symbol))
    n = len(ordered)
    if n == 0:
        return {'train': [], 'validation': [], 'test': []}
    n_train = max(1, int(n * 0.6))
    n_validation = max(1, int(n * 0.2)) if n >= 3 else 0
    train = ordered[:n_train]
    validation = ordered[n_train:n_train + n_validation]
    test = ordered[n_train + n_validation:]
    if not test and validation:
        test = validation[-1:]
        validation = validation[:-1]
    return {'train': train, 'validation': validation, 'test': test}


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _feature_columns() -> list[str]:
    return [
        'raw_signal', 'calibrated_signal', 'trust_score', 'governance_signal',
        'decision_quality', 'benchmark_context', 'portfolio_weight', 'rebalance_delta',
        'alert_count', 'health_flag', 'source_confidence',
    ]


def train_challenger(train_rows: list[LearningRow], *, horizon_label: str = 'label_up_5d') -> dict[str, object]:
    cols = _feature_columns()
    positives = [r for r in train_rows if int(getattr(r, horizon_label)) == 1]
    negatives = [r for r in train_rows if int(getattr(r, horizon_label)) == 0]
    if len(train_rows) < 8 or not positives or not negatives:
        return {'status': 'insufficient_data', 'reason': 'need>=8 rows with both classes'}

    pri = len(positives) / len(train_rows)
    bias = math.log(pri / (1.0 - pri))
    weights: dict[str, float] = {}
    for c in cols:
        pos_mean = sum(float(getattr(r, c)) for r in positives) / len(positives)
        neg_mean = sum(float(getattr(r, c)) for r in negatives) / len(negatives)
        weights[c] = round(pos_mean - neg_mean, 6)

    return {
        'status': 'trained',
        'model_type': 'linear_logistic_baseline',
        'target': horizon_label,
        'bias': bias,
        'weights': weights,
    }


def score_rows(model: dict[str, object], rows: list[LearningRow]) -> list[float]:
    if model.get('status') != 'trained':
        return []
    bias = float(model['bias'])
    weights = {str(k): _safe_float(v) for k, v in dict(model['weights']).items()}
    probs: list[float] = []
    for row in rows:
        z = bias
        for c in _feature_columns():
            z += weights.get(c, 0.0) * _safe_float(getattr(row, c))
        probs.append(_sigmoid(z))
    return probs


def evaluate_predictions(rows: list[LearningRow], probs: list[float], *, target: str = 'label_up_5d') -> dict[str, float]:
    if not rows or not probs or len(rows) != len(probs):
        return {'coverage': 0.0, 'accuracy': 0.0, 'brier': 1.0, 'calibration_error': 1.0, 'stability_gap': 1.0, 'turnover_proxy': 1.0, 'benchmark_lift': -1.0, 'missingness_rate': 1.0}
    ys = [int(getattr(r, target)) for r in rows]
    preds = [1 if p >= 0.5 else 0 for p in probs]
    accuracy = sum(1 for y, p in zip(ys, preds) if y == p) / len(ys)
    brier = sum((p - y) ** 2 for y, p in zip(ys, probs)) / len(ys)
    calibration_error = abs((sum(probs) / len(probs)) - (sum(ys) / len(ys)))

    half = max(1, len(ys) // 2)
    acc_a = sum(1 for y, p in zip(ys[:half], preds[:half]) if y == p) / len(ys[:half])
    acc_b = sum(1 for y, p in zip(ys[half:], preds[half:]) if y == p) / len(ys[half:])
    stability_gap = abs(acc_a - acc_b)

    turnover_proxy = sum(abs(probs[i] - probs[i - 1]) for i in range(1, len(probs))) / max(1, len(probs) - 1)
    benchmark_probs = [max(0.0, min(1.0, 0.5 + (r.benchmark_context * 0.2))) for r in rows]
    benchmark_brier = sum((p - y) ** 2 for y, p in zip(ys, benchmark_probs)) / len(ys)
    benchmark_lift = benchmark_brier - brier

    missingness_hits = 0
    total_cells = len(rows) * len(_feature_columns())
    for r in rows:
        for c in _feature_columns():
            if getattr(r, c) == 0.0:
                missingness_hits += 1
    missingness_rate = missingness_hits / total_cells if total_cells else 1.0

    return {
        'coverage': 1.0,
        'accuracy': round(accuracy, 6),
        'brier': round(brier, 6),
        'calibration_error': round(calibration_error, 6),
        'stability_gap': round(stability_gap, 6),
        'turnover_proxy': round(turnover_proxy, 6),
        'benchmark_lift': round(benchmark_lift, 6),
        'missingness_rate': round(missingness_rate, 6),
    }


def evaluate_acceptance(metrics: dict[str, float]) -> dict[str, object]:
    gates = {
        'predictive_performance': metrics['accuracy'] >= 0.52 and metrics['brier'] <= 0.26,
        'calibration_quality': metrics['calibration_error'] <= 0.12,
        'stability': metrics['stability_gap'] <= 0.2,
        'turnover_proxy': metrics['turnover_proxy'] <= 0.35,
        'benchmark_relative': metrics['benchmark_lift'] >= 0.0,
        'coverage_missingness': metrics['coverage'] >= 0.9 and metrics['missingness_rate'] <= 0.35,
    }
    passed = all(gates.values())
    reasons = [f'gate_failed:{k}' for k, ok in gates.items() if not ok]
    if passed:
        reasons.append('accepted_for_manual_promotion_review_only')
    return {'accepted': passed, 'gates': gates, 'reasons': reasons}


def build_registry_record(
    *,
    model: dict[str, object],
    metrics: dict[str, float],
    acceptance: dict[str, object],
    schema_hash: str,
    train_rows: list[LearningRow],
) -> dict[str, object]:
    training_window = {
        'start': train_rows[0].as_of_date if train_rows else None,
        'end': train_rows[-1].as_of_date if train_rows else None,
        'samples': len(train_rows),
    }
    return {
        'model_version': f"challenger_{training_window['end'] or 'na'}_{len(train_rows)}",
        'role': 'challenger',
        'target_horizon': '5d',
        'training_window': training_window,
        'feature_schema_hash': schema_hash,
        'calibration_metadata': {
            'tested': True,
            'metric': 'calibration_error',
            'value': metrics.get('calibration_error', 1.0),
        },
        'evaluation_metrics': metrics,
        'acceptance_decision': acceptance,
        'promoted': False,
        'status': 'accepted_pending_manual_gate' if acceptance.get('accepted') else 'rejected',
        'reasons': list(acceptance.get('reasons', [])),
    }


def build_drift_report(*, train_rows: list[LearningRow], test_rows: list[LearningRow], metrics: dict[str, float]) -> dict[str, object]:
    if not train_rows or not test_rows:
        return {
            'status': 'insufficient_data',
            'feature_drift': {},
            'label_drift': {},
            'source_drift': {},
            'calibration_degradation': True,
            'quality_decay': True,
            'retraining_recommendation': 'reject_retraining_insufficient_coverage',
            'reasons': ['insufficient rows for drift checks'],
        }

    feature_drift: dict[str, float] = {}
    for c in _feature_columns():
        train_mean = sum(float(getattr(r, c)) for r in train_rows) / len(train_rows)
        test_mean = sum(float(getattr(r, c)) for r in test_rows) / len(test_rows)
        feature_drift[c] = round(abs(train_mean - test_mean), 6)

    train_label = sum(r.label_up_5d for r in train_rows) / len(train_rows)
    test_label = sum(r.label_up_5d for r in test_rows) / len(test_rows)
    label_drift = {'positive_rate_delta': round(abs(train_label - test_label), 6)}

    train_source = sum(r.source_confidence for r in train_rows) / len(train_rows)
    test_source = sum(r.source_confidence for r in test_rows) / len(test_rows)
    source_drift = {'source_confidence_delta': round(abs(train_source - test_source), 6)}

    feature_trigger = any(v > 0.2 for v in feature_drift.values())
    label_trigger = label_drift['positive_rate_delta'] > 0.15
    source_trigger = source_drift['source_confidence_delta'] > 0.2
    calibration_fail = metrics.get('calibration_error', 1.0) > 0.12
    quality_decay = metrics.get('accuracy', 0.0) < 0.5

    if (feature_trigger or label_trigger or source_trigger) and metrics.get('coverage', 0.0) >= 0.9:
        recommendation = 'retrain_model'
    elif calibration_fail and metrics.get('accuracy', 0.0) >= 0.5:
        recommendation = 'recalibrate_model'
    elif metrics.get('coverage', 0.0) < 0.9:
        recommendation = 'reject_retraining_insufficient_coverage'
    else:
        recommendation = 'monitor_only'

    return {
        'status': 'ok',
        'feature_drift': feature_drift,
        'label_drift': label_drift,
        'source_drift': source_drift,
        'calibration_degradation': calibration_fail,
        'quality_decay': quality_decay,
        'retraining_recommendation': recommendation,
        'reasons': [],
    }


def generate_sample_decision_history(*, periods: int = 36, start: str = '2025-01-02') -> list[dict[str, object]]:
    start_date = date.fromisoformat(start)
    history: list[dict[str, object]] = []
    symbols = ['NBK', 'ZAIN', 'AGLTY']
    for idx in range(periods):
        d = start_date + timedelta(days=7 * idx)
        entries: list[dict[str, object]] = []
        for s_idx, symbol in enumerate(symbols):
            base = 0.45 + 0.05 * ((idx + s_idx) % 5)
            trend = ((idx % 7) - 3) / 100
            r1 = round(trend + (0.01 if symbol == 'NBK' else -0.002 if symbol == 'ZAIN' else 0.004), 4)
            r5 = round(r1 * 1.8, 4)
            r20 = round(r1 * 3.2, 4)
            entries.append(
                {
                    'symbol': symbol,
                    'canonical_entity_id': f'KW:{symbol}',
                    'raw_signal': base,
                    'calibrated_signal': min(1.0, max(0.0, base * 0.97)),
                    'trust_score': 0.82 - s_idx * 0.06,
                    'governance_signal': 0.74 - s_idx * 0.05,
                    'decision_quality': 0.66 - s_idx * 0.04,
                    'benchmark_context': 0.02 - s_idx * 0.01,
                    'portfolio_weight': 0.2 - s_idx * 0.03,
                    'rebalance_delta': 0.01 if idx % 2 == 0 else -0.01,
                    'alert_count': float((idx + s_idx) % 2),
                    'health_flag': 0.0,
                    'source_confidence': 0.86 - s_idx * 0.08,
                    'observed_outcomes': {
                        'return_1d': r1,
                        'return_5d': r5,
                        'return_20d': r20,
                    },
                }
            )
        history.append({'as_of_date': d.isoformat(), 'symbols': entries})
    return history
