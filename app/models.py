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
