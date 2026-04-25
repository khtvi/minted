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
   - Optional environment variable: `DATA_FILE` → `/tmp/storage.json` (ephemeral)
5. Optional but recommended for persistent data:
   - Add a Render Disk and mount it at `/var/data`
   - Set `DATA_FILE=/var/data/storage.json`
6. Deploy

> **Note:** Render's free tier uses ephemeral storage — `storage.json` resets on redeploy.
> For persistent data, swap the JSON file for a free PostgreSQL DB on Render.

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
├── storage.json        # Auto-created on first run
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
