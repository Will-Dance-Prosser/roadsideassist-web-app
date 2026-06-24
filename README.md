# MemberMatch

MemberMatch is a simulated Master Data Management (MDM) match-and-merge portal built for the Software Engineering and DevOps Level 6 module.

It lets a fictional data stewardship team review potential duplicate member records from several mock source systems, approve or reject match candidates, and maintain a set of trusted golden records — all under role-based access control, with every decision captured in an audit log.

All records, source systems, match candidates and user accounts are fictional. No real customer, colleague, operational, or live system data is used.

## Technology Stack

- Python 3.12
- Flask 3 (application factory pattern with blueprints)
- Jinja2 templates
- Bootstrap 5.3
- SQLAlchemy + Flask-Migrate (Alembic)
- Flask-WTF (CSRF + form validation)
- Flask-Login (session-based authentication)
- SQLite for local/dev and tests, PostgreSQL on Railway
- pytest + pytest-cov (339 tests)
- pip-audit (dependency vulnerability scanning)
- GitHub Actions CI
- Gunicorn (production WSGI)

## Features

- Secure session-based login and logout with hashed passwords
- Role-based access control across three roles
- Dashboard with match-review stats, priority queue, and recent activity
- Source record CRUD with strict server-side validation and soft-delete (archive)
- Match candidate queue with approve / reject / reopen workflow
- Golden record creation, merge-into-existing, and audited deletion
- Configurable matching rules (field + method + weight) with exact / fuzzy / normalised methods
- Match scoring service with an explainable per-field breakdown
- Full audit log for every state change (admin-only view)
- Admin user management: create, edit, deactivate, reactivate
- Source-record edit lock once a record is part of an approved golden record
- Cross-resource search
- Reports view
- Custom 403 page for forbidden actions
- CSRF protection on every form

## User Roles

- **Administrator** — manages users, data sources, matching rules, audit logs, and golden record deletion
- **Data Steward** — reviews match candidates, approves/rejects/reopens decisions, edits source records
- **Data Analyst** — read-only access to source records, match candidates, golden records, and reports

## Project Structure

```
app/
  __init__.py          Application factory + blueprint registration
  commands.py          Flask CLI commands (seed-demo-users, seed-demo-mdm, reset-demo-mdm)
  extensions.py        db, migrate, login_manager, csrf
  models.py            SQLAlchemy models
  admin/               User management blueprint
  audit_log/           Audit log viewer
  auth/                Login/logout
  dashboard/           Home dashboard
  golden_records/      Golden record list, detail, delete
  match_queue/         Candidate queue, detail, approve, reject, reopen, explain
  reports/             Reporting views
  rules/               Match rule configuration
  search/              Cross-resource search
  services/            Match scoring service
  source_records/      Source record CRUD
  static/              CSS, favicon
  templates/           Jinja templates
docs/                  Acceptance criteria, data model, security plan, test strategy, user stories
migrations/            Alembic migrations
tests/                 pytest suite (339 tests)
```

## Local Development

### Prerequisites

- Python 3.12 (pinned via `.python-version`)
- Git

### Setup

```powershell
# Clone and enter the repo
git clone https://github.com/Will-Dance-Prosser/roadsideassist-web-app.git
cd roadsideassist-web-app

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy the example env file and adjust if needed (SQLite is the default)
Copy-Item .env.example .env

# Apply migrations
$env:FLASK_APP = "wsgi.py"
flask db upgrade

# Seed demo users and demo MDM data
flask seed-demo-users
flask seed-demo-mdm

# Run the app
python run.py
```

The app starts on <http://127.0.0.1:5000>.

### Demo Accounts

After running `flask seed-demo-users`, three accounts are available with the password `demo-password-123` (override via the `DEMO_USER_PASSWORD` environment variable):

| Username  | Role            |
| --------- | --------------- |
| `admin`   | administrator   |
| `steward` | data_steward    |
| `analyst` | data_analyst    |

### Resetting Demo Data

```powershell
flask reset-demo-mdm
flask seed-demo-mdm
```

## Testing

```powershell
# Run the full suite
pytest

# Verbose
pytest -v

# With coverage (writes HTML report to htmlcov/)
pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov
```

All 339 tests run against an in-memory SQLite database (`TestingConfig` in `config.py`) with CSRF disabled.

## Security Scanning

```powershell
pip-audit
```

`requirements.txt` includes explicit minimum versions for `idna`, `Mako`, and `urllib3` to pin transitive dependencies above their currently known CVEs.

## Continuous Integration

`.github/workflows/ci.yml` runs `pytest` on every push to `dev` or `main` and every pull request to `main`, using Python 3.12 on Ubuntu.

## Deployment

The app is deployed to Railway from the `main` branch.

- `Procfile` declares the web process: `gunicorn wsgi:app`
- `start.sh` runs migrations and seeders before starting Gunicorn
- `config.py` converts Railway's `postgres://` URL prefix to the SQLAlchemy-required `postgresql://`
- `.python-version` pins Python 3.12 for the Railpack builder

Required environment variables in production:

| Variable              | Purpose                                       |
| --------------------- | --------------------------------------------- |
| `SECRET_KEY`          | Flask session signing key                     |
| `DATABASE_URL`        | PostgreSQL connection string (Railway adds it)|
| `DEMO_USER_PASSWORD`  | Optional override for seeded demo passwords   |

## Documentation

Design and planning artefacts live in `docs/`:

- `acceptance-criteria.md`
- `data-model-plan.md`
- `security-plan.md`
- `test-strategy.md`
- `user-stories.md`
- `diagrams/`

## Security and Privacy Notice

This project uses fictional demonstration data only. It does not contain real customer records, personal data, colleague data, operational data, or live system data.
