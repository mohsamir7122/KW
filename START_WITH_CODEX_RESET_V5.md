# START_WITH_CODEX_RESET_V5.md

## ما الذي أكتبه فقط داخل Codex؟
اكتب كلمة واحدة فقط:

`START`

## ماذا يجب أن يفهم Codex من كلمة START؟
يجب أن يقرأ الملفات الثلاثة التالية أولًا:
- `AGENTS_RESET_REBUILD_V5.md`
- `PROJECT_BOOTSTRAP_SPEC_AR_RESET_V5.md`
- `START_WITH_CODEX_RESET_V5.md`

ثم ينفذ فورًا الخطة الكاملة من أولها إلى آخرها، بدون أي سؤال متابعة، حتى يصل إلى:
- clean rebuild branch
- repo نظيفة
- no runtime artifacts in git
- `config/kuwait_equities_master.csv`
- `data/quarterly_history.csv`
- tradable-only ranking
- evidence-based source governance
- workflow sample/live/phase
- passing tests
- PR واحدة نظيفة جاهزة ضد `main`

## لا شيء آخر يُكتب
لا تكتب prompt طويل.
لا تشرح.
لا تفاوض.
فقط:
`START`

## الإعداد الخارجي الوحيد
إذا احتاج Codex لاحقًا push/PR من داخل shell، فذلك يعتمد على GitHub auth/connector/SSH أو token.
لكن البناء نفسه وإعداد الريبو يجب أن يكتمل تلقائيًا بمجرد START.
