"""Tests for the roles: registration, authorization on every route, menus, role changes and the command line."""
import re

import pytest
from click.testing import CliRunner
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from app import create_app
from app.auth.services import bootstrap_accounts, register_user, roles_required, upsert_account
from app.extensions import db
from app.menus import MENU_BY_ROLE
from app.models import ROLES, User
from config import TestingConfig

PASSWORD = "correct-horse-battery"

ANON, APPLICANT, ANALYST, ADMIN = "anonymous", "applicant", "analyst", "admin"

# route -> who may open it (everyone else gets the login redirect or a 403).
PUBLIC = [
    "/", "/resources", "/credit/models/", "/methodology/", "/methodology/phase-1",
]
APPLICANT_ONLY = ["/dashboard/", "/transactions/", "/transactions/new", "/credit/", "/credit/history"]
STAFF = ["/reviews/", "/reviews/history", "/reviews/indicators"]
ADMIN_ONLY = ["/admin/", "/admin/categories", "/admin/monitoring", "/admin/reports", "/admin/reports/decisions.csv"]

ALLOWED = {
    **{path: {ANON, APPLICANT, ANALYST, ADMIN} for path in PUBLIC},
    **{path: {APPLICANT} for path in APPLICANT_ONLY},
    **{path: {ANALYST, ADMIN} for path in STAFF},
    **{path: {ADMIN} for path in ADMIN_ONLY},
}


@pytest.fixture
def clients(app, analyst_client, admin_client, applicant_client):
    """One test client per role; the anonymous one has no session."""
    return {ANON: app.test_client(), APPLICANT: applicant_client, ANALYST: analyst_client, ADMIN: admin_client}


# Access matrix: every route x every role

@pytest.mark.parametrize("path", sorted(ALLOWED))
@pytest.mark.parametrize("role", [ANON, APPLICANT, ANALYST, ADMIN])
def test_each_role_only_opens_its_pages(clients, path, role):
    response = clients[role].get(path)
    if role in ALLOWED[path]:
        assert response.status_code == 200, f"{role} should open {path}"
    elif role == ANON:
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/auth/login")
    else:
        assert response.status_code == 403, f"{role} must not open {path}"


def test_the_old_result_address_follows_the_same_rule(clients):
    assert clients[APPLICANT].get("/credit/result").status_code == 302
    assert clients[ANON].get("/credit/result").headers["Location"].startswith("/auth/login")
    assert clients[ANALYST].get("/credit/result").status_code == 403


def test_the_403_page_uses_the_layout_of_the_app(clients):
    html = clients[APPLICANT].get("/admin/").get_data(as_text=True)
    assert "Access denied" in html
    assert 'data-testid="sidebar"' in html and "Back to my home" in html


def test_every_private_route_is_covered_by_the_matrix(app):
    """A new route that needs a role must be added to ALLOWED, so it cannot ship without a test."""
    private_prefixes = ("/dashboard", "/transactions", "/credit", "/reviews", "/admin")
    covered = set(ALLOWED) | {"/credit/result"}  # the old address redirects: tested below
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(private_prefixes) and "GET" in rule.methods and not rule.arguments:
            assert rule.rule in covered or rule.rule.rstrip("/") + "/" in covered or rule.rule.rstrip("/") in covered, (
                f"{rule.rule} is not in the access matrix of tests/test_roles.py"
            )


def test_staff_post_routes_reject_applicants_and_anonymous(clients):
    assert clients[APPLICANT].post("/credit/models/xgboost/predict", data={}).status_code == 403
    assert clients[ANON].post("/credit/models/xgboost/predict", data={}).status_code == 302
    assert clients[APPLICANT].post("/admin/users/1/role", data={"role": "admin"}).status_code == 403
    assert clients[ANALYST].post("/admin/users/1/role", data={"role": "admin"}).status_code == 403


def test_applicant_data_is_not_open_to_staff(clients):
    for role in (ANALYST, ADMIN):
        assert clients[role].get("/transactions/").status_code == 403
        assert clients[role].get("/credit/history").status_code == 403


def test_roles_required_rejects_unknown_roles():
    with pytest.raises(ValueError):
        roles_required("root")
    with pytest.raises(ValueError):
        roles_required()


# Registration and role changes

def test_registration_always_creates_an_applicant(app, client):
    app.config["AUTH_ENABLED"] = True
    user = register_user("ana", "ana@example.com", PASSWORD)
    assert user.role == "applicant"


@pytest.mark.parametrize("role", ["admin", "analyst"])
def test_registration_form_ignores_a_role_sent_by_the_user(app, client, role):
    app.config["AUTH_ENABLED"] = True
    client.post(
        "/auth/register",
        data={"username": "mallory", "email": "m@example.com", "password": PASSWORD, "role": role},
    )
    user = db.session.execute(db.select(User).filter_by(email="m@example.com")).scalar_one()
    assert user.role == "applicant"


