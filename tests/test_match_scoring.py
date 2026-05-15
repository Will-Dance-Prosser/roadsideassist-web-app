"""Tests for the match scoring service (app/services/match_scoring.py)."""

import pytest
from app import create_app
from app.extensions import db
from app.models import MatchCandidate, MatchRule, SourceRecord, SourceSystem
from app.services.match_scoring import (
    calculate_match_score,
    recalculate_all_candidate_scores,
    recalculate_candidate_score,
    recalculate_scores_for_source_record,
)
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def system(app):
    with app.app_context():
        s = SourceSystem(name="TEST")
        db.session.add(s)
        db.session.commit()
        yield s


def _make_record(system_id, external_id, **kwargs):
    r = SourceRecord(source_system_id=system_id, external_id=external_id, **kwargs)
    db.session.add(r)
    db.session.flush()
    return r


def _make_rule(field_name, match_method, weight, is_active=True):
    r = MatchRule(
        field_name=field_name,
        match_method=match_method,
        weight=weight,
        is_active=is_active,
    )
    db.session.add(r)
    db.session.flush()
    return r


def _make_candidate(rec_a, rec_b, score=0.0, status="pending"):
    c = MatchCandidate(
        record_a_id=rec_a.id,
        record_b_id=rec_b.id,
        match_score=score,
        status=status,
    )
    db.session.add(c)
    db.session.flush()
    return c


# ---------------------------------------------------------------------------
# calculate_match_score
# ---------------------------------------------------------------------------


