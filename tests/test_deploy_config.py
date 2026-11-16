"""The Render Blueprint (render.yaml) and the start-up commands it relies on."""
import os
import re

from app.auth.services import DEMO_EMAIL
from app.models import User
from config import PROJECT_ROOT

BLUEPRINT = os.path.join(PROJECT_ROOT, "render.yaml")


def blueprint():
    with open(BLUEPRINT, encoding="utf-8") as fh:
        return fh.read()


def start_command():
    return re.search(r"^\s*startCommand: (.+)$", blueprint(), re.MULTILINE).group(1)


def test_both_the_service_and_the_database_use_the_free_plan():
    assert len(re.findall(r"^\s*plan: free$", blueprint(), re.MULTILINE)) == 2


def test_the_python_version_is_fully_qualified_and_in_the_ci_line():
    version = re.search(r"key: PYTHON_VERSION\s+value: (\S+)", blueprint()).group(1)
    assert re.fullmatch(r"3\.14\.\d+", version)
    with open(os.path.join(PROJECT_ROOT, ".github", "workflows", "tests.yml"), encoding="utf-8") as fh:
        assert 'python-version: "3.14"' in fh.read()


def test_the_start_command_migrates_seeds_and_serves_with_one_worker():
    command = start_command()
    steps = [
        "flask --app run db upgrade",
        "flask --app run seed-demo",
        "flask --app run bootstrap-accounts",
        "gunicorn --workers 1 --timeout 120",
    ]
    positions = [command.index(step) for step in steps]
    assert positions == sorted(positions)
    assert command.count("&&") == 3
    assert command.rstrip().endswith("run:app")


def test_the_build_installs_the_pinned_requirements():
    assert "buildCommand: pip install -r requirements.txt" in blueprint()


def test_the_environment_is_production_and_secrets_are_not_in_the_file():
    text = blueprint()
    assert re.search(r"key: FLASK_CONFIG\s+value: production", text)
    assert re.search(r"key: SECRET_KEY\s+generateValue: true", text)
    assert re.search(r"key: DATABASE_URL\s+fromDatabase:\s+name: credit-risk-db\s+property: connectionString", text)
    # The demo password is typed in the dashboard: sync: false and no value.
    assert re.search(r"key: DEMO_PASSWORD\s+sync: false", text)
    assert "demo-password" not in text
    assert not re.search(r"postgres(ql)?://", text)


def test_seed_demo_can_run_every_start_and_only_updates_the_password(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    app.config["DEMO_PASSWORD"] = "another-password-2027"
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    assert "Demo user already exists." in result.output
    users = User.query.filter_by(email=DEMO_EMAIL).all()
    assert len(users) == 1
    assert users[0].check_password("another-password-2027")
    assert not users[0].check_password("demo-password-2026")


def test_env_example_lists_every_variable_and_holds_no_secret():
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    text = open(os.path.join(root, ".env.example"), encoding="utf-8").read()
    names = set(re.findall(r"^([A-Z_]+)=", text, re.M))
    for name in ("FLASK_CONFIG", "SECRET_KEY", "DATABASE_URL", "AUTH_ENABLED", "DEMO_PASSWORD",
                 "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD", "BOOTSTRAP_ANALYST_EMAIL",
                 "BOOTSTRAP_ANALYST_PASSWORD", "TEST_DATABASE_URL", "PREDICTION_LOG_PATH"):
        assert name in names, name
    for line in text.splitlines():
        if re.match(r"^[A-Z_]*(PASSWORD|SECRET_KEY)=", line):
            assert line.split("=", 1)[1].startswith("change-me"), line  # only visible placeholders
    assert not re.search(r"postgres(ql)?://\w+:\w+@", text)
