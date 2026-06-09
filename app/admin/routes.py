from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, User
from app.admin.forms import CreateUserForm, EditUserForm

admin_bp = Blueprint("admin", __name__, template_folder="../templates")


@admin_bp.route("/admin/users", methods=["GET"])
@role_required("administrator")
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/admin/users/create", methods=["GET", "POST"])
@role_required("administrator")
def create_user():
    form = CreateUserForm()

    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role=form.role.data,
            is_active=form.is_active.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # populate user.id before the audit log references it
        db.session.add(AuditLog(
            user_id=current_user.id,
            action="user_created",
            target_type="user",
            target_id=user.id,
            detail=f"User '{user.username}' ({user.role}) created by {current_user.username}.",
        ))
        db.session.commit()
        flash(f"User '{user.username}' created successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/create_user.html", form=form)


@admin_bp.route("/admin/users/<int:id>/edit", methods=["GET", "POST"])
@role_required("administrator")
def edit_user(id):
    user = db.session.get(User, id)
    if user is None:
        abort(404)

    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        new_role = form.role.data
        new_active = form.is_active.data

        # Self-protection: cannot remove own admin role
        if user.id == current_user.id and new_role != "administrator":
            flash("You cannot remove your own admin role.", "warning")
            return redirect(url_for("admin.edit_user", id=id))

        # Self-protection: cannot deactivate own account
        if user.id == current_user.id and not new_active:
            flash("You cannot deactivate your own account.", "warning")
            return redirect(url_for("admin.edit_user", id=id))

        # Zero-admin guard: cannot demote the last active admin
        if user.role == "administrator" and new_role != "administrator":
            other_active_admins = User.query.filter(
                User.role == "administrator",
                User.is_active == True,
                User.id != user.id,
            ).count()
            if other_active_admins == 0:
                flash("Cannot change role: this is the only active administrator.", "warning")
                return redirect(url_for("admin.edit_user", id=id))

        # Zero-admin guard: cannot deactivate the last active admin
        if user.role == "administrator" and not new_active:
            other_active_admins = User.query.filter(
                User.role == "administrator",
                User.is_active == True,
                User.id != user.id,
            ).count()
            if other_active_admins == 0:
                flash("Cannot deactivate: this is the only active administrator.", "warning")
                return redirect(url_for("admin.edit_user", id=id))

        changes = []
        if user.role != new_role:
            changes.append(("user_role_changed", f"role: {user.role!r} -> {new_role!r}"))
            user.role = new_role
        if user.is_active != new_active:
            action = "user_deactivated" if not new_active else "user_reactivated"
            changes.append((action, f"active: {user.is_active} -> {new_active}"))
            user.is_active = new_active

        if changes:
            for action, detail_part in changes:
                db.session.add(AuditLog(
                    user_id=current_user.id,
                    action=action,
                    target_type="user",
                    target_id=user.id,
                    detail=f"User '{user.username}': {detail_part}; updated by {current_user.username}.",
                ))
            db.session.commit()
            flash(f"User '{user.username}' updated successfully.", "success")
        else:
            flash("No changes were made.", "info")

        return redirect(url_for("admin.users"))

    return render_template("admin/edit_user.html", form=form, user=user)


@admin_bp.route("/admin/users/<int:id>/deactivate", methods=["POST"])
@role_required("administrator")
def deactivate_user(id):
    user = db.session.get(User, id)
    if user is None:
        abort(404)

    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("admin.users"))

    if not user.is_active:
        flash(f"'{user.username}' is already inactive.", "warning")
        return redirect(url_for("admin.users"))

    # Zero-admin guard
    if user.role == "administrator":
        other_active_admins = User.query.filter(
            User.role == "administrator",
            User.is_active == True,
            User.id != user.id,
        ).count()
        if other_active_admins == 0:
            flash("Cannot deactivate: this is the only active administrator.", "warning")
            return redirect(url_for("admin.users"))

    user.is_active = False
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="user_deactivated",
        target_type="user",
        target_id=user.id,
        detail=f"User '{user.username}' deactivated by {current_user.username}.",
    ))
    db.session.commit()
    flash(f"User '{user.username}' has been deactivated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/admin/users/<int:id>/reactivate", methods=["POST"])
@role_required("administrator")
def reactivate_user(id):
    user = db.session.get(User, id)
    if user is None:
        abort(404)

    if user.is_active:
        flash(f"'{user.username}' is already active.", "warning")
        return redirect(url_for("admin.users"))

    user.is_active = True
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="user_reactivated",
        target_type="user",
        target_id=user.id,
        detail=f"User '{user.username}' reactivated by {current_user.username}.",
    ))
    db.session.commit()
    flash(f"User '{user.username}' has been reactivated.", "success")
    return redirect(url_for("admin.users"))

