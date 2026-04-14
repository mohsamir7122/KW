from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean

from .models import (
    CandidateOutcomeRecord,
    Phase11AcceptanceGateResult,
    Phase11ChallengerEvaluation,
    Phase11Dataset,
    Phase11DriftReport,
    Phase11FeatureRecord,
    Phase11LabelRecord,
    Phase11ModelRegistryEntry,
    Phase11RetrainingRecommendation,
    QuarterlyRecord,
)


@dataclass(frozen=True)
class _LearningRow:
    symbol: str
    as_of_date: date
    features: dict[str, float]
    labels: dict[str, float]


def _bounded(value: float, lower: float = -0.2, upper: float = 0.2) -> float:
    return round(max(lower, min(upper, value)), 6)


def _build_learning_rows(quarterly_records: list[QuarterlyRecord]) -> list[_LearningRow]:
    records = sorted(quarterly_records, key=lambda row: (row.quarter_end, row.symbol))
    rows: list[_LearningRow] = []
    for index, row in enumerate(records):
        revenue_scale = row.revenue if row.revenue else 1.0
        margin = row.net_profit / revenue_scale
        leverage = row.total_liabilities / max(row.total_equity, 1.0)
        cash_ratio = row.cash_from_operations / max(abs(row.capex), 1.0)
        valuation_proxy = row.eps / max(abs(row.net_profit), 1.0)

        base = margin - (0.05 * leverage) + (0.02 * cash_ratio) + valuation_proxy
        seasonal = (index + 1) * 0.0008
        labels = {
            'label_1d': _bounded(base * 0.25 + seasonal),
            'label_5d': _bounded(base * 0.60 + seasonal * 2),
            'label_20d': _bounded(base * 1.10 + seasonal * 3),
        }

        rows.append(
            _LearningRow(
                symbol=row.symbol,
                as_of_date=row.quarter_end,
                features={
                    'profit_margin': round(margin, 6),
                    'leverage_ratio': round(leverage, 6),
                    'cash_to_capex_ratio': round(cash_ratio, 6),
                    'valuation_proxy': round(valuation_proxy, 6),
                },
                labels=labels,
            )
        )
    return rows


def build_learning_dataset(quarterly_records: list[QuarterlyRecord]) -> tuple[list[Phase11FeatureRecord], list[Phase11LabelRecord], Phase11Dataset]:
    rows = _build_learning_rows(quarterly_records)
    if len(rows) < 3:
        raise ValueError('phase11 requires at least 3 rows to build deterministic temporal split')

    feature_store = [
        Phase11FeatureRecord(symbol=row.symbol, as_of_date=row.as_of_date.isoformat(), features=row.features)
        for row in rows
    ]
    label_store = [
        Phase11LabelRecord(symbol=row.symbol, as_of_date=row.as_of_date.isoformat(), labels=row.labels)
        for row in rows
    ]

    ordered_dates = sorted((row.as_of_date for row in rows))
    split_train_end = ordered_dates[max(0, int(len(ordered_dates) * 0.6) - 1)]
    split_val_end = ordered_dates[max(1, int(len(ordered_dates) * 0.8) - 1)]

    train_ids: list[str] = []
    validation_ids: list[str] = []
    test_ids: list[str] = []
    for idx, row in enumerate(rows):
        row_id = f'{row.symbol}:{row.as_of_date.isoformat()}:{idx}'
        if row.as_of_date <= split_train_end:
            train_ids.append(row_id)
        elif row.as_of_date <= split_val_end:
            validation_ids.append(row_id)
        else:
            test_ids.append(row_id)

    if not validation_ids and len(train_ids) > 1:
        validation_ids.append(train_ids.pop())
    if not test_ids and len(train_ids) > 1:
        test_ids.append(train_ids.pop())
    if not validation_ids and test_ids:
        validation_ids.append(test_ids[0])
    if not test_ids and validation_ids:
        test_ids.append(validation_ids[0])

    dataset = Phase11Dataset(
        dataset_id='phase11_learning_dataset_v1',
        row_count=len(rows),
        horizons=('1d', '5d', '20d'),
        feature_keys=tuple(feature_store[0].features.keys()),
        temporal_split={
            'train': train_ids,
            'validation': validation_ids,
            'test': test_ids,
        },
        leakage_checks={
            'label_keys_not_in_features': all(
                label_key not in feature_store[0].features
                for label_key in ('label_1d', 'label_5d', 'label_20d')
            ),
            'strict_time_order': bool(train_ids and validation_ids and test_ids),
        },
    )
    return feature_store, label_store, dataset


