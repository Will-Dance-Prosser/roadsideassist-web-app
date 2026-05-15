from flask import Blueprint, render_template, redirect, url_for, flash, abort
from app.auth.decorators import role_required
from app.extensions import db
from app.models import MatchRule
from app.rules.forms import MatchRuleForm

rules_bp = Blueprint("rules", __name__, template_folder="../templates")


@rules_bp.route("/rules", methods=["GET"])
@role_required("administrator")
def index():
    # List all match rules ordered by field name
    rules = MatchRule.query.order_by(MatchRule.field_name).all()
    return render_template("rules/index.html", rules=rules)


@rules_bp.route("/rules/<int:id>/edit", methods=["GET", "POST"])
@role_required("administrator")
def edit(id):
    rule = db.session.get(MatchRule, id)
    if rule is None:
        abort(404)

    form = MatchRuleForm(obj=rule)

    if form.validate_on_submit():
        # Duplicate check: same field_name + match_method, excluding this rule
        duplicate = MatchRule.query.filter(
            MatchRule.field_name == form.field_name.data,
            MatchRule.match_method == form.match_method.data,
            MatchRule.id != id,
        ).first()
        if duplicate:
            flash("Another rule already uses that field name and match method combination.", "warning")
            return render_template("rules/edit.html", form=form, rule=rule)

        rule.field_name = form.field_name.data
        rule.match_method = form.match_method.data
        rule.weight = form.weight.data
        rule.is_active = form.is_active.data
        db.session.commit()
        flash(f"Rule '{rule.field_name} ({rule.match_method})' updated successfully.", "success")
        return redirect(url_for("rules.index"))

    return render_template("rules/edit.html", form=form, rule=rule)
