# Kuwait Market Intelligence OS

نظام استخبارات سوق الكويت مبني بنهج **candidate-selection** وليس تنفيذ لحظي.

## Architecture Overview (Phase 4)
- `signal_engine.py`: حساب الإشارات الأساسية (trend, quality, liquidity, value, event, coverage) مع حدود واضحة وmissing-data penalty.
- `evidence_normalization.py`: تحويل الأدلة الخام إلى سجلات typed + quarantine للكيانات غير القابلة للتداول/السياقية.
- `candidate_assembly.py`: دمج universe + signals + governance + evidence وإنتاج candidates/exclusions/explanations/quality report.
- `historical_snapshot.py`: إنشاء لقطة تاريخية point-in-time من بيانات مالية وأدلة موثّقة.
- `evaluation.py`: تقييم walk-forward مبسّط لنتائج المرشحين مع metrics وحدود تقييم واضحة.
- `learning.py`: إنتاج سجلات learning-ready منظّمة من features + outcomes المرصودة.
- `source_growth.py`: تتبع نمو/تغطية المصادر ومشاركتها وقبولها/رفضها بشكل observational فقط.
- `phase4.py`: إضافة طبقة معايرة الإشارات + مقارنات benchmarks + تقرير جودة القرار + تقرير فائدة الإشارات تاريخيًا.

## ما الذي أضافته Phase 4؟
- **Raw vs Calibrated signals**: حفظ الإشارات الخام كما هي مع نسخة calibrated منفصلة (بدون overwrite صامت).
- **Benchmarking مبسّط وقابل للتدقيق**: مقارنة أداء المرشحين مقابل baselines واضحة ومحدودة.
- **Decision Quality**: إخراج score + confidence band + summaries قابلة للقراءة الآلية.
- **Signal Usefulness**: ترتيب الإشارات حسب فائدتها التاريخية مع توضيح حدود العينة.

## Runtime artifacts (Phase 4)
### Publishing + Quality
- `runtime/candidates/candidates.json`
- `runtime/quality/exclusions.json`
- `runtime/quality/explanations.json`
- `runtime/quality/quality_report.json`
- `runtime/quality/evaluation_quality_report.json`
- `runtime/quality/benchmark_report.json`
- `runtime/quality/decision_quality_report.json`

### Latest snapshots
- `runtime/latest/candidates_latest.json`
- `runtime/latest/evaluation_latest.json`
- `runtime/latest/benchmark_latest.json`
- `runtime/latest/decision_quality_latest.json`
- `runtime/latest/run_manifest.json`

### Learning scope (`runtime/learning`)
- `evaluation_snapshot.json`: لقطة تاريخية صالحة للتقييم.
- `candidate_outcomes.json`: تتبع حالة كل مرشح (published/evaluable/observed/unavailable).
- `learning_records.json`: bundles من خصائص المرشح ونتيجته الفعلية (عند توفر outcome).
- `calibrated_signals.json`: raw signals + calibrated signals + calibration metadata.
- `signal_usefulness_report.json`: فائدة الإشارات عبر التاريخ + ranking + limitations.

### Source growth scope (`runtime/source_growth`)
- `source_growth_report.json`: تتبع coverage عبر الزمن، المشاركة في الأدلة للمرشحين، counts القبول/الرفض، وeligibility summary.

## التشغيل المحلي
```bash
python scripts/bootstrap_audit.py
python scripts/smoke_test.py
python scripts/run_phase.py --sample-mode
python scripts/type_check.py
pytest -q
```

## ملاحظات Phase 3
- التقييم الحالي scaffold واقعي وخفيف، وليس backtester مؤسسي كامل.
- عند نقص البيانات، تظهر limitations بشكل structured داخل evaluation report.
- sample mode deterministic.
- live mode متاح مع fallback واضح، وقد يستخدم outcome feed محدود حسب البيئة.

## تفسير Decision Quality (Phase 4)
- `decision_quality_score` بين `0` و `1`.
- `confidence_band`: `high` أو `moderate` أو `weak`.
- `evidence_strength_summary`: قوة الأدلة الداعمة لمجموعة المرشحين.
- `signal_alignment_summary`: هل الإشارات calibrated متناسقة أم متعارضة.
- `missing_data_risk_summary`: أثر عقوبات نقص البيانات.
- `benchmark_relative_summary`: هل النتائج تدعم الثقة مقارنة بالـ benchmarks.

## فلسفة Benchmark وحدوده
- المقارنات في هذه المرحلة **observational** وليست backtesting مؤسسي كامل.
- عند نقص البيانات تظهر limitations واضحة (`insufficient_data`, `small_benchmark_sample`, ...).
- benchmark لا يغيّر ranking logic بشكل صامت.

## ما المتبقي للمراحل القادمة؟
- نوافذ تقييم أوسع (multi-horizon) وتحليل attribution أعمق.
- feature stores أغنى وتدريب/اختيار نماذج فوق مخرجات Phase 3/4.
