# Kuwait Market Intelligence OS

نظام استخبارات سوق الكويت مبني بنهج **candidate-selection** وليس تنفيذ لحظي.

## Architecture Overview (Phase 9)
- `signal_engine.py`: حساب الإشارات الأساسية (trend, quality, liquidity, value, event, coverage) مع حدود واضحة وmissing-data penalty.
- `evidence_normalization.py`: تحويل الأدلة الخام إلى سجلات typed + quarantine للكيانات غير القابلة للتداول/السياقية.
- `candidate_assembly.py`: دمج universe + signals + governance + evidence وإنتاج candidates/exclusions/explanations/quality report.
- `historical_snapshot.py`: إنشاء لقطة تاريخية point-in-time من بيانات مالية وأدلة موثّقة.
- `evaluation.py`: تقييم walk-forward مبسّط لنتائج المرشحين مع metrics وحدود تقييم واضحة.
- `learning.py`: إنتاج سجلات learning-ready منظّمة من features + outcomes المرصودة.
- `source_growth.py`: تتبع نمو/تغطية المصادر ومشاركتها وقبولها/رفضها بشكل observational فقط.
- `phase4.py`: معايرة bounded للإشارات مع فصل واضح بين raw/calibrated، مقارنة benchmark بسيطة وقابلة للتدقيق، وتقرير decision quality مع confidence bands.
- `phase5.py`: بناء محفظة من المرشحين المعتمدين، تطبيق ضوابط مخاطر قابلة للتدقيق، إنشاء خطة rebalance، وإنتاج تنبيهات تشغيلية structured.
- `phase6.py`: طبقة تشغيل scheduling-ready: سجل تشغيل run records، health monitoring، فحوصات freshness/stale data، تصنيف failures، ونشر operating status قابل للتفسير.
- `phase7.py`: طبقة dashboard/reporting للاستخدام اليومي البشري: snapshot موحّد، daily review summary، checklist منظّم بحسب severity/priority، وتقرير consolidated_latest_report.
- `phase8.py`: طبقة rollout automation لمدة 30 يوم: توليد daily rollout report، verdict آلي (`approved/caution/reject`)، sign-off recommendation، وحفظ rollout history بشكل append-safe.
- `phase9.py`: طبقة daily export: بناء bundle يومي canonical بصيغة JSON، وتصدير CSV analysis-friendly، وإنشاء ملخّص Markdown بشري من أحدث artifacts الموثّقة.

## Runtime artifacts (Phase 9)
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
- `runtime/latest/operating_status_latest.json`
- `runtime/latest/health_status_latest.json`
- `runtime/latest/scheduler_status_latest.json`
- `runtime/latest/dashboard_snapshot.json`
- `runtime/latest/daily_review_latest.json`
- `runtime/latest/consolidated_latest_report.json`
- `runtime/latest/daily_rollout_latest.json`
- `runtime/latest/operator_verdict_latest.json`
- `runtime/latest/signoff_recommendation_latest.json`

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
- `runtime/quality/operating_status_report.json`
- `runtime/quality/health_report.json`
- `runtime/quality/failure_report.json`
- `runtime/quality/freshness_report.json`
- `runtime/quality/operator_summary_report.json`
- `runtime/quality/review_checklist_report.json`
- `runtime/quality/reporting_metadata.json`
- `runtime/quality/daily_rollout_report.json`
- `runtime/quality/operator_verdict_report.json`
- `runtime/quality/rollout_metadata.json`
- `runtime/latest/benchmark_latest.json`
- `runtime/latest/decision_quality_latest.json`
- `runtime/learning/rollout_30_day_history.json`

### Daily export artifacts (`reports/`)
- `reports/daily_export_latest.json` (canonical machine-readable bundle)
- `reports/daily_summary.md` (human-readable daily narrative)
- `reports/candidates_latest.csv`
- `reports/portfolio_latest.csv`
- `reports/rebalance_latest.csv`
- `reports/alerts_latest.csv`
- `reports/operating_status_latest.csv`
- `reports/export_metadata.json` (timestamp/source manifest/mode/phase coverage/warnings/export version)

## فلسفة Phase 5 وحدودها
- **Portfolio construction** يستهلك مخرجات validated من المراحل السابقة فقط؛ لا يعيد كتابة ranking ولا governance.
- **Risk controls** صريحة وقابلة للتدقيق: max weight, active positions, liquidity, decision-quality, tradability, turnover cap, وcash buffer.
- **Rebalance semantics**: أفعال `add/increase/decrease/hold/remove` مع `delta_weight` ورفض fail-closed لأي canonical join غير صالح.
- **Alerting semantics**: تنبيهات structured مع severity (`info/warning/critical`) مبنية على التقارير والقيود الفعلية.
- **Limitations**: لا يوجد تنفيذ وسيط حي في هذه المرحلة؛ live mode يعرض fallback واضح عند نقص المدخلات التشغيلية.
- **Phase 6 semantics**: حالة التشغيل النهائية تكون explainable (`healthy/degraded/failed`) ومرفقة بأسباب degradation وتصنيف failure قابل للتدقيق.

## التشغيل المحلي
```bash
python scripts/bootstrap_audit.py
python scripts/smoke_test.py
python scripts/run_phase.py --sample-mode
python scripts/type_check.py
pytest -q
```

