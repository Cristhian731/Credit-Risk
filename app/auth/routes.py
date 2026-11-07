
"""Authentication routes for Credit Risk."""

from flask import flash, redirect, render_template, request, url_for

from . import bp
from .services import (
    authenticate_user,
    auth_enabled,
    logout_user,
    register_user,
)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user using the home page login form."""

    if not auth_enabled():
        flash("Authentication is currently disabled.", "info")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = authenticate_user(email, password, remember)

        if user is None:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("main.index", _anchor="login"))

        flash("You have successfully logged in.", "success")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)

        return redirect(url_for("main.index"))

    return redirect(url_for("main.index", _anchor="login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user account."""

    if not auth_enabled():
        flash("Registration is currently disabled.", "info")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        try:
            register_user(username, email, password)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("auth.register"))

        flash("Your account has been created. You can now log in.", "success")
        return redirect(url_for("main.index", _anchor="login"))

    return render_template("auth/register.html")


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Log out the current user."""

    logout_user()
    flash("You have successfully logged out.", "success")

    return redirect(url_for("main.index"))
