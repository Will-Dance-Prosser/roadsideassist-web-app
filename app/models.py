from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="data_steward")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Allowed role values: administrator, data_steward, data_analyst

    def set_password(self, password):
        self.password_hash = generate_password_hash(password) #Hash using salt for no repeated hashes

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>" # debug/logging


@login_manager.user_loader # Reloads user from DB on each request using session cookie
def load_user(user_id):
    return db.session.get(User, int(user_id)) # check user table/ convert to id int


#Source System--------------------------------------------------------------------------

class SourceSystem(db.Model):
    __tablename__ = "source_systems"
    # Columns
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    records = db.relationship("SourceRecord", back_populates="source_system")

    def __repr__(self):
        return f"<SourceSystem {self.name}>"



#Source Record----------------------------------------------------------------------------

class SourceRecord(db.Model):
    __tablename__ = "source_records"

    id = db.Column(db.Integer, primary_key=True)
    source_system_id = db.Column(db.Integer, db.ForeignKey("source_systems.id"), nullable=False)
    external_id = db.Column(db.String(128), nullable=False)   # ID in the originating system
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    postcode = db.Column(db.String(16), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    raw_data = db.Column(db.Text, nullable=True)    # JSON stored as text
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    source_system = db.relationship("SourceSystem", back_populates="records")
    golden_links = db.relationship("GoldenRecordLink", back_populates="source_record")

    def __repr__(self):
        return f"<SourceRecord {self.external_id} ({self.first_name} {self.last_name})>"
    



#Match Candidate----------------------------------------------------------------------------

class MatchCandidate(db.Model):
    __tablename__ = "match_candidates"

    id = db.Column(db.Integer, primary_key=True)
    record_a_id = db.Column(db.Integer, db.ForeignKey("source_records.id"), nullable=False)
    record_b_id = db.Column(db.Integer, db.ForeignKey("source_records.id"), nullable=False)
    match_score = db.Column(db.Float,   nullable=False) # between 0.0 to 1.0
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending, approved, rejected
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    record_a = db.relationship("SourceRecord", foreign_keys=[record_a_id])
    record_b = db.relationship("SourceRecord", foreign_keys=[record_b_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    decisions = db.relationship("MergeDecision", back_populates="candidate")

    def __repr__(self):
        return f"<MatchCandidate {self.id} score={self.match_score} status={self.status}>"





#Golden Record ------------------------------------------------------------------------------

class GoldenRecord(db.Model):
    __tablename__ = "golden_records"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64),  nullable=True)
    last_name = db.Column(db.String(64),  nullable=True)
    email = db.Column(db.String(120), nullable=True)
    date_of_birth = db.Column(db.Date,        nullable=True)
    postcode = db.Column(db.String(16),  nullable=True)
    phone = db.Column(db.String(32),  nullable=True)
    created_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_links = db.relationship("GoldenRecordLink", back_populates="golden_record")

    def __repr__(self):
        return f"<GoldenRecord {self.id} {self.first_name} {self.last_name}>"





#Golden Record Link ------------------------------------------------------------------------------

# joins GoldenRecord and SourceRecord many to many relationship

class GoldenRecordLink(db.Model):
    __tablename__ = "golden_record_links"

    id = db.Column(db.Integer, primary_key=True)
    golden_record_id = db.Column(db.Integer, db.ForeignKey("golden_records.id"),  nullable=False)
    source_record_id = db.Column(db.Integer, db.ForeignKey("source_records.id"),  nullable=False)
    linked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    golden_record = db.relationship("GoldenRecord", back_populates="source_links")
    source_record = db.relationship("SourceRecord",  back_populates="golden_links")

    def __repr__(self):
        return f"<GoldenRecordLink golden={self.golden_record_id} source={self.source_record_id}>"
    




#Merge decision ----------------------------------------------------------------------------------

class MergeDecision(db.Model):
    __tablename__ = "merge_decisions"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("match_candidates.id"), nullable=False)
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id"),            nullable=False)
    decision = db.Column(db.String(16), nullable=False) # approved, rejected
    notes = db.Column(db.String(512), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    candidate = db.relationship("MatchCandidate", back_populates="decisions")
    decided_by = db.relationship("User", foreign_keys=[decided_by_id])

    def __repr__(self):
        return f"<MergeDecision {self.decision} candidate={self.candidate_id}>"




#Match Rule -----------------------------------------------------------------------------------------

class MatchRule(db.Model):
    __tablename__ = "match_rules"

    id = db.Column(db.Integer, primary_key=True)
    field_name = db.Column(db.String(64),  nullable=False)    # e.g. email, last_name
    match_method = db.Column(db.String(32),  nullable=False)    # exact, fuzzy, phonetic
    weight = db.Column(db.Float,       nullable=False)    # contribution to total score
    is_active = db.Column(db.Boolean,     nullable=False, default=True)
    created_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MatchRule {self.field_name} method={self.match_method} weight={self.weight}>"
    



#Audit Log ---------------------------------------------------------------------------------------------

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable for system actions
    action = db.Column(db.String(64),  nullable=False)    # e.g. match_approved, user_created
    target_type = db.Column(db.String(64),  nullable=True)     # e.g. match_candidate, user
    target_id = db.Column(db.Integer,     nullable=True)     # ID of the affected object
    detail = db.Column(db.String(512), nullable=True)     # optional human-readable summary
    created_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} target={self.target_type}:{self.target_id}>"