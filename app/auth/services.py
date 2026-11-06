"""Authentication service contract.

TODO(teammate B): implement every function marked below. Keep the names,
arguments, return values and exceptions exactly as documented; the routes
already depend on them.

Contract summary:
    * Passwords are hashed with ``werkzeug.security.generate_password_hash``
      and checked with ``check_password_hash``. Plain passwords are never stored.
    * The logged-in user's id lives in ``session["user_id"]``.
    * ``login_required`` stores the current user in ``flask.g.user``.

The ``AUTH_ENABLED`` setting (config.py, environment variable of the same
name) switches between two modes:
    * ``False`` (default): authentication is off. ``login_required`` lets every
      request through and ``get_current_user`` returns DEMO_USER (id=1), so the
      rest of the app works before the real login exists.
    * ``True``: the real implementation below is used.

The contract is fulfilled when ``tests/test_auth_contract.py`` passes without
its ``xfail`` marker.
"""
from functools import wraps

from flask import current_app, g

SESSION_USER_KEY = "user_id"


class _DemoUser:
    """Stand-in for app.models.User while AUTH_ENABLED is False."""

    id = 1
    username = "demo user"
    email = "demo@creditrisk.local"


DEMO_USER = _DemoUser()


def auth_enabled():
    """Return True when the real authentication must be used."""
    return bool(current_app.config.get("AUTH_ENABLED", False))


# TODO(teammate B)
def register_user(username, email, password):
    """Create and persist a new user with a hashed password.

    Args:
        username: Unique display name.
        email: Unique email address, used to log in.
        password: Plain-text password; only its hash is stored.

    Returns:
        The new ``app.models.User``, already committed to the database.

    Raises:
        ValueError: If an argument is empty or the username or email is
            already registered.
    """
    raise NotImplementedError("register_user is pending (teammate B).")


# TODO(teammate B)
def authenticate_user(email, password, remember=False):
    """Check the credentials and, if valid, log the user in.

    Must be called inside a request context. On success the user's id is
    stored in ``session["user_id"]``; with ``remember=True`` the session is
    made permanent.

    Args:
        email: Value of the login form field ``email``.
        password: Value of the login form field ``password``.
        remember: True when the login form checkbox ``remember`` is ticked.

    Returns:
        The matching ``app.models.User``, or ``None`` if the email is unknown
        or the password is wrong. The session is not modified on failure.
    """
    raise NotImplementedError("authenticate_user is pending (teammate B).")


# TODO(teammate B)
def logout_user():
    """Log the current user out by removing ``session["user_id"]``.

    Must be called inside a request context. Calling it when nobody is
    logged in is not an error.
    """
    raise NotImplementedError("logout_user is pending (teammate B).")


def get_current_user():
    """Return the logged-in user, or ``None`` if nobody is logged in.

    With AUTH_ENABLED False it always returns DEMO_USER.
    """
    if not auth_enabled():
        return DEMO_USER
    # TODO(teammate B): load the user whose id is in session["user_id"].
    raise NotImplementedError("get_current_user is pending (teammate B).")


def login_required(view):
    """Decorator that only lets logged-in users reach a view.

    With AUTH_ENABLED False every request passes and ``g.user`` is DEMO_USER.
    With AUTH_ENABLED True: if ``get_current_user()`` returns a user, it is
    stored in ``g.user`` and the view runs; otherwise the response is a
    redirect to ``url_for("auth.login", next=request.path)``.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not auth_enabled():
            g.user = DEMO_USER
            return view(*args, **kwargs)
        # TODO(teammate B): redirect anonymous users to auth.login.
        raise NotImplementedError("login_required is pending (teammate B).")

    return wrapped_view
