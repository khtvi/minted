# Minted

A career capital tracker built like a bank. Fresh skills forged, tracked, and deployed. Built with Flask, following ATM-style OOP patterns.

---

## Features

- **Skill Bank** — Add skills, deposit study hours, withdraw (deploy) on projects, transfer hours between related skills
- **Job Ledger** — Log AU remote applications with status tracking, platform, certs used, time invested
- **Freelance Vault** — Track income and expenses, see net balance
- **Admin Panel** — Login as `admin` to see all users
- **Export** — Download full report as CSV or PDF (via ReportLab)

---

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # Linux / Mac
venv\Scripts\activate          # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Visit http://localhost:5000

---

## Deploy to Render (Free)

1. Push this folder to a GitHub repo
2. Go to https://render.com → New Web Service
3. Connect your repo
4. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Add environment variable: `SECRET_KEY` → any random string
   - Optional environment variable: `DB_FILE` → `/tmp/storage.db` (ephemeral)
5. Optional but recommended for persistent data:
   - Add a Render Disk and mount it at `/var/data`
   - Set `DB_FILE=/var/data/storage.db`
6. Deploy

> **Note:** Render's free tier uses ephemeral storage — `storage.db` resets on redeploy without a mounted disk.
> This app auto-uses `/var/data/storage.db` when a Render Disk is mounted at `/var/data`.

---

## Deploy to Heroku

```bash
heroku create your-app-name
heroku config:set SECRET_KEY=your-random-secret
git push heroku main
```

---

## Structure

```
minted/
├── app.py              # Main app — routes + models (Account → User, Skill, Job, Income)
├── storage.db          # SQLite database (auto-created)
├── requirements.txt
├── Procfile            # For Heroku/Render
├── static/
│   └── styles.css
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── skills.html
    ├── skill_detail.html
    ├── add_skill.html
    ├── transfer_skill.html
    ├── jobs.html
    ├── add_job.html
    ├── income.html
    ├── add_income.html
    └── admin.html
```

---

## Admin Access

Register with username `admin`. The admin view shows all registered users.

---

## ATM Pattern Mapping

| ATM App         | Minted            |
|-----------------|-------------------|
| Account         | Skill             |
| Deposit         | Study hours logged |
| Withdraw        | Hours deployed on project |
| Transfer        | Move hours between skills |
| Transaction log | Skill log         |
| Admin view      | Admin view        |
| Download CSV/PDF| Download CSV/PDF  |
