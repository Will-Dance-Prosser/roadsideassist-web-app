# Test Strategy — MemberMatch

## Overview

Testing is split into layers that grow as the application is built. All automated tests run with pytest locally and via GitHub Actions on every push to `dev` and `main`.

The goal is to keep tests simple, meaningful and easy to explain in a viva. Every test should have a clear purpose that maps back to a user story or acceptance criterion.

---

## Test Layers

### 1. Route Tests (in place now)

Verify that pages load and return the correct HTTP status codes.

| Test | What it checks |
|---|---|
| `test_dashboard_page_loads` | GET `/` returns 200 and renders expected headings |

As new routes are added, a corresponding route test is added at the same time.

**Approach:** Use Flask's built-in test client. Create the app with `TESTING=True` via the factory. No real database is needed for basic route tests.

---

### 2. Form Validation Tests (planned)

Verify that Flask-WTF forms reject bad input and accept valid input.

Examples:
- Login form rejects empty username or password
- Match rule form rejects a weight outside the valid range
- Match rule form accepts a valid field, method and weight combination

**Approach:** POST to the form endpoint with a test client. Assert on the response status and the presence of error messages in the HTML.

---

### 3. Matching Logic Unit Tests (planned)

Verify that the match scoring function produces correct scores for known inputs.

Examples:
- Identical names score 100%
- Completely different names score 0%
- Partial name match scores within an expected range
- Email match adds the correct weight to the total score

**Approach:** Call the scoring function directly with controlled inputs. No HTTP request needed. These are pure unit tests.

---

### 4. Access Control Tests (planned)

Verify that role enforcement works correctly for protected routes.

Examples:
- Unauthenticated request to `/match-queue` redirects to login
- Data Analyst POST to `/candidates/<id>/approve` returns 403
- Data Steward POST to `/candidates/<id>/approve` returns 200 or redirect

**Approach:** Use Flask's test client with session manipulation or a test login helper to set the current user role. Assert on the response status code.

---

### 5. Merge Workflow Integration Tests (planned)

Verify that approving a match candidate produces the correct database state end to end.

Examples:
- After approval, candidate status is `Approved`
- After approval, a golden record exists linking both source records
- After approval, an audit log entry exists with the correct fields
- After rejection, candidate status is `Rejected` and no golden record is created

**Approach:** Use an in-memory SQLite database configured for the test session. Call the approve route via the test client. Query the database directly to assert the expected state.

---

## CI Pipeline

GitHub Actions runs on every push to `dev` and `main` using the workflow defined in `.github/workflows/`.

Steps:
1. Check out the repository
2. Set up Python 3.12
3. Install dependencies from `requirements.txt`
4. Run `pytest` with verbose output

A failing test blocks the pipeline. Merging to `main` should only happen when CI is green on `dev`.
Merges to `main` should only occur after the test workflow has passed on `dev` or on the pull request.
---

## Test File Locations

```
tests/
    test_dashboard.py       # route tests — current
    test_forms.py           # form validation — planned
    test_matching.py        # matching logic unit tests — planned
    test_access.py          # access control — planned
    test_merge_workflow.py  # integration tests — planned
```

---

## What Is Not Tested

- Front-end visual appearance (out of scope for this project)
- Third-party libraries (Bootstrap, SQLAlchemy internals)
- Real data — all test data is hardcoded and fictional
