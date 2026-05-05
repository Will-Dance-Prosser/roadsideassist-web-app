# Acceptance Criteria — MemberMatch

Each item maps to a user story in `user-stories.md`.

---

## Source Records (US-01 to US-03)

**AC-01** — Browse source records
- Given I am logged in as a Data Steward or Data Analyst
- When I navigate to Source Records
- Then I see a paginated list of source records showing name, source system, email and record ID

**AC-02** — Filter source records
- Given I am on the Source Records page
- When I enter a search term or filter by source system
- Then only matching records are shown

**AC-03** — View data sources
- Given I am logged in as an Administrator
- When I navigate to Data Sources
- Then I see a list of all connected source systems with their record counts

**AC-19** — Archive a source record
- Given I am logged in as an Administrator
- When I archive a source record
- Then the record is hidden from normal source record lists but remains available for audit and historical traceability

---

## Match Candidates (US-04 to US-08)

**AC-04** — View pending queue
- Given I am logged in as a Data Steward
- When I navigate to Match Queue
- Then I see only candidates with a status of Pending Review, ordered by match score descending

**AC-05** — Side-by-side review
- Given I am on the Match Queue
- When I open a match candidate
- Then I see both source records displayed side by side with the match score and highlighted matching fields

**AC-06** — Approve a match
- Given I am reviewing a match candidate
- When I click Approve
- Then the candidate status changes to Approved, the records are linked to a golden record, and the decision is recorded in the audit log

**AC-07** — Reject a match
- Given I am reviewing a match candidate
- When I click Reject
- Then the candidate status changes to Rejected, the records are not merged, and the decision is recorded in the audit log

**AC-08** — Analyst cannot approve
- Given I am logged in as a Data Analyst
- When I navigate to a match candidate detail page
- Then the Approve and Reject buttons are not visible and any direct POST attempt returns 403

---

## Golden Records (US-09 to US-11)

**AC-09** — View golden records list
- Given I am logged in as any role
- When I navigate to Golden Records
- Then I see a list of golden records with member name, record ID and the number of contributing source records

**AC-10** — View source links on a golden record
- Given I am viewing a golden record
- When I expand the contributing records section
- Then I see each source record that was merged into this golden record, with its source system and original record ID

---

## Matching Rules (US-12 to US-13)

**AC-11** — View matching rules
- Given I am logged in as an Administrator
- When I navigate to Rules
- Then I see a list of active matching rules showing the field, matching method and weight

**AC-12** — Add a matching rule
- Given I am on the Rules page as an Administrator
- When I submit a new rule with a valid field, method and weight
- Then the rule is saved and appears in the rules list

**AC-13** — Invalid rule rejected
- Given I submit a rule with a missing field or invalid weight
- When the form is submitted
- Then a validation error is shown and no rule is saved

---

## Audit Log (US-14 to US-15)

**AC-14** — Audit log contains required fields
- Given a merge decision has been made
- When I view the audit log as an Administrator
- Then I see the user who made the decision, the action taken, the candidate ID and the timestamp

**AC-15** — Audit log is read only
- Given I am viewing the audit log
- Then there are no edit or delete controls visible and no route accepts modifications to audit records

---

## Access Control (US-16 to US-18)

**AC-16** — Login required
- Given I am not logged in
- When I attempt to access any protected page
- Then I am redirected to the login page

**AC-17** — Role enforcement
- Given I am logged in as a Data Analyst
- When I attempt to POST to an approve or reject endpoint
- Then the server returns 403 and no change is made

**AC-18** — Administrator can manage users
- Given I am logged in as an Administrator
- When I navigate to user management
- Then I can create a new user, assign a role and deactivate an existing account
