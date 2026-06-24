import pytest
from app import create_app
from app.extensions import db
from app.models import MatchRule, User
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
def client(app):
    return app.test_client()


def _create_and_login(client, app, username, email, role):
    """Helper: create a user with the given role and log them in."""
    with app.app_context():
        user = User(username=username, email=email, role=role)
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
    client.post(
        "/login",
        data={"username": username, "password": "test-password"},
        follow_redirects=True,
    )


def test_unauthenticated_rules_redirects_to_login(client):
    response = client.get("/rules", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_data_analyst_receives_403_for_rules(client, app):
    _create_and_login(client, app, "analyst", "analyst@example.com", "data_analyst")
    response = client.get("/rules")
    assert response.status_code == 403


def test_data_steward_receives_403_for_rules(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/rules")
    assert response.status_code == 403


def test_administrator_can_access_rules(client, app):
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get("/rules")
    assert response.status_code == 200
    assert b"Match Rules" in response.data


def test_403_page_renders_useful_text(client, app):
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get("/rules")
    assert response.status_code == 403
    assert b"403" in response.data
    assert b"Access Denied" in response.data
    assert b"Back to Dashboard" in response.data


def _seed_rule(app):
    with app.app_context():
        rule = MatchRule(
            field_name="email",
            match_method="exact",
            weight=0.35,
            is_active=True,
        )
        db.session.add(rule)
        db.session.commit()


def test_rules_page_renders_rule_from_database(client, app):
    _seed_rule(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get("/rules")
    assert response.status_code == 200
    assert b"email" in response.data
    assert b"exact" in response.data
    assert b"0.35" in response.data


def test_rules_page_shows_active_badge(client, app):
    _seed_rule(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get("/rules")
    assert b"Active" in response.data


def test_rules_page_shows_inactive_badge(client, app):
    with app.app_context():
        rule = MatchRule(field_name="phone", match_method="normalised", weight=0.25, is_active=False)
        db.session.add(rule)
        db.session.commit()
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get("/rules")
    assert b"Inactive" in response.data


# ---------------------------------------------------------------------------
# Edit rule tests
# ---------------------------------------------------------------------------

def _seed_rule_and_get_id(app):
    with app.app_context():
        rule = MatchRule(field_name="email", match_method="exact", weight=0.35, is_active=True)
        db.session.add(rule)
        db.session.commit()
        return rule.id


def _edit_form(field_name="email", match_method="exact", weight="0.40", is_active="y"):
    data = {"field_name": field_name, "match_method": match_method, "weight": weight}
    if is_active:
        data["is_active"] = is_active
    return data


def test_administrator_can_access_rule_edit_page(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.get(f"/rules/{rule_id}/edit")
    assert response.status_code == 200
    assert b"Edit Rule" in response.data


def test_data_steward_cannot_access_rule_edit(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "steward", "steward@example.com", "data_steward")
    response = client.get(f"/rules/{rule_id}/edit")
    assert response.status_code == 403


def test_data_analyst_cannot_access_rule_edit(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "analyst", "analyst@example.com", "data_analyst")
    response = client.get(f"/rules/{rule_id}/edit")
    assert response.status_code == 403


def test_administrator_can_update_rule_weight(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit", data=_edit_form(weight="0.75"), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert abs(rule.weight - 0.75) < 0.001


def test_administrator_can_deactivate_rule(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    # omit is_active to leave it unchecked
    response = client.post(f"/rules/{rule_id}/edit", data=_edit_form(is_active=None), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.is_active is False


def test_invalid_weight_is_rejected(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit", data=_edit_form(weight="1.5"))
    assert response.status_code == 200
    assert b"Weight must be between" in response.data
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert abs(rule.weight - 0.35) < 0.001  # unchanged


def test_duplicate_field_method_combination_is_rejected(client, app):
    with app.app_context():
        r1 = MatchRule(field_name="email", match_method="exact", weight=0.35, is_active=True)
        r2 = MatchRule(field_name="last_name", match_method="fuzzy", weight=0.20, is_active=True)
        db.session.add_all([r1, r2])
        db.session.commit()
        r2_id = r2.id

    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    # Try to change r2 to the same field+method as r1
    response = client.post(f"/rules/{r2_id}/edit", data=_edit_form(field_name="email", match_method="exact", weight="0.20"))
    assert response.status_code == 200
    assert b"already uses" in response.data


# ---------------------------------------------------------------------------
# Audit log tests
# ---------------------------------------------------------------------------

def test_match_rule_update_creates_audit_log(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    client.post(f"/rules/{rule_id}/edit", data=_edit_form(weight="0.30"), follow_redirects=True)
    with app.app_context():
        from app.models import AuditLog
        entry = AuditLog.query.filter_by(action="match_rule_updated", target_id=rule_id).first()
        assert entry is not None
        assert "match_rule" == entry.target_type


def test_match_rule_audit_detail_includes_changed_field(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    client.post(f"/rules/{rule_id}/edit", data=_edit_form(weight="0.30"), follow_redirects=True)
    with app.app_context():
        from app.models import AuditLog
        entry = AuditLog.query.filter_by(action="match_rule_updated").first()
        assert "weight" in entry.detail
        assert "0.30" in entry.detail or "0.3" in entry.detail


def test_match_rule_deactivation_creates_audit_log(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    client.post(f"/rules/{rule_id}/edit", data=_edit_form(is_active=None), follow_redirects=True)
    with app.app_context():
        from app.models import AuditLog
        entry = AuditLog.query.filter_by(action="match_rule_updated").first()
        assert entry is not None
        assert "active" in entry.detail


def test_match_rule_audit_mentions_score_recalculation(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    client.post(f"/rules/{rule_id}/edit", data=_edit_form(weight="0.28"), follow_redirects=True)
    with app.app_context():
        from app.models import AuditLog
        entry = AuditLog.query.filter_by(action="match_rule_updated").first()
        assert "recalculated" in entry.detail.lower()


# ---------------------------------------------------------------------------
# Match method validation tests
# ---------------------------------------------------------------------------

def test_phonetic_method_is_rejected(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit",
                           data=_edit_form(field_name="email", match_method="phonetic", weight="0.35"))
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.match_method != "phonetic"


def test_normalised_not_allowed_for_email(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit",
                           data=_edit_form(field_name="email", match_method="normalised", weight="0.35"))
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.match_method != "normalised"


def test_fuzzy_not_allowed_for_date_of_birth(client, app):
    with app.app_context():
        rule = MatchRule(field_name="date_of_birth", match_method="exact", weight=0.20, is_active=True)
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit",
                           data=_edit_form(field_name="date_of_birth", match_method="fuzzy", weight="0.20"))
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.match_method == "exact"  # unchanged


def test_valid_method_for_phone_is_accepted(client, app):
    with app.app_context():
        rule = MatchRule(field_name="phone", match_method="exact", weight=0.25, is_active=True)
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit",
                           data=_edit_form(field_name="phone", match_method="normalised", weight="0.25"),
                           follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.match_method == "normalised"


def test_field_name_must_be_known_field(client, app):
    rule_id = _seed_rule_and_get_id(app)
    _create_and_login(client, app, "admin", "admin@example.com", "administrator")
    response = client.post(f"/rules/{rule_id}/edit",
                           data=_edit_form(field_name="favourite_colour", match_method="exact", weight="0.35"))
    assert response.status_code == 200
    with app.app_context():
        rule = db.session.get(MatchRule, rule_id)
        assert rule.field_name == "email"  # unchanged

