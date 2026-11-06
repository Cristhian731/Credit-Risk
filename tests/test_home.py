"""Tests for the home page and the login form contract."""
import re
from html.parser import HTMLParser

import pytest

SECTION_IDS = ["problem", "objective", "how-it-works", "benefits", "technologies"]


class _FormParser(HTMLParser):
    """Collect the login form attributes and its fields."""

    def __init__(self):
        super().__init__()
        self.in_login = False
        self.form = None
        self.fields = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") == "login":
            self.in_login = True
        if not self.in_login:
            return
        if tag == "form":
            self.form = attrs
        elif tag in ("input", "select") and "name" in attrs:
            self.fields[attrs["name"]] = attrs
        elif tag == "a":
            self.links.append(attrs.get("href"))


@pytest.fixture
def home_html(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


@pytest.fixture
def login_card(home_html):
    parser = _FormParser()
    parser.feed(home_html)
    return parser


def test_home_page_has_every_section(home_html):
    for section in SECTION_IDS:
        assert f'id="{section}"' in home_html
    for title in ("The Problem", "Project Objective", "How the Platform Works",
                  "Benefits", "Technologies &amp; Methodology"):
        assert title in home_html


def test_home_page_keeps_hero_text(home_html):
    assert "Credit Risk and Loan Viability Prediction Platform" in home_html
    assert "Smarter lending decisions, powered by Machine Learning." in home_html
    assert "Predict Credit Risk" not in home_html


def test_hero_button_scrolls_to_login(home_html):
    assert re.search(r'<a href="#login"[^>]*>Log in to evaluate a loan</a>', home_html)


def test_navbar_anchors_point_to_existing_sections(home_html):
    for anchor in ("problem", "objective", "how-it-works", "technologies", "login"):
        assert f'href="/#{anchor}"' in home_html
        assert f'id="{anchor}"' in home_html


def test_login_form_posts_to_auth_login(login_card):
    assert login_card.form["method"].upper() == "POST"
    assert login_card.form["action"] == "/auth/login"


@pytest.mark.parametrize("name, field_type", [("email", "email"), ("password", "password"), ("remember", "checkbox")])
def test_login_form_has_contract_field(login_card, name, field_type):
    assert login_card.fields[name]["type"] == field_type


def test_login_form_links_to_register(login_card):
    assert "/auth/register" in login_card.links


def test_submitting_login_shows_not_available_message(client):
    """Placeholder behavior. TODO(teammate B): delete when the real login exists."""
    response = client.post(
        "/auth/login",
        data={"email": "ana@example.com", "password": "secret", "remember": "on"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.request.path == "/"
    assert "Login is not available yet." in response.get_data(as_text=True)
