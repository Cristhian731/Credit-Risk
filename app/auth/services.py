"""Authentication service contract.

TODO(teammate B): implement every function marked below. Keep the names,
arguments, return values and exceptions exactly as documented; the routes
already depend on them.

Contract summary:
    * Passwords are hashed with ``werkzeug.security.generate_password_hash``
      and checked with ``check_password_hash``. Plain passwords are never stored.
    * The logged-in user's id lives in ``session["user_id"]``.
    * ``login_required`` stores the current user in ``flask.g.user``.

Fake mode: while the real implementation does not exist, set the ``FAKE_AUTH``
config value (environment variable ``FAKE_AUTH=true``; on by default in
development) and every function answers with a demo user. Fake mode is always
off in testing and production.

The contract is fulfilled when ``tests/test_auth_contract.py`` passes without
its ``xfail`` marker.
"""
from functools import wraps

from flask import current_app, g, session

SESSION_USER_KEY = "user_id"


class _FakeUser:
    """Stand-in for app.models.User used only in fake mode."""

    id = 1
    username = "demo"
    email = "demo@creditrisk.local"
    password_hash = "fake-hash"


FAKE_USER = _FakeUser()


def _fake_auth_enabled():
    return bool(current_app.config.get("FAKE_AUTH", False))


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
    if _fake_auth_enabled():
        return FAKE_USER
    # TODO(teammate B): validate input, hash the password, save the User.
    raise NotImplementedError("register_user is pending (teammate B).")


def authenticate_user(email, password):
    """Check the credentials and, if valid, log the user in.

    Must be called inside a request context. On success the user's id is
    stored in ``session["user_id"]``.

    Args:
        email: Email address the user registered with.
        password: Plain-text password to check against the stored hash.

    Returns:
        The matching ``app.models.User``, or ``None`` if the email is unknown
        or the password is wrong. The session is not modified on failure.
    """
    if _fake_auth_enabled():
        if not email or not password:
            return None
        session[SESSION_USER_KEY] = FAKE_USER.id
        return FAKE_USER
    # TODO(teammate B): look up the user by email and check the password hash.
    raise NotImplementedError("authenticate_user is pending (teammate B).")


def logout_user():
    """Log the current user out by removing ``session["user_id"]``.

    Must be called inside a request context. Calling it when nobody is
    logged in is not an error.
    """
    if _fake_auth_enabled():
        session.pop(SESSION_USER_KEY, None)
        return
    # TODO(teammate B): clear the user from the session.
    raise NotImplementedError("logout_user is pending (teammate B).")


def login_required(view):
    """Decorator that only lets logged-in users reach a view.

    If ``session["user_id"]`` points to an existing user, that user is stored
    in ``flask.g.user`` and the view runs. Otherwise the response is a redirect
    to ``url_for("auth.login", next=request.path)``.
    """

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if _fake_auth_enabled():
            g.user = FAKE_USER
            return view(*args, **kwargs)
        # TODO(teammate B): load the user from the session or redirect to login.
        raise NotImplementedError("login_required is pending (teammate B).")

    return wrapped_view
