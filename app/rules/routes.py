from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, MatchRule
from app.rules.forms import ALL_METHODS, FIELD_METHODS, MatchRuleForm
from app.services.match_scoring import recalculate_all_candidate_scores

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
            return render_template("rules/edit.html", form=form, rule=rule,
                                   field_methods=FIELD_METHODS, all_methods=ALL_METHODS)

        # Capture changes before overwriting
        changes = []
        if rule.field_name != form.field_name.data:
            changes.append(f"field_name: {rule.field_name!r} -> {form.field_name.data!r}")
        if rule.match_method != form.match_method.data:
            changes.append(f"match_method: {rule.match_method!r} -> {form.match_method.data!r}")
        if rule.weight != form.weight.data:
            changes.append(f"weight: {rule.weight} -> {form.weight.data}")
        if rule.is_active != form.is_active.data:
            changes.append(f"active: {rule.is_active} -> {form.is_active.data}")

        rule.field_name = form.field_name.data
        rule.match_method = form.match_method.data
        rule.weight = form.weight.data
        rule.is_active = form.is_active.data
        db.session.commit()
        recalculate_all_candidate_scores()
        change_summary = "; ".join(changes) if changes else "no changes"
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="match_rule_updated",
            target_type="match_rule",
            target_id=rule.id,
            detail=(
                f"Rule {rule.field_name}/{rule.match_method} updated by {current_user.username}:"
                f" {change_summary}; pending match scores recalculated"
            ),
        ))
        db.session.commit()
        flash(f"Rule '{rule.field_name} ({rule.match_method})' updated successfully.", "success")
        return redirect(url_for("rules.index"))

    return render_template("rules/edit.html", form=form, rule=rule,
                           field_methods=FIELD_METHODS, all_methods=ALL_METHODS)
