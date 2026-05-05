from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required, login_user, logout_user
from app.auth.forms import LoginForm
from app.models import User

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit(): #inherited from Flask-WTF checks fields are not null
        # Accept either username or email in the username field
        identifier = form.username.data.strip()
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier) # checks both coloums - technically an email can be a username - added to list
        ).first()

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("dashboard.index"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html", form=form)



@auth_bp.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))

