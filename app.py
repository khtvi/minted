from flask import Flask, render_template, request, url_for, session, flash, redirect, Response
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from functools import wraps
import json, os, csv, io, uuid

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "minted-dev-key-changeme")

DATA_FILE = os.path.join(BASE_DIR, "storage.json")
SKILL_CATEGORIES = [
    "Programming", "Cybersecurity", "Design", "Admin / VA",
    "Marketing", "Data", "Writing", "Other",
]
JOB_TYPES = [
    "Full-time", "Part-time", "Contract", "Freelance",
    "Internship", "Temporary", "Project-based", "Other",
]
VALID_TXN_TYPES = {"income", "expense"}


def normalize_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


class Skill:
    """
    A single skill acts like an ATM account.
    Deposit = study hours. Withdraw = deployed/used hours.
    Balance = net hours (deposited - deployed).
    Transfer = move hours to a related skill.
    """

    def __init__(self, name, category="General", skill_id=None):
        self.id = skill_id if skill_id else str(uuid.uuid4())[:8]
        self.name = name
        self.category = category
        self.hours_deposited = 0.0
        self.hours_withdrawn = 0.0
        self.log = []

    def _ts(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    @property
    def balance(self):
        return round(self.hours_deposited - self.hours_withdrawn, 2)

    def study(self, hours, note=""):
        if hours <= 0:
            return False
        self.hours_deposited += hours
        label = f"[{self._ts()}] +{hours}h studied"
        if note:
            label += f" - {note}"
        self.log.append(label)
        return True

    def deploy(self, hours, project=""):
        if hours <= 0 or hours > self.balance:
            return False
        self.hours_withdrawn += hours
        label = f"[{self._ts()}] -{hours}h deployed"
        if project:
            label += f" -> {project}"
        self.log.append(label)
        return True

    def receive_transfer(self, hours, from_skill):
        if hours <= 0:
            return False
        self.hours_deposited += hours
        self.log.append(f"[{self._ts()}] +{hours}h transferred from {from_skill}")
        return True

    def send_transfer(self, hours, to_skill):
        if hours <= 0 or hours > self.balance:
            return False
        self.hours_withdrawn += hours
        self.log.append(f"[{self._ts()}] -{hours}h transferred to {to_skill}")
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "hours_deposited": self.hours_deposited,
            "hours_withdrawn": self.hours_withdrawn,
            "log": self.log,
        }

    @staticmethod
    def from_dict(data):
        skill = Skill(data["name"], data.get("category", "General"), skill_id=data["id"])
        skill.hours_deposited = float(data.get("hours_deposited", 0))
        skill.hours_withdrawn = float(data.get("hours_withdrawn", 0))
        skill.log = data.get("log", [])
        return skill


class JobApplication:
    STATUSES = ["Sent", "Viewed", "Responded", "Interviewed", "Offer", "Rejected"]

    def __init__(self, company, role, date=None, job_id=None):
        self.id = job_id if job_id else str(uuid.uuid4())[:8]
        self.company = company
        self.role = role
        self.date_applied = date if date else datetime.now().strftime("%Y-%m-%d")
        self.status = "Sent"
        self.time_invested = 0.0
        self.cert_used = ""
        self.notes = ""
        self.platform = ""
        self.job_type = "Other"
        self.expected_amount = 0.0
        self.earned_amount = 0.0
        self.income_txn_id = ""

    def to_dict(self):
        return {
            "id": self.id,
            "company": self.company,
            "role": self.role,
            "date_applied": self.date_applied,
            "status": self.status,
            "time_invested": self.time_invested,
            "cert_used": self.cert_used,
            "notes": self.notes,
            "platform": self.platform,
            "job_type": self.job_type,
            "expected_amount": self.expected_amount,
            "earned_amount": self.earned_amount,
            "income_txn_id": self.income_txn_id,
        }

    @staticmethod
    def from_dict(data):
        date_applied = normalize_date(data.get("date_applied"))
        job = JobApplication(data["company"], data["role"], date_applied, job_id=data["id"])
        status = data.get("status", "Sent")
        job.status = status if status in JobApplication.STATUSES else "Sent"
        job.time_invested = max(float(data.get("time_invested", 0)), 0.0)
        job.cert_used = data.get("cert_used", "")
        job.notes = data.get("notes", "")
        job.platform = data.get("platform", "")
        job.job_type = data.get("job_type", "Other")
        if job.job_type not in JOB_TYPES:
            job.job_type = "Other"
        job.expected_amount = max(float(data.get("expected_amount", 0) or 0), 0.0)
        job.earned_amount = max(float(data.get("earned_amount", 0) or 0), 0.0)
        job.income_txn_id = data.get("income_txn_id", "")
        return job


