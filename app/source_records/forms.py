import re
from datetime import date
import phonenumbers
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import Length, Optional, ValidationError, DataRequired


def _simple_email(form, field):
    # Requires local-part @ domain . TLD (at least 2 chars) — catches obvious typos
    if field.data and not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", field.data):
        raise ValidationError("Enter a valid email address (e.g. name@example.com).")


def _name_chars(form, field):
    # Names may contain letters, spaces, hyphens and apostrophes — nothing else
    if field.data and not re.match(r"^[A-Za-z\s'\-\.]+$", field.data):
        raise ValidationError("Only letters, spaces, hyphens, apostrophes and full stops are allowed.")


def _external_id_chars(form, field):
    # External IDs should be alphanumeric with hyphens/underscores only
    if field.data and not re.match(r"^[A-Za-z0-9_\-]+$", field.data):
        raise ValidationError("Only letters, numbers, hyphens and underscores are allowed.")


def _phone_chars(form, field):
    # Parse and validate with the phonenumbers library; normalise to E.164 on success.
    # Defaults to GB if no country code is provided.
    if not field.data:
        return
    try:
        parsed = phonenumbers.parse(field.data, "GB")
    except phonenumbers.NumberParseException:
        raise ValidationError("Enter a valid phone number (e.g. +44 7700 900001 or 07700 900001).")
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("That doesn't look like a valid phone number.")
    # Normalise to E.164 so we store it consistently
    field.data = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


# UK postcode regex — covers all standard formats (SW1A 1AA, EC1A 1BB, W1A 0AX, etc.)
_UK_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][ABD-HJLNP-UW-Z]{2}$",
    re.IGNORECASE,
)


def _postcode_chars(form, field):
    if field.data and not _UK_POSTCODE_RE.match(field.data.strip()):
        raise ValidationError("Enter a valid UK postcode (e.g. SW1A 1AA).")


def _dob_not_future(form, field):
    # Date of birth must be in the past
    if field.data and field.data > date.today():
        raise ValidationError("Date of birth cannot be in the future.")


def _valid_json(form, field):
    # Raw data field should be valid JSON if provided
    import json
    if field.data and field.data.strip():
        try:
            json.loads(field.data)
        except ValueError:
            raise ValidationError("Raw data must be valid JSON.")


class SourceRecordForm(FlaskForm):
    # Used for both creating and editing source records
    source_system_id = SelectField("Source System", coerce=int, validators=[DataRequired()])
    external_id = StringField("External ID", validators=[DataRequired(), Length(max=128), _external_id_chars])
    first_name = StringField("First Name", validators=[Optional(), Length(max=64), _name_chars])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=64), _name_chars])
    email = StringField("Email", validators=[Optional(), _simple_email, Length(max=120)])
    date_of_birth = DateField("Date of Birth", validators=[Optional(), _dob_not_future])
    postcode = StringField("Postcode", validators=[Optional(), Length(max=16), _postcode_chars])
    phone = StringField("Phone", validators=[Optional(), Length(max=32), _phone_chars])
    raw_data = TextAreaField("Raw Data (JSON)", validators=[Optional(), _valid_json])
    submit = SubmitField("Save")

    def validate(self, extra_validators=None):
        # At least one name field must be filled in
        if not super().validate(extra_validators):
            return False
        if not self.first_name.data and not self.last_name.data:
            self.first_name.errors.append("At least one of First Name or Last Name is required.")  # type: ignore[union-attr]
            return False
        return True