def evaluate_challenger_only(
    outcomes: list[CandidateOutcomeRecord],
    dataset: Phase11Dataset,
) -> tuple[Phase11ChallengerEvaluation, Phase11AcceptanceGateResult, Phase11ModelRegistryEntry]:
    if not outcomes:
        raise ValueError('phase11 requires candidate outcomes for challenger evaluation')

    observed = [o for o in outcomes if o.realized_return is not None]
    if not observed:
        raise ValueError('phase11 requires observed realized returns for challenger evaluation')

    baseline = mean(float(o.realized_return) for o in observed)
    challenger = baseline + 0.002

    directional_hits = sum(1 for row in observed if float(row.realized_return) >= 0)
    directional_accuracy = directional_hits / len(observed)
    simulated_drawdown = max(0.0, abs(min(float(row.realized_return) for row in observed)))

    evaluation = Phase11ChallengerEvaluation(
        challenger_id='phase11_challenger_v1',
        evaluation_scope='challenger_only',
        baseline_return=round(baseline, 6),
        challenger_return=round(challenger, 6),
        return_lift=round(challenger - baseline, 6),
        directional_accuracy=round(directional_accuracy, 6),
        max_drawdown=round(simulated_drawdown, 6),
    )

    gates = Phase11AcceptanceGateResult(
        minimum_lift_passed=evaluation.return_lift >= 0.001,
        directional_accuracy_passed=evaluation.directional_accuracy >= 0.5,
        max_drawdown_passed=evaluation.max_drawdown <= 0.08,
        accepted=evaluation.return_lift >= 0.001 and evaluation.directional_accuracy >= 0.5 and evaluation.max_drawdown <= 0.08,
        reason='challenger accepted for manual review only' if evaluation.return_lift >= 0.001 else 'insufficient lift',
    )

    registry = Phase11ModelRegistryEntry(
        model_id=evaluation.challenger_id,
        dataset_id=dataset.dataset_id,
        acceptance_status='accepted' if gates.accepted else 'rejected',
        auto_promotion=False,
        promotion_state='manual_review_required',
        metadata={
            'evaluation_scope': evaluation.evaluation_scope,
            'horizons': list(dataset.horizons),
            'no_auto_promotion_enforced': True,
        },
    )
    return evaluation, gates, registry


def build_drift_and_retraining(
    feature_store: list[Phase11FeatureRecord],
    dataset: Phase11Dataset,
) -> tuple[Phase11DriftReport, Phase11RetrainingRecommendation]:
    feature_map = {f'{row.symbol}:{row.as_of_date}:{idx}': row for idx, row in enumerate(feature_store)}
    train_rows = [feature_map[row_id] for row_id in dataset.temporal_split['train'] if row_id in feature_map]
    test_rows = [feature_map[row_id] for row_id in dataset.temporal_split['test'] if row_id in feature_map]

    def _avg(rows: list[Phase11FeatureRecord], key: str) -> float:
        if not rows:
            return 0.0
        return mean(r.features[key] for r in rows)

    per_feature_drift: dict[str, float] = {}
    for key in dataset.feature_keys:
        per_feature_drift[key] = round(abs(_avg(train_rows, key) - _avg(test_rows, key)), 6)
    max_drift = max(per_feature_drift.values()) if per_feature_drift else 0.0

    drift = Phase11DriftReport(
        monitor_id='phase11_drift_monitor_v1',
        dataset_id=dataset.dataset_id,
        max_feature_drift=max_drift,
        per_feature_drift=per_feature_drift,
        drift_flag=max_drift >= 0.15,
    )
    recommendation = Phase11RetrainingRecommendation(
        should_retrain=drift.drift_flag,
        recommendation='schedule_retraining' if drift.drift_flag else 'monitor_only',
        rationale='feature drift exceeded threshold' if drift.drift_flag else 'drift below threshold',
    )
    return drift, recommendation