class TestCalculateMatchScore:
    def test_exact_email_match_contributes_weight(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "A1", email="user@test.com")
            rec_b = _make_record(system.id, "A2", email="user@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.35

    def test_exact_email_case_insensitive(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "B1", email="User@Test.COM")
            rec_b = _make_record(system.id, "B2", email="user@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.35

    def test_email_mismatch_contributes_nothing(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "C1", email="a@test.com")
            rec_b = _make_record(system.id, "C2", email="b@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.0

    def test_phone_normalised_match(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("phone", "normalised", 0.25)
            rec_a = _make_record(system.id, "D1", phone="077 009 00001")
            rec_b = _make_record(system.id, "D2", phone="07700900001")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.25

    def test_postcode_normalised_match(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("postcode", "normalised", 0.08)
            rec_a = _make_record(system.id, "E1", postcode="sw1a 1aa")
            rec_b = _make_record(system.id, "E2", postcode="SW1A1AA")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.08

    def test_fuzzy_last_name_close_match(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("last_name", "fuzzy", 0.12)
            rec_a = _make_record(system.id, "F1", last_name="Ahmed")
            rec_b = _make_record(system.id, "F2", last_name="Ahmad")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.12

    def test_fuzzy_last_name_no_match(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("last_name", "fuzzy", 0.12)
            rec_a = _make_record(system.id, "G1", last_name="Smith")
            rec_b = _make_record(system.id, "G2", last_name="Jones")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.0

    def test_inactive_rule_not_counted(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35, is_active=False)
            rec_a = _make_record(system.id, "H1", email="user@test.com")
            rec_b = _make_record(system.id, "H2", email="user@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.0

    def test_missing_field_contributes_nothing(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "I1", email=None)
            rec_b = _make_record(system.id, "I2", email="user@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.0

    def test_score_clamped_to_one(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.6)
            _make_rule("phone", "normalised", 0.6)
            rec_a = _make_record(system.id, "J1", email="x@test.com", phone="07700900001")
            rec_b = _make_record(system.id, "J2", email="x@test.com", phone="07700900001")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 1.0

    def test_no_active_rules_returns_zero(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            rec_a = _make_record(system.id, "K1", email="x@test.com")
            rec_b = _make_record(system.id, "K2", email="x@test.com")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == 0.0

    def test_multiple_rules_accumulate(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            _make_rule("phone", "normalised", 0.25)
            rec_a = _make_record(system.id, "L1", email="x@test.com", phone="07700900001")
            rec_b = _make_record(system.id, "L2", email="x@test.com", phone="07700900001")
            db.session.commit()
            score = calculate_match_score(rec_a, rec_b)
            assert score == round(0.35 + 0.25, 2)


# ---------------------------------------------------------------------------
# recalculate_candidate_score
# ---------------------------------------------------------------------------


class TestRecalculateCandidateScore:
    def test_pending_candidate_score_updated(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "M1", email="x@test.com")
            rec_b = _make_record(system.id, "M2", email="x@test.com")
            candidate = _make_candidate(rec_a, rec_b, score=0.0, status="pending")
            db.session.commit()
            recalculate_candidate_score(candidate)
            assert candidate.match_score == 0.35

    def test_approved_candidate_score_unchanged(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "N1", email="x@test.com")
            rec_b = _make_record(system.id, "N2", email="x@test.com")
            candidate = _make_candidate(rec_a, rec_b, score=0.98, status="approved")
            db.session.commit()
            recalculate_candidate_score(candidate)
            assert candidate.match_score == 0.98

    def test_rejected_candidate_score_unchanged(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "O1", email="x@test.com")
            rec_b = _make_record(system.id, "O2", email="x@test.com")
            candidate = _make_candidate(rec_a, rec_b, score=0.94, status="rejected")
            db.session.commit()
            recalculate_candidate_score(candidate)
            assert candidate.match_score == 0.94


# ---------------------------------------------------------------------------
# recalculate_scores_for_source_record
# ---------------------------------------------------------------------------


class TestRecalculateScoresForSourceRecord:
    def test_pending_candidates_involving_record_are_updated(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "P1", email="x@test.com")
            rec_b = _make_record(system.id, "P2", email="x@test.com")
            candidate = _make_candidate(rec_a, rec_b, score=0.0, status="pending")
            db.session.commit()
            recalculate_scores_for_source_record(rec_a.id)
            db.session.commit()
            db.session.refresh(candidate)
            assert candidate.match_score == 0.35

    def test_unrelated_candidates_not_touched(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "Q1", email="a@test.com")
            rec_b = _make_record(system.id, "Q2", email="a@test.com")
            unrelated_c = _make_record(system.id, "Q3", email="b@test.com")
            unrelated_d = _make_record(system.id, "Q4", email="b@test.com")
            candidate = _make_candidate(rec_a, rec_b, score=0.0, status="pending")
            other = _make_candidate(unrelated_c, unrelated_d, score=0.99, status="pending")
            db.session.commit()
            recalculate_scores_for_source_record(rec_a.id)
            db.session.commit()
            db.session.refresh(candidate)
            db.session.refresh(other)
            assert candidate.match_score == 0.35
            assert other.match_score == 0.99  # unchanged — not involved with rec_a


# ---------------------------------------------------------------------------
# recalculate_all_candidate_scores
# ---------------------------------------------------------------------------


class TestRecalculateAllCandidateScores:
    def test_all_pending_candidates_updated(self, app, system):
        with app.app_context():
            system = db.session.merge(system)
            _make_rule("email", "exact", 0.35)
            rec_a = _make_record(system.id, "R1", email="x@test.com")
            rec_b = _make_record(system.id, "R2", email="x@test.com")
            rec_c = _make_record(system.id, "R3", email="y@test.com")
            rec_d = _make_record(system.id, "R4", email="y@test.com")
            c1 = _make_candidate(rec_a, rec_b, score=0.0, status="pending")
            c2 = _make_candidate(rec_c, rec_d, score=0.0, status="pending")
            approved = _make_candidate(rec_a, rec_c, score=0.98, status="approved")
            db.session.commit()
            recalculate_all_candidate_scores()
            db.session.refresh(c1)
            db.session.refresh(c2)
            db.session.refresh(approved)
            assert c1.match_score == 0.35
            assert c2.match_score == 0.35
            assert approved.match_score == 0.98  # unchanged