class IncomeTransaction:
    def __init__(self, txn_type, amount, description, date=None, txn_id=None):
        self.id = txn_id if txn_id else str(uuid.uuid4())[:8]
        self.type = txn_type if txn_type in VALID_TXN_TYPES else "income"
        self.amount = float(amount)
        self.description = description
        self.date = normalize_date(date) if date else datetime.now().strftime("%Y-%m-%d")
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": self.amount,
            "description": self.description,
            "date": self.date,
        }

    @staticmethod
    def from_dict(data):
        return IncomeTransaction(
            data.get("type", "income"),
            float(data["amount"]),
            data["description"],
            data.get("date"),
            txn_id=data["id"],
        )


class User:
    def __init__(self, username, pin, user_id=None, is_hashed=False, email=None, name=""):
        self.id = user_id if user_id else str(uuid.uuid4())[:8]
        self.username = username
        self.email = email if email else username
        self.name = name
        self.__pin = pin if is_hashed else generate_password_hash(str(pin))
        self.skills = []
        self.jobs = []
        self.income_txns = []
        self.created_at = datetime.now().strftime("%Y-%m-%d")

    def verify_pin(self, pin):
        return check_password_hash(self.__pin, str(pin))

    def set_pin(self, pin):
        self.__pin = generate_password_hash(str(pin))

    def get_skill(self, skill_id):
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None

    def find_skill_by_name(self, name):
        for skill in self.skills:
            if skill.name.lower() == name.lower():
                return skill
        return None

    def add_skill(self, name, category):
        if self.find_skill_by_name(name):
            return None
        skill = Skill(name, category)
        self.skills.append(skill)
        return skill

    def total_study_hours(self):
        return round(sum(skill.hours_deposited for skill in self.skills), 2)

    def income_balance(self):
        total = 0
        for txn in self.income_txns:
            total += txn.amount if txn.type == "income" else -txn.amount
        return round(total, 2)

    def total_income(self):
        return round(sum(txn.amount for txn in self.income_txns if txn.type == "income"), 2)

    def total_expenses(self):
        return round(sum(txn.amount for txn in self.income_txns if txn.type == "expense"), 2)

    def get_job(self, job_id):
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def job_conversion_rate(self):
        total = len(self.jobs)
        if total == 0:
            return 0
        responded = sum(1 for job in self.jobs if job.status not in ["Sent", "Rejected"])
        return round((responded / total) * 100, 1)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "name": self.name,
            "pin": self.__pin,
            "created_at": self.created_at,
            "skills": [skill.to_dict() for skill in self.skills],
            "jobs": [job.to_dict() for job in self.jobs],
            "income_txns": [txn.to_dict() for txn in self.income_txns],
        }

    @staticmethod
    def from_dict(data):
        user = User(
            data["username"],
            data["pin"],
            user_id=data["id"],
            is_hashed=True,
            email=data.get("email"),
            name=data.get("name", ""),
        )
        user.created_at = data.get("created_at", "")
        user.skills = [Skill.from_dict(item) for item in data.get("skills", [])]
        user.jobs = [JobApplication.from_dict(item) for item in data.get("jobs", [])]
        user.income_txns = [IncomeTransaction.from_dict(item) for item in data.get("income_txns", [])]
        return user


users = []


def load_users():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if not content:
                    users = []
                    return
                data = json.loads(content)
                users = [User.from_dict(item) for item in data]
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"Error loading data: {exc}")
            users = []
    else:
        users = []


def save_users():
    temp_file = f"{DATA_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump([user.to_dict() for user in users], file, indent=2)
    os.replace(temp_file, DATA_FILE)


def find_user_by_username(username):
    if not username:
        return None
    for user in users:
        if user.username.lower() == username.lower():
            return user
    return None


def find_user_by_login(identifier):
    if not identifier:
        return None
    lowered = identifier.lower()
    for user in users:
        if user.username.lower() == lowered or user.email.lower() == lowered:
            return user
    return None


load_users()


def current_user():
    if "username" in session:
        user = find_user_by_username(session["username"])
        if user:
            return user
        session.pop("username", None)
    return None