## Phase 11 — Learning, Validation, and Adaptive Improvement Engine
- تمت إضافة محرك تعلم منفصل يبني datasets supervision من قرارات تاريخية + outcomes مُلاحظة عبر horizons: `1d/5d/20d`.
- artifacts الجديدة تشمل:
  - `runtime/learning/feature_store_latest.json`
  - `runtime/learning/label_store_latest.json`
  - `runtime/learning/training_dataset_latest.csv`
  - `runtime/learning/validation_dataset_latest.csv`
  - `runtime/learning/test_dataset_latest.csv`
  - `runtime/learning/model_registry_latest.json`
  - `runtime/quality/model_evaluation_report.json`
  - `runtime/quality/challenger_acceptance_report.json`
  - `runtime/quality/drift_monitoring_report.json`
  - `runtime/latest/learning_decision_latest.json`
  - `runtime/latest/champion_model_status.json`
- Champion/Challenger policy: النظام يدرب **challenger فقط**، ويمنع auto-promotion بالكامل (`promoted=false` دائمًا في Phase 11).
- Acceptance gates صريحة: predictive/calibration/stability/turnover proxy/benchmark lift/coverage.
- drift-aware policy مضافة: feature drift + label drift + source drift + calibration degradation + quality decay مع قرارات `retrain` أو `recalibrate` أو `monitor/reject`.
- Fail-closed safeguards: dataset schema, temporal split integrity, leakage prevention, registry schema, acceptance consistency, drift report structure.
- إذا البيانات غير كافية للتدريب، النظام يرفض الترويج ويفشل بشكل آمن دون ادعاء نجاح.

## التشغيل المجدول (GitHub Actions)
- workflow `.github/workflows/market-intelligence-os.yml` يدعم:
  - `workflow_dispatch` للتشغيل اليدوي (sample/live + phase override حتى `phase9`).
  - `schedule` يومي عبر cron لتشغيل آلي repo-native بعد الدمج، ثم رفع artifacts من `runtime/` و`reports/`.
- في البيئات ephemeral (مثل CI) قد لا تبقى `runtime/` و`reports/` بين الجلسات؛ لذلك توجد limitation note داخل metadata ويتم رفع artifacts القابلة للتنزيل.

## تشغيل التصدير اليومي يدويًا (Phase 9)
- المسار الكامل الموصى به:
  - `python scripts/run_phase.py --sample-mode` (يشمل Phase 1→9 افتراضيًا)
- تشغيل مخصص للتصدير بعد توفر latest validated inputs:
  - `python scripts/run_phase.py --mode sample --phase phase9`
- المخرجات التحليلية الرسمية في هذه المرحلة هي: **JSON + CSV + Markdown فقط**.
- **PowerPoint خارج النطاق عمدًا في Phase 9**.

## Workflow المراجعة اليومية (Phase 8)
- شغّل `python scripts/run_phase.py --sample-mode` لإنتاج أحدث snapshots.
- ابدأ من `runtime/latest/dashboard_snapshot.json` لفهم الحالة التشغيلية والاستثمارية بسرعة.
- راجع `runtime/latest/daily_review_latest.json` لمعرفة: هل التشغيل ناجح؟ ما أهم التغييرات؟ ما الذي يجب فحصه أولاً؟
- نفّذ checklist من `runtime/quality/review_checklist_report.json` بترتيب `priority` مع مراعاة `severity`.
- اعتمد `runtime/latest/consolidated_latest_report.json` كpayload موحّد للإنسان/الآلة.
- راجع `runtime/latest/daily_rollout_latest.json` لمعرفة حالة اليوم (`healthy/degraded/failed`) وحكم التشغيل.
- راجع `runtime/latest/operator_verdict_latest.json` و`runtime/latest/signoff_recommendation_latest.json` قبل قرار الاعتماد.
- استخدم `runtime/learning/rollout_30_day_history.json` لمراقبة اتجاه الاستقرار عبر آخر 30 يوم.

## فلسفة Phase 8 وحدودها
- Phase 8 **لا** يعيد كتابة ranking أو portfolio أو monitoring أو dashboard؛ بل يستهلك مخرجات المراحل السابقة فقط.
- verdict/sign-off في هذه المرحلة توصية تشغيلية آلية قابلة للتدقيق، وليست تنفيذ تداول تلقائي.
- history window مضبوط على 30 يوم مع append-safe semantics وتحقق fail-closed ضد التناقضات.
- لا يوجد external DB أو cloud infra دائم في هذه المرحلة (خارج النطاق).

## ملاحظات ما بعد Phase 8
- المعايرة bounded ومقيّدة عند sparse data (shrinkage + limitations واضحة).
- benchmark الحالي بسيط auditable baseline (صِفر عائد) ومناسب للحوكمة.
- decision quality يقدّم score تفسيري مع confidence bands وحدود الاستخدام.
- التقييم الحالي scaffold واقعي وخفيف، وليس backtester مؤسسي كامل.
- عند نقص البيانات، تظهر limitations بشكل structured داخل evaluation report.
- sample mode deterministic.
- live mode متاح مع fallback واضح، وقد يستخدم outcome feed محدود حسب البيئة.
- scheduler sample mode deterministic لضمان reproducible status snapshots وrun history ثابتة.
- لاحقًا: UI تفاعلي خفيف فوق artifacts الحالية، تنفيذ تداول حي، تحسين optimizer متعدد القيود، وتقييم multi-horizon أوسع.
