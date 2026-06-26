import re
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp, ValidationError


def _simple_email(form, field):
    if field.data and not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", field.data):
        raise ValidationError("Enter a valid email address (e.g. name@example.com).")


class CreateUserForm(FlaskForm):
    username = StringField("Username", validators=[
        DataRequired(),
        Length(max=64),
        Regexp(r'^[a-zA-Z0-9_\-]+$', message="Username may only contain letters, numbers, hyphens, and underscores."),
    ])
    email = StringField("Email", validators=[DataRequired(), Length(max=120), _simple_email])
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")],
    )
    role = SelectField(
        "Role",
        choices=[
            ("administrator", "Administrator"),
            ("data_steward", "Data Steward"),
            ("data_analyst", "Data Analyst"),
        ],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Create User")

    def validate_username(self, field):
        from app.models import User
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("That username is already taken.")

    def validate_email(self, field):
        from app.models import User
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("That email address is already registered.")


class EditUserForm(FlaskForm):
    role = SelectField(
        "Role",
        choices=[
            ("administrator", "Administrator"),
            ("data_steward", "Data Steward"),
            ("data_analyst", "Data Analyst"),
        ],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active")
    submit = SubmitField("Save Changes")
