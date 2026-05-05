# User Stories — MemberMatch

## Roles

| Role | Description |
|---|---|
| Administrator | Manages users, data sources, matching rules and audit records |
| Data Steward | Reviews match candidates and approves or rejects proposed merges |
| Data Analyst | Views source records, match candidates and golden records — read only |

---

## Source Records

**US-01** — As a Data Steward, I want to browse source records from each connected system so that I can understand what raw member data is available before reviewing matches.

**US-02** — As a Data Analyst, I want to search and filter source records by name, email or source system so that I can quickly locate a specific member record.

**US-03** — As an Administrator, I want to view which source systems have been loaded into the portal so that I can confirm the data landscape is correct.

**US-19** — As an Administrator, I want to archive source records or deactivate source systems so that inaccurate or retired data can be removed from normal workflows without losing audit history.

---

## Match Candidates

**US-04** — As a Data Steward, I want to see a queue of pending match candidates so that I know which records need a review decision.

**US-05** — As a Data Steward, I want to view two source records side by side with their match score and matched fields so that I can make an informed approve or reject decision.

**US-06** — As a Data Steward, I want to approve a match candidate so that the two records are linked and a golden record is created or updated.

**US-07** — As a Data Steward, I want to reject a match candidate so that the two records are marked as a false match and removed from the review queue.

**US-08** — As a Data Analyst, I want to view match candidates and their scores so that I can understand the current state of the data without making decisions.

---

## Golden Records

**US-09** — As a Data Steward, I want to view the list of golden records so that I can see which members have a trusted master record.

**US-10** — As a Data Steward, I want to view which source records contributed to a golden record so that I can trace where the trusted data came from.

**US-11** — As a Data Analyst, I want to view golden records so that I can use them for reporting and analysis.

---

## Matching Rules

**US-12** — As an Administrator, I want to view the current matching rules so that I can understand how match scores are calculated.

**US-13** — As an Administrator, I want to add or update a matching rule so that the system can be tuned to improve match quality.

---

## Audit Log

**US-14** — As an Administrator, I want to view a log of all merge decisions so that I have a record of who approved or rejected each match and when.

**US-15** — As an Administrator, I want the audit log to record the user, the action, the affected records and the timestamp so that decisions can be traced and reviewed.

---

## Access Control

**US-16** — As a user, I want to log in with a username and password so that only authorised people can access the portal.

**US-17** — As an Administrator, I want to create and manage user accounts so that I control who has access and what role they hold.

**US-18** — As a Data Analyst, I want the system to prevent me from approving or rejecting matches so that the workflow is protected from unauthorised changes.