def test_register_user_has_no_role_parameter():
    with pytest.raises(TypeError):
        register_user("x", "x@example.com", PASSWORD, role="admin")


def test_an_admin_changes_a_role(clients, app):
    applicant = db.session.execute(db.select(User).filter_by(email="applicant@example.com")).scalar_one()
    response = clients[ADMIN].post(f"/admin/users/{applicant.id}/role", data={"role": "analyst"})
    assert response.status_code == 302
    db.session.refresh(applicant)
    assert applicant.role == "analyst"


def test_nobody_can_give_themselves_privileges(clients):
    me = db.session.execute(db.select(User).filter_by(email="applicant@example.com")).scalar_one()
    assert clients[APPLICANT].post(f"/admin/users/{me.id}/role", data={"role": "admin"}).status_code == 403
    db.session.refresh(me)
    assert me.role == "applicant"


def test_an_invalid_role_is_refused(clients):
    applicant = db.session.execute(db.select(User).filter_by(email="applicant@example.com")).scalar_one()
    clients[ADMIN].post(f"/admin/users/{applicant.id}/role", data={"role": "root"})
    db.session.refresh(applicant)
    assert applicant.role == "applicant"


def test_the_last_administrator_cannot_be_demoted(clients):
    admin = db.session.execute(db.select(User).filter_by(email="admin@example.com")).scalar_one()
    clients[ADMIN].post(f"/admin/users/{admin.id}/role", data={"role": "applicant"})
    db.session.refresh(admin)
    assert admin.role == "admin"


def test_an_administrator_can_be_demoted_when_another_exists(clients):
    upsert_account("second@example.com", PASSWORD, "admin")
    admin = db.session.execute(db.select(User).filter_by(email="admin@example.com")).scalar_one()
    clients[ADMIN].post(f"/admin/users/{admin.id}/role", data={"role": "applicant"})
    db.session.refresh(admin)
    assert admin.role == "applicant"


def test_the_role_column_only_accepts_known_roles(app):
    user = User(username="x", email="x@example.com")
    with pytest.raises(ValueError):
        user.role = "root"


# The demo account is public: always an applicant

def test_the_demo_user_is_an_applicant_and_staff_pages_stay_closed(client, demo_user):
    assert demo_user.role == "applicant"
    assert client.get("/dashboard/").status_code == 200
    assert client.get("/reviews/").status_code == 403
    assert client.get("/admin/").status_code == 403


def test_the_demo_user_loses_any_other_role_when_it_is_seeded_again(demo_user):
    from app.seed import ensure_demo_user

    demo_user.role = "admin"
    db.session.commit()
    user, _created = ensure_demo_user()
    assert user.role == "applicant"


def test_the_demo_account_cannot_be_made_staff(app):
    from app.auth.services import DEMO_EMAIL

    with pytest.raises(ValueError):
        upsert_account(DEMO_EMAIL, PASSWORD, "admin")


# Menus

def _sidebar_labels(html):
    nav = re.search(r'<nav class="app-sidebar".*?</nav>', html, re.DOTALL).group(0)
    return [label.strip() for label in re.findall(r'class="nav-link[^"]*"[^>]*>([^<]+)<', nav)]


@pytest.mark.parametrize("role", [APPLICANT, ANALYST, ADMIN])
def test_the_sidebar_lists_the_pages_of_the_role(clients, role):
    html = clients[role].get("/credit/models/").get_data(as_text=True)
    assert _sidebar_labels(html) == [label for _endpoint, label in MENU_BY_ROLE[role]]


def test_every_menu_item_of_a_role_opens_for_that_role(app, clients):
    from flask import url_for

    for role in ROLES:
        for endpoint, _label in MENU_BY_ROLE[role]:
            with app.test_request_context():
                path = url_for(endpoint)
            assert clients[role].get(path).status_code == 200, f"{role} cannot open its menu item {endpoint}"


def test_the_public_menu_has_no_private_pages(clients):
    html = clients[ANON].get("/").get_data(as_text=True)
    assert 'data-testid="sidebar"' not in html
    for label in ("Home", "Methodology", "Models", "Resources", "Log in", "Register"):
        assert label in html


def test_each_role_lands_on_its_own_home_after_login(app):
    app.config["AUTH_ENABLED"] = True
    expected = {APPLICANT: "/dashboard/", ANALYST: "/reviews/", ADMIN: "/admin/"}
    for role, location in expected.items():
        upsert_account(f"{role}@example.com", PASSWORD, role)
        response = app.test_client().post("/auth/login", data={"email": f"{role}@example.com", "password": PASSWORD})
        assert response.headers["Location"] == location


# Command line and start-up bootstrap

@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def test_create_user_reads_the_password_from_the_environment(runner, monkeypatch, app):
    monkeypatch.setenv("NEW_USER_PASSWORD", PASSWORD)
    result = runner.invoke(args=["create-user", "--role", "admin", "--email", "Boss@Example.com"])
    assert result.exit_code == 0, result.output
    user = db.session.execute(db.select(User).filter_by(email="boss@example.com")).scalar_one()
    assert user.role == "admin" and user.check_password(PASSWORD)
    assert PASSWORD not in result.output


