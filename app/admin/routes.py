"""Administrator pages. Only an administrator changes roles; nobody can give themselves privileges."""
from flask import abort, flash, redirect, render_template, request, url_for

from ..auth.services import DEMO_EMAIL, roles_required
from ..extensions import db
from ..models import ROLES, User
from . import bp

# Placeholders until block D4 (they already enforce the role).
PLACEHOLDER_ENDPOINTS = {"admin.categories", "admin.monitoring", "admin.reports"}


@bp.route("/")
@roles_required("admin")
def users():
    """List the users with their role and a form to change it."""
    rows = db.session.execute(db.select(User).order_by(User.id)).scalars().all()
    return render_template("admin/users.html", users=rows, roles=ROLES)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@roles_required("admin")
def change_role(user_id):
    """Change the role of a user. The last administrator cannot lose the role."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    role = request.form.get("role", "")
    if role not in ROLES:
        flash("Choose a valid role.", "danger")
        return redirect(url_for("admin.users"))
    if user.email == DEMO_EMAIL and role != "applicant":
        flash("The public demo account is always an applicant.", "danger")
        return redirect(url_for("admin.users"))
    if user.role == "admin" and role != "admin":
        admins = db.session.execute(
            db.select(db.func.count()).select_from(User).filter_by(role="admin")
        ).scalar_one()
        if admins <= 1:
            flash("The last administrator cannot be demoted.", "danger")
            return redirect(url_for("admin.users"))
    user.role = role
    db.session.commit()
    flash(f"{user.username} is now {role}.", "success")
    return redirect(url_for("admin.users"))


def _placeholder(title, block):
    return render_template("placeholder.html", title=title, block=block)


@bp.route("/categories")
@roles_required("admin")
def categories():
    """Category management (block D4)."""
    return _placeholder("Categories", "D4")


@bp.route("/monitoring")
@roles_required("admin")
def monitoring():
    """Monitoring (block D4)."""
    return _placeholder("Monitoring", "D4")


@bp.route("/reports")
@roles_required("admin")
def reports():
    """Reports (block D4)."""
    return _placeholder("Reports", "D4")
