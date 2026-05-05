# Data Model Plan — MemberMatch

## Overview

This document describes the planned database tables for MemberMatch. No models have been implemented yet — this is a planning document only.

The database will be PostgreSQL in production (hosted on Railway) and SQLite for local development. SQLAlchemy will be used for all database access via the ORM. Flask-Migrate will manage schema changes.

---

## Tables

### `users`

Stores application user accounts.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `username` | String | Unique, not null |
| `email` | String | Unique, not null |
| `password_hash` | String | bcrypt hash, never plain text |
| `role` | String | `administrator`, `data_steward`, `data_analyst` |
| `is_active` | Boolean | False disables login without deleting the account |
| `created_at` | DateTime | Set on insert |

---

### `source_systems`

Represents each fictional source system that member records are loaded from.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `name` | String | e.g. `CRM`, `ERP`, `LEGACY` |
| `description` | String | Optional |
| `created_at` | DateTime | Set on insert |
| `is_active` | Boolean | False disables the source system without deleting history

---

### `source_records`

Individual member records as they exist in a source system, before any matching or merging.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `source_system_id` | Integer | Foreign key → `source_systems.id` |
| `external_id` | String | The record's ID in the originating system |
| `first_name` | String | |
| `last_name` | String | |
| `email` | String | |
| `date_of_birth` | Date | Optional |
| `postcode` | String | Optional |
| `phone` | String | Optional |
| `raw_data` | JSON | Full original record for reference |
| `created_at` | DateTime | Set on insert |
| `is_archived` | Boolean | False by default; archived records are hidden from normal views
| `archived_at` | DateTime | Nullable; set when record is archived

---

### `match_candidates`

A pair of source records that the matching process has identified as potential duplicates.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `record_a_id` | Integer | Foreign key → `source_records.id` |
| `record_b_id` | Integer | Foreign key → `source_records.id` |
| `match_score` | Float | 0.0 to 1.0 — calculated by the matching rules |
| `status` | String | `pending`, `approved`, `rejected` |
| `created_at` | DateTime | Set on insert |
| `reviewed_at` | DateTime | Set when a decision is made |
| `reviewed_by_id` | Integer | Foreign key → `users.id`, nullable |

---

### `golden_records`

A trusted master record created when a match is approved. Represents the single version of truth for a member.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `first_name` | String | |
| `last_name` | String | |
| `email` | String | |
| `date_of_birth` | Date | Optional |
| `postcode` | String | Optional |
| `phone` | String | Optional |
| `created_at` | DateTime | Set on insert |
| `updated_at` | DateTime | Updated on each merge |

---

### `golden_record_links`

Links a source record to its golden record. One golden record can have many contributing source records.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `golden_record_id` | Integer | Foreign key → `golden_records.id` |
| `source_record_id` | Integer | Foreign key → `source_records.id` |
| `linked_at` | DateTime | Set on insert |

---

### `merge_decisions`

Records the outcome of each match candidate review. Separate from `match_candidates` to keep the workflow history clean.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `candidate_id` | Integer | Foreign key → `match_candidates.id` |
| `decided_by_id` | Integer | Foreign key → `users.id` |
| `decision` | String | `approved` or `rejected` |
| `notes` | String | Optional — reviewer comments |
| `decided_at` | DateTime | Set on insert |

---

### `match_rules`

Configuration for how match scores are calculated. Each rule targets a field and assigns a weight.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `field_name` | String | e.g. `email`, `last_name`, `date_of_birth` |
| `match_method` | String | e.g. `exact`, `fuzzy`, `phonetic` |
| `weight` | Float | Contribution to the total score — weights should sum to 1.0 |
| `is_active` | Boolean | Inactive rules are ignored during scoring |
| `created_at` | DateTime | Set on insert |
| `updated_at` | DateTime | Updated when a rule is changed

---

### `audit_logs`

Append-only log of significant events. Never updated or deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key → `users.id`, nullable (system actions) |
| `action` | String | e.g. `match_approved`, `match_rejected`, `user_created`, `rule_updated` |
| `target_type` | String | The type of object affected, e.g. `match_candidate`, `user` |
| `target_id` | Integer | The ID of the object affected |
| `detail` | String | Optional human-readable summary |
| `created_at` | DateTime | Set on insert |

---

## Relationships Summary

```
source_systems ──< source_records
source_records >── match_candidates (as record_a and record_b)
match_candidates ──< merge_decisions
match_candidates >── golden_records (via approval)
golden_records ──< golden_record_links ──> source_records
users ──< merge_decisions
users ──< audit_logs
match_rules (standalone — used by the matching process)
```

---

## Notes

- All tables will be created via Flask-Migrate — no manual SQL.
- `audit_logs` has no update or delete route by design.
- `raw_data` on `source_records` stores the original JSON payload so nothing is lost if field mapping changes later.
- `match_score` is stored on the candidate at the time of creation — it is not recalculated live so that historical decisions remain meaningful.
- Delete behaviour will be implemented as soft deletion or deactivation rather than permanent deletion, so that data lineage and audit history are preserved.
