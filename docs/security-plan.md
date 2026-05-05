# Security Plan — MemberMatch

## Overview

MemberMatch is a fictional coursework application. It handles no real personal data, but it is designed and implemented as if it were a production system. This is intentional — the goal is to demonstrate understanding of secure development practices as required by the OWASP Top 10.

All security controls are planned or in progress. This document maps planned controls to the risks they address.

---

## Risk and Control Mapping

### 1. Broken Access Control

**Risk:** A user accesses a page or performs an action that their role does not permit. For example, a Data Analyst approves a match candidate, or an unauthenticated user accesses the dashboard.

**Planned controls:**
- Flask-Login used to enforce authentication on all routes via `@login_required`
- A custom `role_required` decorator checks the current user's role before allowing access to sensitive routes
- Data Analyst role cannot POST to approve or reject endpoints — server returns 403
- All role checks are server-side — frontend hiding alone is not relied upon
- Access control is tested in `tests/test_access.py`

---

### 2. CSRF (Cross-Site Request Forgery)

**Risk:** A malicious site tricks an authenticated user's browser into submitting a forged form — for example, auto-approving a merge the user did not intend.

**Planned controls:**
- Flask-WTF is installed and CSRF protection is enabled globally via `CSRFProtect`
- All forms include `{{ form.hidden_tag() }}` to embed the CSRF token
- Any POST route without a valid token returns 400
- CSRF is already initialised in `app/extensions.py`

---

### 3. Injection

**Risk:** Malicious input is passed to a database query, shell command or template in a way that changes its behaviour.

**Planned controls:**
- SQLAlchemy ORM is used for all database access — raw SQL is avoided
- Parameterised queries are used if raw SQL is ever needed
- Jinja2 auto-escaping is enabled by default — all template variables are HTML-escaped
- No shell commands or `eval` used anywhere in application code

---

### 4. Authentication Failures

**Risk:** Weak login controls allow unauthorised access — for example, no lockout after repeated failed attempts, passwords stored in plain text, or session tokens that do not expire.

**Planned controls:**
- Passwords are hashed using Werkzeug’s `generate_password_hash` and verified using `check_password_hash`. Plain text passwords are never stored or logged.
- Plain text passwords are never stored or logged
- Flask-Login manages session lifecycle including logout and session expiry
- Login page does not reveal whether the username or password was incorrect — generic error message only
- Brute-force protection considered for later iterations

---

### 5. Security Logging and Monitoring

**Risk:** Merge decisions, role changes and login events are not recorded, making it impossible to detect misuse or audit decisions after the fact.

**Planned controls:**
- An `audit_logs` table records every merge decision with: user ID, action, affected candidate ID, timestamp
- Administrator role changes and user creation are also logged
- Audit records are append-only — no route permits editing or deleting audit entries
- Logs are viewable by Administrators only

---

### 6. Security Misconfiguration

**Risk:** The application runs in debug mode in production, exposes stack traces to users, uses a weak or committed secret key, or has unnecessary routes enabled.

**Planned controls:**
- `SECRET_KEY` is read from an environment variable — never hardcoded in committed code
- `DEBUG` mode is disabled in production (Railway sets `FLASK_ENV=production`)
- A `.env` file is listed in `.gitignore` and never committed
- Flask debug toolbar and Werkzeug debugger are not enabled in production
- `config.py` has separate `Config` and `TestingConfig` classes to prevent test settings leaking into production

---

## Summary Table

| OWASP Risk | Control |
|---|---|
| Broken Access Control | `@login_required`, `role_required` decorator, server-side role checks, access control tests |
| CSRF | Flask-WTF `CSRFProtect`, CSRF token in all forms |
| Injection | SQLAlchemy ORM, Jinja2 auto-escaping |
| Authentication Failures | Password hashing, generic error messages, Flask-Login session management |
| Security Logging and Monitoring | `audit_logs` table, append-only, admin-only view |
| Security Misconfiguration | Environment variable for secret key, debug off in production, secrets in `.gitignore` |
