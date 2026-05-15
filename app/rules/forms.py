from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange


class MatchRuleForm(FlaskForm):
    field_name = StringField("Field Name", validators=[DataRequired()])
    match_method = SelectField(
        "Match Method",
        choices=[("exact", "exact"), ("fuzzy", "fuzzy"), ("phonetic", "phonetic"), ("normalised", "normalised")],
        validators=[DataRequired()],
    )
    weight = FloatField(
        "Weight",
        validators=[DataRequired(), NumberRange(min=0, max=1, message="Weight must be between 0 and 1.")],
    )
    is_active = BooleanField("Active")
    submit = SubmitField("Save Changes")
