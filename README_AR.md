# Kuwait Market Intelligence OS

نظام استخبارات سوق الكويت مبني بنهج **candidate-selection** وليس تنفيذ لحظي.

## Architecture Overview (Phase 5)
- `signal_engine.py`: حساب الإشارات الأساسية (trend, quality, liquidity, value, event, coverage) مع حدود واضحة وmissing-data penalty.
- `evidence_normalization.py`: تحويل الأدلة الخام إلى سجلات typed + quarantine للكيانات غير القابلة للتداول/السياقية.
- `candidate_assembly.py`: دمج universe + signals + governance + evidence وإنتاج candidates/exclusions/explanations/quality report.
- `historical_snapshot.py`: إنشاء لقطة تاريخية point-in-time من بيانات مالية وأدلة موثّقة.
- `evaluation.py`: تقييم walk-forward مبسّط لنتائج المرشحين مع metrics وحدود تقييم واضحة.
- `learning.py`: إنتاج سجلات learning-ready منظّمة من features + outcomes المرصودة.
- `source_growth.py`: تتبع نمو/تغطية المصادر ومشاركتها وقبولها/رفضها بشكل observational فقط.
- `phase4.py`: معايرة bounded للإشارات مع فصل واضح بين raw/calibrated، مقارنة benchmark بسيطة وقابلة للتدقيق، وتقرير decision quality مع confidence bands.
- `phase5.py`: بناء محفظة من المرشحين المعتمدين، تطبيق ضوابط مخاطر قابلة للتدقيق، إنشاء خطة rebalance، وإنتاج تنبيهات تشغيلية structured.

## Runtime artifacts (Phase 5)
### Publishing + Quality
- `runtime/candidates/candidates.json`
- `runtime/quality/exclusions.json`
- `runtime/quality/explanations.json`
- `runtime/quality/quality_report.json`
- `runtime/quality/evaluation_quality_report.json`

### Latest snapshots
- `runtime/latest/candidates_latest.json`
- `runtime/latest/evaluation_latest.json`
- `runtime/latest/portfolio_latest.json`
- `runtime/latest/rebalance_latest.json`
- `runtime/latest/alerts_latest.json`
- `runtime/latest/run_manifest.json`

### Learning scope (`runtime/learning`)
- `evaluation_snapshot.json`: لقطة تاريخية صالحة للتقييم.
- `candidate_outcomes.json`: تتبع حالة كل مرشح (published/evaluable/observed/unavailable).
- `learning_records.json`: bundles من خصائص المرشح ونتيجته الفعلية (عند توفر outcome).
- `calibrated_signals.json`: metadata للمعايرة + فصل صريح بين `raw_signal` و`calibrated_signal`.
- `signal_usefulness_report.json`: قياس فائدة الإشارة من النتائج التاريخية المرصودة.
- `portfolio_decision_history.json`: سجل قرارات Phase 5 (proposal + risk + rebalance + alerts) بشكل machine-readable.

### Source growth scope (`runtime/source_growth`)
- `source_growth_report.json`: تتبع coverage عبر الزمن، المشاركة في الأدلة للمرشحين، counts القبول/الرفض، وeligibility summary.

### Quality additions (`runtime/quality` + `runtime/latest`)
- `runtime/quality/benchmark_report.json`
- `runtime/quality/decision_quality_report.json`
- `runtime/quality/portfolio_quality_report.json`
- `runtime/quality/risk_control_report.json`
- `runtime/quality/alert_report.json`
- `runtime/latest/benchmark_latest.json`
- `runtime/latest/decision_quality_latest.json`

## فلسفة Phase 5 وحدودها
- **Portfolio construction** يستهلك مخرجات validated من المراحل السابقة فقط؛ لا يعيد كتابة ranking ولا governance.
- **Risk controls** صريحة وقابلة للتدقيق: max weight, active positions, liquidity, decision-quality, tradability, turnover cap, وcash buffer.
- **Rebalance semantics**: أفعال `add/increase/decrease/hold/remove` مع `delta_weight` ورفض fail-closed لأي canonical join غير صالح.
- **Alerting semantics**: تنبيهات structured مع severity (`info/warning/critical`) مبنية على التقارير والقيود الفعلية.
- **Limitations**: لا يوجد تنفيذ وسيط حي في هذه المرحلة؛ live mode يعرض fallback واضح عند نقص المدخلات التشغيلية.

## التشغيل المحلي
```bash
python scripts/bootstrap_audit.py
python scripts/smoke_test.py
python scripts/run_phase.py --sample-mode
python scripts/type_check.py
pytest -q
```

## ملاحظات Phase 5
- المعايرة bounded ومقيّدة عند sparse data (shrinkage + limitations واضحة).
- benchmark الحالي بسيط auditable baseline (صِفر عائد) ومناسب للحوكمة.
- decision quality يقدّم score تفسيري مع confidence bands وحدود الاستخدام.
- التقييم الحالي scaffold واقعي وخفيف، وليس backtester مؤسسي كامل.
- عند نقص البيانات، تظهر limitations بشكل structured داخل evaluation report.
- sample mode deterministic.
- live mode متاح مع fallback واضح، وقد يستخدم outcome feed محدود حسب البيئة.
- لاحقًا: تنفيذ تداول حي، تحسين optimizer متعدد القيود، وتقييم multi-horizon أوسع.
