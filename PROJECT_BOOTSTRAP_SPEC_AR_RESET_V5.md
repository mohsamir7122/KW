# PROJECT_BOOTSTRAP_SPEC_AR_RESET_V5.md

# المواصفة التنفيذية المختصرة النهائية

## كلمة التشغيل الوحيدة
إذا كتبت للمساعد داخل Codex كلمة واحدة فقط:
`START`
فالمطلوب أن يبدأ فورًا تنفيذ إعادة البناء الكامل من غير أسئلة متابعة ومن غير اقتراح بدائل ومن غير توقف بين المراحل.

## الهدف
بناء نسخة نظيفة قابلة للتشغيل الذاتي على GitHub Actions لسوق الكويت، مع:
- Universe كويتي رسمي قابل للتداول
- Ranking شفافة
- High-Test يومي
- Learning يومي
- Source governance مبني على evidence
- فصل كامل بين سورس الكود وبين نواتج التشغيل

## الأخطاء القديمة التي يجب منعها
- إدخال `runtime/*` في git
- عدم وجود master universe منذ البداية
- دخول `ALL/MACRO/MKT/BRENT` إلى الترشيح والتعلّم
- مساواة كل المصادر في health/contribution
- تكرار bootstrap كاملة بدل بناء واحد نظيف

## خطة التنفيذ الإلزامية
### المرحلة 1: clean reset
- أنشئ backup branch
- أنشئ rebuild branch جديدة
- امسح كل generated artifacts من التتبع
- اترك runtime directories فقط
- فعّل `.gitignore` لمنع أي نواتج تشغيل مستقبلية من الدخول في git

### المرحلة 2: universe master
أنشئ:
- `config/kuwait_equities_master.csv`

ويجب أن يحتوي على:
`symbol,arabic_name,english_name,sector,market,listing_status,entity_type,tradable_flag,sec_code,isin,source_primary,source_secondary,verified_at_utc`

ولا يبدأ أي scoring أو learning قبل هذا الملف.

### المرحلة 3: التاريخ الربع سنوي
أنشئ:
- `data/quarterly_history.csv`

ويحتوي على:
`symbol,quarter_end,fiscal_period,filing_date,revenue,operating_profit,net_profit,eps,total_assets,total_liabilities,total_equity,cash_from_operations,capex,dividend_flag,buyback_flag,material_event_flag,source_primary,source_secondary,verified_at_utc`

### المرحلة 4: قواعد الكيانات
- `entity_type` canonical
- القيم الدنيا:
  - `kuwait_listed_equity`
  - `context_macro`
  - `unknown`
- fail-closed: `unknown` لا تدخل candidate flow
- `ALL/MACRO/MKT/BRENT` تبقى supporting signals فقط

### المرحلة 5: source governance
- `source_health` يعتمد على parser success + completeness + freshness + conflict behavior
- `source_contribution` يعتمد على actual tradable-candidate impact
- official bonus صغير فقط للمصادر الرسمية
- لا قيم موحدة افتراضيًا

### المرحلة 6: workflow
- `workflow_dispatch` مع:
  - `mode = sample/live`
  - `phase` اختياري
- default = sample
- live لا يعمل إلا عند الاختيار اليدوي
- تبقى كل cron schedules كما هي

### المرحلة 7: الاختبارات
يجب إضافة وتمرير اختبارات تثبت:
- tradable-only ranking
- استبعاد context entities من scoring
- استبعاد context entities من training/evaluation
- divergence في source health
- divergence في source contribution
- idempotency للمخرجات المطلوبة

## أكثر من 40 مصدرًا
اعتمد ملف catalog منفصل كبذرة مصادر تشغيلية وتوسعية.
المصادر الأساسية تبدأ بالرسمية، ثم تتسع إلى newspapers, market-assist, KCC, KPC, EIA, Reuters, Investing, Mubasher, Argaam, Yahoo، ثم company IR discovery slots.

## ممنوعات
- لا generated runtime files في git
- لا PRs كبيرة تعيد bootstrap كاملة
- لا placeholders في candidate ranking
- لا Fake realtime language

## التسليم النهائي
بعد انتهاء التنفيذ:
- branch واحدة نظيفة
- PR واحدة فقط
- README واضح
- workflow جاهزة
- sample mode ناجح
- live-ready بعد setup مرة واحدة
