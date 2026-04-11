# Kuwait Market Intelligence OS

نظام استخبارات سوق الكويت مبني بنهج **candidate-selection** وليس تنفيذ لحظي.

## Architecture Overview (Phase 2)
- `signal_engine.py`: حساب الإشارات الأساسية (trend, quality, liquidity, value, event, coverage) مع حدود واضحة وmissing-data penalty.
- `evidence_normalization.py`: تحويل الأدلة الخام إلى سجلات typed + quarantine للكيانات غير القابلة للتداول/السياقية.
- `candidate_assembly.py`: دمج universe + signals + governance + evidence وإنتاج candidates/exclusions/explanations/quality report.
- `governance.py`: ownership كامل لـ trust/contribution eligibility فقط.
- `ranking.py`: score composition deterministic وتطبيق trust مرة واحدة فقط.

## Runtime artifacts (Phase 2 publishing)
- `runtime/candidates/candidates.json`
- `runtime/quality/exclusions.json`
- `runtime/quality/explanations.json`
- `runtime/quality/quality_report.json`
- `runtime/latest/candidates_latest.json`
- `runtime/latest/run_manifest.json`

## التشغيل المحلي
```bash
python scripts/bootstrap_audit.py
python scripts/smoke_test.py
python scripts/run_phase.py --sample-mode
python scripts/type_check.py
pytest -q
```

## ملاحظات
- sample mode deterministic baseline.
- live mode متاح مع fallback واضح عند فشل online fetch.
- ما زال لاحقًا مطلوب: توسيع factor universe ورفع دقة live ingestion تدريجيًا.
