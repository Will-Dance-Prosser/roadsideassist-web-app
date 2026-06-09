from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user
from app.auth.decorators import role_required
from app.extensions import db
from app.models import AuditLog, User
from app.admin.forms import CreateUserForm

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
