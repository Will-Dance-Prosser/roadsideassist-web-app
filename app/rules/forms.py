from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, ValidationError

# Valid match methods per field — phonetic is not implemented in the scoring engine
FIELD_METHODS = {
    "email":         ["exact", "fuzzy"],
    "first_name":    ["exact", "fuzzy"],
    "last_name":     ["exact", "fuzzy"],
    "phone":         ["normalised", "exact"],
    "postcode":      ["normalised", "exact"],
    "date_of_birth": ["exact"],
}

ALL_METHODS = ["exact", "fuzzy", "normalised"]


class MatchRuleForm(FlaskForm):
    field_name = SelectField(
        "Field Name",
        choices=[(f, f) for f in FIELD_METHODS],
        validators=[DataRequired()],
    )
    match_method = SelectField(
        "Match Method",
        choices=[(m, m) for m in ALL_METHODS],
        validators=[DataRequired()],
    )
    weight = FloatField(
        "Weight",
        validators=[DataRequired(), NumberRange(min=0, max=1, message="Weight must be between 0 and 1.")],
    )
    is_active = BooleanField("Active")
    submit = SubmitField("Save Changes")

    def validate_match_method(self, field):
        allowed = FIELD_METHODS.get(self.field_name.data, ALL_METHODS)
        if field.data not in allowed:
            raise ValidationError(
                f"'{field.data}' is not supported for '{self.field_name.data}'. "
                f"Allowed: {', '.join(allowed)}."
            )
