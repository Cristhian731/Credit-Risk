"""Authentication services for Credit Risk."""

from functools import wraps

from flask import (
    current_app,
    g,
    redirect,
    request,
    session,
    url_for,
)

SESSION_USER_KEY = "user_id"

# Same minimum as the minlength of the registration form.
MIN_PASSWORD_LENGTH = 8


class _DemoUser:
    """Stand-in for app.models.User while AUTH_ENABLED is False."""

    id = 1
    username = "demo user"
    email = "demo@creditrisk.local"


DEMO_USER = _DemoUser()


def auth_enabled():
    """Return True when real authentication must be used."""
    return bool(current_app.config.get("AUTH_ENABLED", False))


def register_user(username, email, password):
    """Create and persist a new user with a hashed password."""

    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models import User

    if (
        not isinstance(username, str) or not username.strip()
        or not isinstance(email, str) or not email.strip()
        or not isinstance(password, str) or not password.strip()
    ):
        raise ValueError("Username, email and password are required.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    username = username.strip()
    email = email.strip().lower()

    existing_username = db.session.execute(
        db.select(User).filter_by(username=username)
    ).scalar_one_or_none()

    existing_email = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()

    if existing_username or existing_email:
        raise ValueError("Username or email is already registered.")

    user = User(
        username=username,
        email=email,
    )
    user.set_password(password)

    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Username or email is already registered.")

    return user


def authenticate_user(email, password, remember=False):
    """Validate credentials and create an authenticated session."""

    from app.extensions import db
    from app.models import User

    if not isinstance(email, str) or not isinstance(password, str):
        return None

    email = email.strip().lower()

    user = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()

    if user is None or not user.check_password(password):
        return None

    session[SESSION_USER_KEY] = user.id
    session.permanent = bool(remember)

    return user


def logout_user():
    """Remove the authenticated user from the session."""

    session.pop(SESSION_USER_KEY, None)


def get_current_user():
    """Return the logged-in user or None."""

    if not auth_enabled():
        return DEMO_USER

    from app.extensions import db
    from app.models import User

    user_id = session.get(SESSION_USER_KEY)

    if user_id is None:
        return None

    return db.session.get(User, user_id)


def login_required(view):
    """Protect a view from unauthenticated requests."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if not auth_enabled():
            g.user = DEMO_USER
            return view(*args, **kwargs)

        user = get_current_user()

        if user is None:
            return redirect(
                url_for("auth.login", next=request.path)
            )

        g.user = user

        return view(*args, **kwargs)

    return wrapped_view
