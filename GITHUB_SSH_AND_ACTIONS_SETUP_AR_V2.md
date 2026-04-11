# GITHUB_SSH_AND_ACTIONS_SETUP_AR_V2.md

# الإعداد مرة واحدة فقط

## ما الذي تحتاجه النسخة الجديدة لتعمل Live-ready؟
شيئان فقط:
1. GitHub/Codex repository authorization
2. GitHub auth محلي أو Actions secrets إذا ستستخدم push محليًا أو APIs خاصة

## SSH باختصار
SSH key لا تُشترى.
هي زوج مفاتيح مجاني:
- private key يبقى عندك فقط
- public key ترفعه على GitHub

## إنشاء SSH key محليًا
```bash
ssh-keygen -t ed25519 -C "YOUR_GITHUB_EMAIL"
```

## رفع الـ public key إلى GitHub
- GitHub
- Settings
- SSH and GPG keys
- New SSH key
- الصق محتوى `~/.ssh/id_ed25519.pub`

## اختبار الاتصال
```bash
ssh -T git@github.com
```

## تحويل الريموت إلى SSH
```bash
git remote set-url origin git@github.com:mohsamir7122/Kuwait.git
```

## Actions secrets عند الحاجة
- Repo Settings
- Secrets and variables
- Actions
- New repository secret

## المبدأ
هذا إعداد مرة واحدة فقط.
بعده:
- Codex تبني وتفتح PRs
- GitHub Actions تشغّل sample/live
- البيانات التاريخية المنظمة تعيش في repo
- runtime outputs تبقى artifacts أو ignored
