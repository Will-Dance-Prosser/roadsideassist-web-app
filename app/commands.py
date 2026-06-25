import os
from datetime import date
import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models import AuditLog,MatchCandidate, MatchRule, SourceRecord, SourceSystem, User
from app.services.match_scoring import generate_candidates_for_source_record


DEMO_USERS = [
    {"username": "admin",   "email": "admin@demo.local",   "role": "administrator"},
    {"username": "steward", "email": "steward@demo.local", "role": "data_steward"},
    {"username": "analyst", "email": "analyst@demo.local", "role": "data_analyst"},
]


@click.command("seed-demo-users")
@with_appcontext
def seed_demo_users():
    # Create demo users for local development if they don't already exist
    password = os.environ.get("DEMO_USER_PASSWORD", "demo-password-123")

    db.create_all()

    for data in DEMO_USERS:
        existing = User.query.filter_by(username=data["username"]).first()
        if existing:
            click.echo(f"  already exists: {data['username']} ({data['role']})")
        else:
            user = User(
                username=data["username"],
                email=data["email"],
                role=data["role"],
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            click.echo(f"  created:        {data['username']} ({data['role']})")

    db.session.commit()
    click.echo(f"\nPassword for new accounts: {password}")
    click.echo("Run 'flask seed-demo-users' again at any time, existing users are not overwritten.")



# Demo MDM seed data


DEMO_SOURCE_SYSTEMS = [
    {"name": "CRM",                "description": "Main customer relationship management system"},
    {"name": "Web Portal",         "description": "Self-service member web portal"},
    {"name": "Legacy Membership",  "description": "Legacy membership database (pre-2015)"},
    {"name": "Vehicle Records",    "description": "DVLA-linked vehicle ownership records"},
]

DEMO_SOURCE_RECORDS = [
    # CRM records
    {"system": "CRM", "external_id": "CRM-001", "first_name": "John", "last_name": "Smith", "email": "j.smith@email.com", "phone": "07700 900001", "postcode": "SW1A 1AA", "date_of_birth": date(1980, 4, 12)},
    {"system": "CRM", "external_id": "CRM-002", "first_name": "Patricia", "last_name": "Patel", "email": "p.patel@email.com", "phone": "07700 900002", "postcode": "M1 1AE", "date_of_birth": date(1975, 9, 3)},
    {"system": "CRM", "external_id": "CRM-003", "first_name": "Charles", "last_name": "Johnson", "email": "c.johnson@email.com", "phone": "07700 900003", "postcode": "B1 1BB", "date_of_birth": date(1990, 1, 22)},
    {"system": "CRM", "external_id": "CRM-004", "first_name": "Sara", "last_name": "Ahmed", "email": "s.ahmed@email.com", "phone": "07700 900004", "postcode": "E1 6AN", "date_of_birth": date(1988, 7, 15)},
    {"system": "CRM", "external_id": "CRM-005", "first_name": "Michael", "last_name": "Owen", "email": "m.owen@email.com", "phone": "07700 900007", "postcode": "CF10 1EP", "date_of_birth": date(1982, 6, 18)},
    {"system": "CRM", "external_id": "CRM-006", "first_name": "Emma", "last_name": "Taylor", "email": "emma.taylor@email.com", "phone": "07700 900008", "postcode": "G1 1AA", "date_of_birth": date(1995, 12, 4)},

    # Web Portal records — near-duplicates of CRM records to demonstrate matching
    {"system": "Web Portal", "external_id": "WEB-001", "first_name": "J.", "last_name": "Smith", "email": "j.smith@email.com", "phone": "07700 900001", "postcode": "SW1A 1AA", "date_of_birth": date(1980, 4, 12)},
    {"system": "Web Portal", "external_id": "WEB-002", "first_name": "Pat", "last_name": "Patel", "email": "p.patel@email.com", "phone": "07700 900002", "postcode": "M1 1AE", "date_of_birth": date(1975, 9, 3)},
    {"system": "Web Portal", "external_id": "WEB-003", "first_name": "Laura", "last_name": "Williams", "email": "l.williams@email.com", "phone": "07700 900005", "postcode": "LS1 1BA", "date_of_birth": date(1993, 3, 8)},
    {"system": "Web Portal", "external_id": "WEB-004", "first_name": "Mike", "last_name": "Owen", "email": "m.owen@email.com", "phone": "07700 900007", "postcode": "CF10 1EP", "date_of_birth": date(1982, 6, 18)},
    {"system": "Web Portal", "external_id": "WEB-005", "first_name": "E.", "last_name": "Taylor", "email": "emma.taylor@email.com", "phone": "07700 900008", "postcode": "G1 1AA", "date_of_birth": date(1995, 12, 4)},

    # Legacy Membership records
    {"system": "Legacy Membership", "external_id": "LEG-001", "first_name": "C.", "last_name": "Johnson", "email": "cjohnson@oldmail.com", "phone": "07700 900003", "postcode": "B1 1BB", "date_of_birth": date(1990, 1, 22)},
    {"system": "Legacy Membership", "external_id": "LEG-002", "first_name": "Sara", "last_name": "Ahmad", "email": "s.ahmed@email.com", "phone": "07700 900004", "postcode": "E1 6AN", "date_of_birth": date(1988, 7, 15)},
    {"system": "Legacy Membership", "external_id": "LEG-003", "first_name": "Robert", "last_name": "Brown", "email": "r.brown@email.com", "phone": "07700 900006", "postcode": "EH1 1YZ", "date_of_birth": date(1965, 11, 30)},
    {"system": "Legacy Membership", "external_id": "LEG-004", "first_name": "Michael", "last_name": "Owens", "email": "michael.owen@oldmail.com", "phone": "07700 900007", "postcode": "CF10 1EP", "date_of_birth": date(1982, 6, 18)},

    # Vehicle Records
    {"system": "Vehicle Records", "external_id": "VEH-001", "first_name": "John", "last_name": "Smith", "email": None, "phone": None, "postcode": "SW1A 1AA", "date_of_birth": date(1980, 4, 12)},
    {"system": "Vehicle Records", "external_id": "VEH-002", "first_name": "Laura", "last_name": "Williams", "email": "l.williams@email.com", "phone": "07700 900005", "postcode": "LS1 1BA", "date_of_birth": date(1993, 3, 8)},
    {"system": "Vehicle Records", "external_id": "VEH-003", "first_name": "Emma", "last_name": "Taylor", "email": None, "phone": None, "postcode": "G1 1AA", "date_of_birth": date(1995, 12, 4)},
]

DEMO_MATCH_RULES = [
    {"field_name": "email",         "match_method": "exact",      "weight": 0.35},
    {"field_name": "phone",         "match_method": "normalised",  "weight": 0.25},
    {"field_name": "date_of_birth", "match_method": "exact",      "weight": 0.20},
    {"field_name": "last_name",     "match_method": "fuzzy",      "weight": 0.12},
    {"field_name": "postcode",      "match_method": "exact",      "weight": 0.08},
]


@click.command("seed-demo-mdm-data")
@with_appcontext
def seed_demo_mdm_data():
    # Seeds source systems, records and rules, then auto-generates pending match candidates.

    db.create_all()

    # Source Systems
    systems = {}
    for data in DEMO_SOURCE_SYSTEMS:
        existing = SourceSystem.query.filter_by(name=data["name"]).first()
        if existing:
            systems[data["name"]] = existing
            click.echo(f"  system exists:  {data['name']}")
        else:
            system = SourceSystem(name=data["name"], description=data["description"])
            db.session.add(system)
            db.session.flush()  # get id before commit
            systems[data["name"]] = system
            click.echo(f"  system created: {data['name']}")

    db.session.commit()



    # Source Records
    records = {}
    for data in DEMO_SOURCE_RECORDS:
        existing = SourceRecord.query.filter_by(external_id=data["external_id"]).first()
        if existing:
            records[data["external_id"]] = existing
            click.echo(f"  record exists:  {data['external_id']}")
        else:
            record = SourceRecord(
                source_system_id=systems[data["system"]].id,
                external_id=data["external_id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                phone=data["phone"],
                postcode=data["postcode"],
                date_of_birth=data["date_of_birth"],
            )
            db.session.add(record)
            db.session.flush()
            records[data["external_id"]] = record
            click.echo(f"  record created: {data['external_id']} — {data['first_name']} {data['last_name']}")

    db.session.commit()

    # Match Rules — seeded BEFORE candidates so calculate_match_score can use them
    for data in DEMO_MATCH_RULES:
        existing = MatchRule.query.filter_by(field_name=data["field_name"]).first()
        if existing:
            click.echo(f"  rule exists:    {data['field_name']} ({data['match_method']})")
        else:
            rule = MatchRule(
                field_name=data["field_name"],
                match_method=data["match_method"],
                weight=data["weight"],
            )
            db.session.add(rule)
            click.echo(f"  rule created:   {data['field_name']} ({data['match_method']}, weight={data['weight']})")

    db.session.commit()
    
    # Auto-generate pending match candidates using the real scoring service.
    # This keeps the demo realistic: the queue is produced by the application's
    # matching rules rather than by hardcoded candidate rows.
    click.echo("\nGenerating match candidates from seeded source records...")

    total_created = 0
    for record in SourceRecord.query.filter_by(is_archived=False).all():
        created = generate_candidates_for_source_record(
            record,
            triggered_by="demo_seed",
        )
        total_created += created

    db.session.commit()
    click.echo(f"  auto-generated pending candidates: {total_created}")

    # Drop a single audit log entry so there's something to show in the UI
    existing_log = AuditLog.query.filter_by(action="demo_seed").first()
    if not existing_log:
        db.session.add(AuditLog(
            action="demo_seed",
            target_type="seed",
            detail="Demo MDM seed data created by seed-demo-mdm-data command",
        ))
        db.session.commit()
        click.echo("  audit log entry created")

    click.echo("\nDemo MDM seed complete. Run again at any time — existing records are skipped.")


@click.command("reset-demo-mdm-data")
@with_appcontext
def reset_demo_mdm_data():
    # Wipe all MDM demo data (leaves users alone) then re-seeds from scratch
    # useful when the seed data gets into a messy state during testing

    click.echo("Deleting existing MDM demo data...")

    # Order matters here - delete children before parents to avoid FK violations
    AuditLog.query.delete()
    MergeDecision.query.delete()
    GoldenRecordLink.query.delete()
    GoldenRecord.query.delete()
    MatchCandidate.query.delete()
    SourceRecord.query.delete()
    SourceSystem.query.delete()
    MatchRule.query.delete()
    db.session.commit()

    click.echo("Existing MDM demo data deleted. Re-seeding...\n")

    # Re-use the existing seed logic
    from flask import current_app
    from click.testing import CliRunner
    runner = CliRunner()
    with current_app.app_context():
        runner.invoke(seed_demo_mdm_data, catch_exceptions=False)

    click.echo("\nDemo MDM data has been reset to its original seeded state.")