def test_create_user_has_no_password_argument(runner):
    result = runner.invoke(args=["create-user", "--role", "admin", "--email", "a@example.com", "--password", "x"])
    assert result.exit_code != 0


def test_create_user_fails_without_the_environment_variable(runner, monkeypatch):
    monkeypatch.delenv("NEW_USER_PASSWORD", raising=False)
    result = runner.invoke(args=["create-user", "--role", "analyst", "--email", "a@example.com"])
    assert result.exit_code != 0
    assert db.session.execute(db.select(User).filter_by(email="a@example.com")).scalar_one_or_none() is None


def test_create_user_rejects_a_short_password(runner, monkeypatch):
    monkeypatch.setenv("NEW_USER_PASSWORD", "short")
    assert runner.invoke(args=["create-user", "--role", "analyst", "--email", "a@example.com"]).exit_code != 0


def test_create_user_is_idempotent_and_updates_password_and_role(runner, monkeypatch):
    monkeypatch.setenv("NEW_USER_PASSWORD", PASSWORD)
    runner.invoke(args=["create-user", "--role", "analyst", "--email", "a@example.com"])
    monkeypatch.setenv("NEW_USER_PASSWORD", "another-password-2027")
    result = runner.invoke(args=["create-user", "--role", "admin", "--email", "a@example.com"])
    assert "Updated" in result.output
    users = db.session.execute(db.select(User).filter_by(email="a@example.com")).scalars().all()
    assert len(users) == 1 and users[0].role == "admin" and users[0].check_password("another-password-2027")


def test_bootstrap_creates_admin_and_analyst_from_the_environment(app):
    env = {
        "BOOTSTRAP_ADMIN_EMAIL": "root@example.com", "BOOTSTRAP_ADMIN_PASSWORD": PASSWORD,
        "BOOTSTRAP_ANALYST_EMAIL": "ana@example.com", "BOOTSTRAP_ANALYST_PASSWORD": PASSWORD,
    }
    assert [(role, created) for role, _email, created in bootstrap_accounts(env)] == [("admin", True), ("analyst", True)]
    assert bootstrap_accounts(env) == [("admin", "root@example.com", False), ("analyst", "ana@example.com", False)]
    assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 2


def test_bootstrap_updates_the_password_and_role_without_duplicating(app):
    upsert_account("root@example.com", "old-password-2025", "applicant")
    bootstrap_accounts({"BOOTSTRAP_ADMIN_EMAIL": "root@example.com", "BOOTSTRAP_ADMIN_PASSWORD": PASSWORD})
    users = db.session.execute(db.select(User)).scalars().all()
    assert len(users) == 1 and users[0].role == "admin" and users[0].check_password(PASSWORD)


def test_bootstrap_skips_a_role_with_a_missing_value(app):
    assert bootstrap_accounts({"BOOTSTRAP_ADMIN_EMAIL": "root@example.com"}) == []
    assert bootstrap_accounts({}) == []
    assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 0


def test_the_bootstrap_command_runs_without_variables(runner, monkeypatch):
    for name in ("ADMIN", "ANALYST"):
        monkeypatch.delenv(f"BOOTSTRAP_{name}_EMAIL", raising=False)
    result = runner.invoke(args=["bootstrap-accounts"])
    assert result.exit_code == 0 and "No BOOTSTRAP_* accounts" in result.output


# Migration 0003

@pytest.fixture
def migrated_app(tmp_path, monkeypatch):
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'roles.db'}")
    application = create_app("testing")
    with application.app_context():
        yield application
        db.session.remove()
        db.engine.dispose()


def test_the_migration_gives_existing_users_the_applicant_role_and_can_be_reversed(migrated_app):
    upgrade(revision="0002")
    db.session.execute(
        text("INSERT INTO users (username, email, password_hash, created_at) VALUES ('old', 'old@example.com', 'x', '2026-01-01')")
    )
    db.session.commit()
    upgrade()
    assert db.session.execute(text("SELECT role FROM users")).scalar_one() == "applicant"
    with pytest.raises(Exception):
        db.session.execute(text("UPDATE users SET role = 'root'"))
        db.session.commit()
    db.session.rollback()
    downgrade(revision="0002")
    assert "role" not in {column["name"] for column in inspect(db.engine).get_columns("users")}
    assert db.session.execute(text("SELECT email FROM users")).scalar_one() == "old@example.com"


# Temporary pages

def test_no_placeholder_page_remains():
    from app.admin.routes import PLACEHOLDER_ENDPOINTS as admin_placeholders
    from app.reviews.routes import PLACEHOLDER_ENDPOINTS as review_placeholders

    assert admin_placeholders | review_placeholders == set()
