"""Authentication services for Credit Risk."""

from functools import wraps

from flask import (
    abort,
    current_app,
    g,
    redirect,
    request,
    session,
    url_for,
)

from app.models import DEFAULT_ROLE, ROLES

SESSION_USER_KEY = "user_id"

# Same minimum as the minlength of the registration form.
MIN_PASSWORD_LENGTH = 8


# Identity of the demo user. The account is created by ``flask seed-demo`` and
# used while AUTH_ENABLED is False. Its password is DEMO_PASSWORD (public, for the demo only).
DEMO_EMAIL = "demo@creditrisk.local"
DEMO_USERNAME = "demo user"
DEMO_USER_MISSING_MESSAGE = "Demo mode needs the demo user. Run: flask --app run seed-demo"


def auth_enabled():
    """Return True when real authentication must be used."""
    return bool(current_app.config.get("AUTH_ENABLED", False))


def get_demo_user():
    """Return the persisted demo user, or None if ``flask seed-demo`` has not run.

    The demo account is public, so it is only ever an applicant (see ``demo_as_applicant``).
    """

    from app.extensions import db
    from app.models import User

    return db.session.execute(
        db.select(User).filter_by(email=DEMO_EMAIL)
    ).scalar_one_or_none()


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

    if email == DEMO_EMAIL:
        # Reserved: registering it would let a stranger own the demo data.
        raise ValueError("Username or email is already registered.")

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
        return get_demo_user()

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
            g.user = get_demo_user()
            if g.user is None:
                abort(503, description=DEMO_USER_MISSING_MESSAGE)
            return view(*args, **kwargs)

        user = get_current_user()

        if user is None:
            return redirect(
                url_for("auth.login", next=request.path)
            )

        g.user = user

        return view(*args, **kwargs)

    return wrapped_view


# Where each role lands after logging in (endpoint names).
HOME_ENDPOINT_BY_ROLE = {
    "applicant": "dashboard.index",
    "analyst": "reviews.queue",
    "admin": "admin.users",
}


def home_url_for(user):
    """The first page of the private area of ``user``."""
    return url_for(HOME_ENDPOINT_BY_ROLE.get(getattr(user, "role", DEFAULT_ROLE), "dashboard.index"))


def roles_required(*roles):
    """Allow only users with one of ``roles``; the check runs on the server for every request.

    Without a session an HTML request is redirected to the login. With a session but another
    role the answer is a 403 page. With authentication off the user is the demo user, which is
    only an applicant, so staff pages stay closed.
    """
    unknown = set(roles) - set(ROLES)
    if unknown or not roles:
        raise ValueError(f"roles_required needs roles from {ROLES}, got {roles!r}.")

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not auth_enabled():
                user = get_demo_user()
                if user is None:
                    abort(503, description=DEMO_USER_MISSING_MESSAGE)
            else:
                user = get_current_user()
                if user is None:
                    return redirect(url_for("auth.login", next=request.path))
            if user.role not in roles:
                current_app.logger.warning(
                    "403: user %s (%s) tried %s %s", user.id, user.role, request.method, request.path
                )
                abort(403)
            g.user = user
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def upsert_account(email, password, role, username=None):
    """Create or update an account with a role. Returns ``(user, created)``.

    Used only by the command line and the start-up bootstrap: the web never calls it. An existing
    account keeps its data; its password and role are set to the given values, so running it again
    never duplicates anything. The reserved demo address is refused: it is always an applicant.
    """
    from app.extensions import db
    from app.models import User

    if role not in ROLES:
        raise ValueError(f"Role must be one of {ROLES}.")
    if not isinstance(email, str) or not email.strip():
        raise ValueError("An email is required.")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.")
    email = email.strip().lower()
    if email == DEMO_EMAIL:
        raise ValueError("The demo account is reserved and can only be an applicant.")

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    created = user is None
    if created:
        base = (username or email.split("@")[0]).strip() or "user"
        name, n = base, 1
        while db.session.execute(db.select(User).filter_by(username=name)).scalar_one_or_none():
            n += 1
            name = f"{base}{n}"
        user = User(username=name, email=email)
        db.session.add(user)
    user.set_password(password)
    user.role = role
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return user, created


def bootstrap_accounts(environ):
    """Create or update the accounts named by BOOTSTRAP_* variables. Returns a list of ``(role, email, created)``.

    BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD and BOOTSTRAP_ANALYST_EMAIL /
    BOOTSTRAP_ANALYST_PASSWORD (Render's free plan has no shell). A role is skipped when its
    email or password is missing. The values live only in the environment.
    """
    done = []
    for role in ("admin", "analyst"):
        prefix = f"BOOTSTRAP_{role.upper()}"
        email = (environ.get(f"{prefix}_EMAIL") or "").strip()
        password = environ.get(f"{prefix}_PASSWORD") or ""
        if not email or not password:
            continue
        user, created = upsert_account(email, password, role, username=f"{role} account")
        done.append((role, user.email, created))
    return done
