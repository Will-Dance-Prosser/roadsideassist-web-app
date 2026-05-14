import pytest
from app import create_app
from app.extensions import db
from app.models import GoldenRecord, MatchCandidate, SourceRecord, SourceSystem, User
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        user = User(username="steward", email="steward@example.com", role="data_steward")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"username": "steward", "password": "correct-password"}, follow_redirects=True)
    return c


@pytest.fixture
def anon_client(app):
    return app.test_client()


def _seed_source_record(app, first_name="Jane", last_name="Doe", email="jane@example.com",
                         postcode="SW1A1AA", phone="07700900001", external_id="EXT-001"):
    with app.app_context():
        system = SourceSystem(name=f"SYS-{external_id}")
        db.session.add(system)
        db.session.flush()
        r = SourceRecord(
            source_system_id=system.id,
            external_id=external_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            postcode=postcode,
            phone=phone,
        )
        db.session.add(r)
        db.session.commit()
        return r.id


def _seed_golden_record(app, first_name="John", last_name="Gold",
                         email="gold@example.com", postcode="EC1A1BB", phone="07700900002"):
    with app.app_context():
        g = GoldenRecord(
            first_name=first_name,
            last_name=last_name,
            email=email,
            postcode=postcode,
            phone=phone,
        )
        db.session.add(g)
        db.session.commit()
        return g.id


def _seed_match_candidate(app):
    with app.app_context():
        system = SourceSystem(name="SYS-MC")
        db.session.add(system)
        db.session.flush()
        r1 = SourceRecord(source_system_id=system.id, external_id="MC-R1", first_name="Alice", last_name="Smith")
        r2 = SourceRecord(source_system_id=system.id, external_id="MC-R2", first_name="Bob", last_name="Jones")
        db.session.add_all([r1, r2])
        db.session.flush()
        c = MatchCandidate(record_a_id=r1.id, record_b_id=r2.id, match_score=0.88, status="pending")
        db.session.add(c)
        db.session.commit()
        return c.id


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_search_requires_login(anon_client):
    response = anon_client.get("/search?q=test", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Empty query
# ---------------------------------------------------------------------------

def test_search_empty_query_shows_friendly_message(client):
    response = client.get("/search")
    assert response.status_code == 200
    assert b"Enter a search term" in response.data


def test_search_whitespace_query_shows_friendly_message(client):
    response = client.get("/search?q=   ")
    assert response.status_code == 200
    assert b"Enter a search term" in response.data


# ---------------------------------------------------------------------------
# Source Records
# ---------------------------------------------------------------------------

def test_search_by_first_name_returns_source_record(app, client):
    _seed_source_record(app, first_name="Zelda", last_name="Unique")
    response = client.get("/search?q=Zelda")
    assert response.status_code == 200
    assert b"Source Records" in response.data
    assert b"Zelda" in response.data


def test_search_by_last_name_returns_source_record(app, client):
    _seed_source_record(app, first_name="Roger", last_name="Distinctlastname")
    response = client.get("/search?q=Distinctlastname")
    assert response.status_code == 200
    assert b"Distinctlastname" in response.data


def test_search_by_email_returns_source_record(app, client):
    _seed_source_record(app, email="unique_search@example.com", external_id="EXT-EMAIL")
    response = client.get("/search?q=unique_search@example.com")
    assert response.status_code == 200
    assert b"unique_search@example.com" in response.data


def test_search_by_postcode_returns_source_record(app, client):
    _seed_source_record(app, postcode="ZZ99ZZ", external_id="EXT-POST")
    response = client.get("/search?q=ZZ99ZZ")
    assert response.status_code == 200
    assert b"ZZ99ZZ" in response.data


def test_search_by_phone_returns_source_record(app, client):
    _seed_source_record(app, phone="07911123456", external_id="EXT-PHONE")
    response = client.get("/search?q=07911123456")
    assert response.status_code == 200
    assert b"07911123456" in response.data


def test_search_by_external_id_returns_source_record(app, client):
    _seed_source_record(app, external_id="EXTID-UNIQUE-999")
    response = client.get("/search?q=EXTID-UNIQUE-999")
    assert response.status_code == 200
    assert b"EXTID-UNIQUE-999" in response.data


# ---------------------------------------------------------------------------
# Golden Records
# ---------------------------------------------------------------------------

def test_search_by_name_returns_golden_record(app, client):
    _seed_golden_record(app, first_name="Goldie", last_name="Locks")
    response = client.get("/search?q=Goldie")
    assert response.status_code == 200
    assert b"Golden Records" in response.data
    assert b"Goldie" in response.data


def test_search_by_golden_email_returns_golden_record(app, client):
    _seed_golden_record(app, email="goldunique@example.com")
    response = client.get("/search?q=goldunique@example.com")
    assert response.status_code == 200
    assert b"goldunique@example.com" in response.data


# ---------------------------------------------------------------------------
# Match Candidates
# ---------------------------------------------------------------------------

def test_search_by_mc_reference_returns_candidate(app, client):
    cid = _seed_match_candidate(app)
    response = client.get(f"/search?q=MC-{cid:04d}")
    assert response.status_code == 200
    assert b"Match Candidates" in response.data
    assert f"MC-{cid:04d}".encode() in response.data


def test_search_by_plain_id_returns_candidate(app, client):
    cid = _seed_match_candidate(app)
    response = client.get(f"/search?q={cid}")
    assert response.status_code == 200
    assert f"MC-{cid:04d}".encode() in response.data


def test_search_by_zero_padded_id_returns_candidate(app, client):
    cid = _seed_match_candidate(app)
    response = client.get(f"/search?q={cid:04d}")
    assert response.status_code == 200
    assert f"MC-{cid:04d}".encode() in response.data


# ---------------------------------------------------------------------------
# No results
# ---------------------------------------------------------------------------

def test_search_no_results_shows_no_results_message(client):
    response = client.get("/search?q=ZZZNOMATCH999XYZ")
    assert response.status_code == 200
    assert b"No results found" in response.data