def login_required(route):
    @wraps(route)
    def decorated(*args, **kwargs):
        if current_user() is None:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)

    return decorated


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip()
        pin = request.form["pin"].strip()
        confirm = request.form["confirm_pin"].strip()

        if not email or not pin:
            flash("Email and PIN are required.", "error")
            return redirect(url_for("register"))

        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("register"))

        if pin != confirm:
            flash("PINs do not match.", "error")
            return redirect(url_for("register"))

        if find_user_by_login(email):
            flash("Email already in use.", "error")
            return redirect(url_for("register"))

        user = User(email, pin, email=email)
        users.append(user)
        save_users()
        session["show_tour"] = True
        session["username"] = user.username
        session["display_name"] = user.name or user.username
        flash("Account created! Let's finish your profile.", "success")
        return redirect(url_for("welcome"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = request.form["login_id"].strip()
        pin = request.form["pin"].strip()
        user = find_user_by_login(login_id)

        if user and user.verify_pin(pin):
            session["username"] = user.username
            session["display_name"] = user.name or user.username
            flash(f"Welcome back, {user.name or user.username}!", "success")
            if user.username.lower() == "admin":
                return redirect(url_for("admin"))
            if not user.name:
                return redirect(url_for("welcome"))
            return redirect(url_for("dashboard"))

        flash("Invalid email/username or PIN.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome():
    user = current_user()
    if user.name:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("welcome"))
        user.name = name
        save_users()
        session["display_name"] = user.name
        flash(f"Welcome, {user.name}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("welcome.html", user=user)


@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/user", methods=["GET", "POST"])
@login_required
def user_profile():
    user = current_user()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "update_pin":
            current_pin = request.form.get("current_pin", "").strip()
            new_pin = request.form.get("new_pin", "").strip()
            confirm_pin = request.form.get("confirm_pin", "").strip()

            if not current_pin or not new_pin or not confirm_pin:
                flash("All PIN fields are required.", "error")
                return redirect(url_for("user_profile"))

            if not user.verify_pin(current_pin):
                flash("Current PIN is incorrect.", "error")
                return redirect(url_for("user_profile"))

            if new_pin != confirm_pin:
                flash("New PINs do not match.", "error")
                return redirect(url_for("user_profile"))

            user.set_pin(new_pin)
            save_users()
            flash("PIN updated successfully.", "success")
            return redirect(url_for("user_profile"))

        flash("Unknown settings action.", "error")
        return redirect(url_for("user_profile"))

    return render_template("user.html", user=user)


@app.route("/dashboard")
@login_required
def dashboard():
    show_tour = session.pop("show_tour", False)
    return render_template("dashboard.html", user=current_user(), show_tour=show_tour)


@app.route("/skills")
@login_required
def skills():
    return render_template("skills.html", user=current_user())


@app.route("/skills/add", methods=["GET", "POST"])
@login_required
def add_skill():
    user = current_user()

    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()

        if not name:
            flash("Skill name is required.", "error")
            return redirect(url_for("add_skill"))

        if category not in SKILL_CATEGORIES:
            flash("Please select a valid skill category.", "error")
            return redirect(url_for("add_skill"))

        result = user.add_skill(name, category)
        if result is None:
            flash(f"Skill '{name}' already exists.", "error")
            return redirect(url_for("add_skill"))

        save_users()
        flash(f"Skill '{name}' added to your skill bank!", "success")
        return redirect(url_for("skills"))

    return render_template("add_skill.html", categories=SKILL_CATEGORIES, user=user)


@app.route("/skills/<skill_id>", methods=["GET", "POST"])
@login_required
def skill_detail(skill_id):
    user = current_user()
    skill = user.get_skill(skill_id)

    if not skill:
        flash("Skill not found.", "error")
        return redirect(url_for("skills"))

    if request.method == "POST":
        action = request.form.get("action")
        hours = request.form.get("hours", "0")
        note = request.form.get("note", "").strip()

        try:
            hours = float(hours)
        except ValueError:
            flash("Invalid hours value.", "error")
            return redirect(url_for("skill_detail", skill_id=skill_id))

        if action == "study":
            if skill.study(hours, note):
                save_users()
                flash(f"+{hours}h deposited into {skill.name}.", "success")
            else:
                flash("Hours must be greater than 0.", "error")
        elif action == "deploy":
            if skill.deploy(hours, note):
                save_users()
                flash(f"-{hours}h deployed from {skill.name}.", "success")
            else:
                flash("Insufficient hours or invalid amount.", "error")
        else:
            flash("Invalid skill action.", "error")

        return redirect(url_for("skill_detail", skill_id=skill_id))

    return render_template("skill_detail.html", user=user, skill=skill)


@app.route("/skills/transfer", methods=["GET", "POST"])
@login_required
def transfer_skill():
    user = current_user()

    if len(user.skills) < 2:
        flash("You need at least two skills before transferring hours.", "error")
        return redirect(url_for("skills"))

    if request.method == "POST":
        from_id = request.form.get("from_skill")
        to_id = request.form.get("to_skill")
        hours = request.form.get("hours", "0")

        try:
            hours = float(hours)
        except ValueError:
            flash("Invalid hours value.", "error")
            return redirect(url_for("transfer_skill"))

        if hours <= 0:
            flash("Transfer hours must be greater than 0.", "error")
            return redirect(url_for("transfer_skill"))

        if from_id == to_id:
            flash("Cannot transfer to the same skill.", "error")
            return redirect(url_for("transfer_skill"))

        from_skill = user.get_skill(from_id)
        to_skill = user.get_skill(to_id)

        if not from_skill or not to_skill:
            flash("Skill not found.", "error")
            return redirect(url_for("transfer_skill"))

        if from_skill.send_transfer(hours, to_skill.name) and to_skill.receive_transfer(hours, from_skill.name):
            save_users()
            flash(f"Transferred {hours}h from {from_skill.name} to {to_skill.name}.", "success")
            return redirect(url_for("skills"))

        flash("Insufficient balance for transfer.", "error")
        return redirect(url_for("transfer_skill"))

    return render_template("transfer_skill.html", user=user)


@app.route("/jobs")
@login_required
def jobs():
    user = current_user()
    txn_by_id = {txn.id: txn for txn in user.income_txns}
    return render_template(
        "jobs.html",
        user=user,
        statuses=JobApplication.STATUSES,
        job_types=JOB_TYPES,
        txn_by_id=txn_by_id,
    )


@app.route("/jobs/add", methods=["GET", "POST"])
@login_required
def add_job():
    user = current_user()

    if request.method == "POST":
        company = request.form["company"].strip()
        role = request.form["role"].strip()
        date = request.form.get("date_applied", "").strip()
        platform = request.form.get("platform", "").strip()
        time_invested = request.form.get("time_invested", "0").strip()
        cert_used = request.form.get("cert_used", "").strip()
        notes = request.form.get("notes", "").strip()
        job_type = request.form.get("job_type", "").strip()
        expected_amount = request.form.get("expected_amount", "").strip()
        earned_amount = request.form.get("earned_amount", "").strip()

        if not company or not role:
            flash("Company and role are required.", "error")
            return redirect(url_for("add_job"))

        if job_type and job_type not in JOB_TYPES:
            flash("Please select a valid job type.", "error")
            return redirect(url_for("add_job"))

        normalized_date = normalize_date(date)
        if date and not normalized_date:
            flash("Date applied must be a valid date.", "error")
            return redirect(url_for("add_job"))

        try:
            time_invested = float(time_invested)
            if time_invested < 0:
                raise ValueError
        except ValueError:
            flash("Time invested must be 0 or greater.", "error")
            return redirect(url_for("add_job"))

        try:
            expected_amount = float(expected_amount) if expected_amount else 0.0
            earned_amount = float(earned_amount) if earned_amount else 0.0
            if expected_amount < 0 or earned_amount < 0:
                raise ValueError
        except ValueError:
            flash("Expected and earned amounts must be 0 or greater.", "error")
            return redirect(url_for("add_job"))

        job = JobApplication(company, role, normalized_date)
        job.platform = platform
        job.time_invested = time_invested
        job.cert_used = cert_used
        job.notes = notes
        job.job_type = job_type or "Other"
        job.expected_amount = expected_amount
        job.earned_amount = earned_amount
        user.jobs.append(job)
        save_users()
        flash(f"Application to {company} logged!", "success")
        return redirect(url_for("jobs"))

    return render_template(
        "add_job.html",
        user=user,
        today=datetime.now().strftime("%Y-%m-%d"),
        job_types=JOB_TYPES,
    )


@app.route("/jobs/<job_id>/update", methods=["POST"])
@login_required
def update_job(job_id):
    user = current_user()
    job = user.get_job(job_id)

    if not job:
        flash("Application not found.", "error")
        return redirect(url_for("jobs"))

    new_status = request.form.get("status")
    if new_status in JobApplication.STATUSES:
        job.status = new_status
        if new_status == "Offer" and not job.income_txn_id:
            amount = job.earned_amount if job.earned_amount > 0 else job.expected_amount
            if amount > 0:
                txn = IncomeTransaction(
                    "income",
                    amount,
                    f"{job.company} - {job.role}",
                    datetime.now().strftime("%Y-%m-%d"),
                )
                user.income_txns.append(txn)
                job.income_txn_id = txn.id
        save_users()
        flash(f"Status updated to '{new_status}'.", "success")
    else:
        flash("Invalid status.", "error")

    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": True}
    return redirect(url_for("jobs"))


@app.route("/jobs/<job_id>/link-income", methods=["POST"])
@login_required
def link_job_income(job_id):
    user = current_user()
    job = user.get_job(job_id)
    if not job:
        flash("Application not found.", "error")
        return redirect(url_for("jobs"))
    txn_id = request.form.get("txn_id", "").strip()
    if not txn_id:
        job.income_txn_id = ""
        save_users()
        flash("Vault link cleared.", "success")
        return redirect(url_for("jobs"))
    txn = next((txn for txn in user.income_txns if txn.id == txn_id), None)
    if not txn:
        flash("Transaction not found.", "error")
        return redirect(url_for("jobs"))
    job.income_txn_id = txn.id
    save_users()
    flash("Job linked to vault transaction.", "success")
    return redirect(url_for("jobs"))


@app.route("/jobs/<job_id>/send-income", methods=["POST"])
@login_required
def send_job_income(job_id):
    user = current_user()
    job = user.get_job(job_id)
    if not job:
        flash("Application not found.", "error")
        return redirect(url_for("jobs"))
    if job.income_txn_id:
        flash("Job already linked to a vault transaction.", "info")
        return redirect(url_for("jobs"))
    amount = job.earned_amount if job.earned_amount > 0 else job.expected_amount
    if amount <= 0:
        flash("Add an expected or earned amount before sending to vault.", "error")
        return redirect(url_for("jobs"))
    txn = IncomeTransaction(
        "income",
        amount,
        f"{job.company} - {job.role}",
        datetime.now().strftime("%Y-%m-%d"),
    )
    user.income_txns.append(txn)
    job.income_txn_id = txn.id
    save_users()
    flash("Income added to vault.", "success")
    return redirect(url_for("jobs"))


@app.route("/jobs/<job_id>/delete", methods=["POST"])
@login_required
def delete_job(job_id):
    user = current_user()
    job = user.get_job(job_id)
    if job:
        user.jobs.remove(job)
        save_users()
        flash("Application removed.", "success")
    return redirect(url_for("jobs"))


@app.route("/income")
@login_required
def income():
    user = current_user()
    job_by_txn = {job.income_txn_id: job for job in user.jobs if job.income_txn_id}
    return render_template("income.html", user=user, job_by_txn=job_by_txn)


@app.route("/income/add", methods=["GET", "POST"])
@login_required
def add_income():
    user = current_user()

    if request.method == "POST":
        txn_type = request.form.get("type", "income")
        amount = request.form.get("amount", "0").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        if txn_type not in VALID_TXN_TYPES:
            flash("Invalid transaction type.", "error")
            return redirect(url_for("add_income"))

        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("add_income"))

        normalized_date = normalize_date(date)
        if date and not normalized_date:
            flash("Date must be a valid date.", "error")
            return redirect(url_for("add_income"))

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.", "error")
            return redirect(url_for("add_income"))

        txn = IncomeTransaction(txn_type, amount, description, normalized_date)
        user.income_txns.append(txn)
        save_users()
        label = "Income" if txn_type == "income" else "Expense"
        flash(f"{label} of PHP {amount:,.2f} logged!", "success")
        return redirect(url_for("income"))

    return render_template("add_income.html", user=user, today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/income/<txn_id>/delete", methods=["POST"])
@login_required
def delete_income(txn_id):
    user = current_user()
    txn = next((item for item in user.income_txns if item.id == txn_id), None)
    if txn:
        user.income_txns.remove(txn)
        save_users()
        flash("Transaction removed.", "success")
    return redirect(url_for("income"))


@app.route("/download/csv")
@login_required
def download_csv():
    user = current_user()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== MINTED REPORT ==="])
    writer.writerow(["User", user.username])
    writer.writerow(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")])
    writer.writerow([])

    writer.writerow(["=== SKILL BANK ==="])
    writer.writerow(["Skill", "Category", "Hours Studied", "Hours Deployed", "Balance"])
    for skill in user.skills:
        writer.writerow([skill.name, skill.category, skill.hours_deposited, skill.hours_withdrawn, skill.balance])
    writer.writerow([])

    writer.writerow(["=== JOB APPLICATIONS ==="])
    writer.writerow([
        "Company", "Role", "Type", "Date Applied", "Status", "Platform",
        "Time Invested (h)", "Cert Used", "Expected Amount", "Earned Amount", "Notes",
    ])
    for job in user.jobs:
        writer.writerow([
            job.company,
            job.role,
            job.job_type,
            job.date_applied,
            job.status,
            job.platform,
            job.time_invested,
            job.cert_used,
            job.expected_amount,
            job.earned_amount,
            job.notes,
        ])
    writer.writerow([])

    writer.writerow(["=== INCOME / EXPENSES ==="])
    writer.writerow(["Date", "Type", "Amount", "Description"])
    for txn in user.income_txns:
        writer.writerow([txn.date, txn.type.capitalize(), txn.amount, txn.description])
    writer.writerow(["", "NET BALANCE", user.income_balance(), ""])

    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={user.username}_minted_report.csv"})


@app.route("/download/pdf")
@login_required
def download_pdf():
    user = current_user()
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"{user.username} - Minted Report")
    elements = []

    header_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), (0.08, 0.15, 0.30)),
        ("TEXTCOLOR", (0, 0), (-1, 0), (1, 1, 1)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, (0.8, 0.8, 0.8)),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [(0.95, 0.97, 1.0), (1, 1, 1)]),
    ])

    elements.append(Paragraph(f"Minted Report - {user.username}", styles["Title"]))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.25 * inch))

    elements.append(Paragraph("Skill Bank", styles["Heading2"]))
    skill_data = [["Skill", "Category", "Studied (h)", "Deployed (h)", "Balance"]]
    for skill in user.skills:
        skill_data.append([skill.name, skill.category, str(skill.hours_deposited), str(skill.hours_withdrawn), str(skill.balance)])
    if len(skill_data) > 1:
        table = Table(skill_data, colWidths=[1.8 * inch, 1.3 * inch, 1.1 * inch, 1.2 * inch, 1.0 * inch])
        table.setStyle(header_style)
        elements.append(table)
    else:
        elements.append(Paragraph("No skills logged yet.", styles["Normal"]))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Job Applications", styles["Heading2"]))
    job_data = [["Company", "Role", "Type", "Date", "Status", "Expected", "Earned"]]
    for job in user.jobs:
        job_data.append([
            job.company,
            job.role,
            job.job_type,
            job.date_applied,
            job.status,
            f"{job.expected_amount:,.2f}" if job.expected_amount else "-",
            f"{job.earned_amount:,.2f}" if job.earned_amount else "-",
        ])
    if len(job_data) > 1:
        table = Table(job_data, colWidths=[1.3 * inch, 1.3 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch, 1.0 * inch, 1.0 * inch])
        table.setStyle(header_style)
        elements.append(table)
    else:
        elements.append(Paragraph("No applications logged yet.", styles["Normal"]))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Freelance Vault", styles["Heading2"]))
    income_data = [["Date", "Type", "Amount (PHP)", "Description"]]
    for txn in user.income_txns:
        income_data.append([txn.date, txn.type.capitalize(), f"{txn.amount:,.2f}", txn.description])
    income_data.append(["", "NET BALANCE", f"{user.income_balance():,.2f}", ""])
    if len(income_data) > 2:
        table = Table(income_data, colWidths=[1.1 * inch, 1.0 * inch, 1.3 * inch, 3.0 * inch])
        table.setStyle(header_style)
        elements.append(table)
    else:
        elements.append(Paragraph("No transactions logged yet.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return Response(buffer.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": f"attachment;filename={user.username}_minted_report.pdf"})


@app.route("/admin")
@login_required
def admin():
    user = current_user()
    if user.username.lower() != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))
    visible_users = [item for item in users if item.username.lower() != "admin"]
    return render_template("admin.html", users=visible_users)


if __name__ == "__main__":
    app.run(debug=False)
