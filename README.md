# MemberMatch

MemberMatch is a simulated Master Data Management (MDM) match-and-merge portal developed for the Software Engineering and DevOps Level 6 module.

The application is designed to support a fictional data stewardship workflow. It will allow users to review potential duplicate member records from multiple fictional source systems, approve or reject match candidates, and maintain trusted golden records.

All records, source systems, match candidates and user accounts are fictional and created for demonstration purposes only. No real customer, colleague, operational or live system data is used.

## Technology Stack

- Python
- Flask
- Jinja2 templates
- Bootstrap 5
- SQLAlchemy
- Flask-Migrate
- Flask-WTF
- PostgreSQL hosted on Railway
- pytest
- GitHub Actions
- Gunicorn

## Planned Features

- Secure login and logout
- Role-based access control
- Dashboard showing match-review activity
- Source record browsing and management
- Match candidate queue with approve/reject workflow
- Golden record creation and management
- Configurable matching rules
- Audit logging for merge decisions and administrative changes
- Admin user management
- Form validation and user feedback
- OWASP Top 10 security evidence

## Planned User Roles

- Administrator: manages users, data sources, matching rules and audit records
- Data Steward: reviews match candidates and approves or rejects proposed merges
- Data Analyst: views source records, match candidates and golden records but cannot approve merges

## Development Status

Project has been re-scoped and the initial Flask layout is in place. Core MDM features have not yet been implemented.

## Security and Privacy Notice

This project uses fictional demonstration data only. It must not contain real customer records, personal data, colleague data, operational data or live system data.

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py