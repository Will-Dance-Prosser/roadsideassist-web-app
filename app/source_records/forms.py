import re
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import Length, Optional, ValidationError, DataRequired


def _simple_email(form, field):
    # Lightweight email check to avoid pulling in an external validator just for this
    if field.data and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", field.data):
        raise ValidationError("Enter a valid email address.")


class SourceRecordForm(FlaskForm):
    # Used for both creating and editing source records
    source_system_id = SelectField("Source System", coerce=int, validators=[DataRequired()])
    external_id = StringField("External ID", validators=[DataRequired(), Length(max=128)])
    first_name = StringField("First Name", validators=[Optional(), Length(max=64)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=64)])
    email = StringField("Email", validators=[Optional(), _simple_email, Length(max=120)])
    date_of_birth = DateField("Date of Birth", validators=[Optional()])
    postcode = StringField("Postcode", validators=[Optional(), Length(max=16)])
    phone = StringField("Phone", validators=[Optional(), Length(max=32)])
    raw_data = TextAreaField("Raw Data (JSON)", validators=[Optional()])
    submit = SubmitField("Save")

    def validate(self, extra_validators=None):
        # At least one name field must be filled in
        if not super().validate(extra_validators):
            return False
        if not self.first_name.data and not self.last_name.data:
            self.first_name.errors.append("At least one of First Name or Last Name is required.")  # type: ignore[union-attr]
            return False
        return True
