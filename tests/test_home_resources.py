"""Home documentation (PGC), Resources, the manual page and the video link."""
import pytest

SECTIONS = ["pgc-title", "pgc-problem", "pgc-general", "pgc-specific", "pgc-framework",
            "pgc-methodology", "pgc-references"]


def test_home_has_the_full_documentation_and_a_contents_list(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-testid="pgc-toc"' in html
    for section in SECTIONS:
        assert f'id="{section}"' in html
    assert 'data-testid="schedule"' in html
    for old in ("The Problem", "Project Objective", ">Benefits<"):
        assert old not in html


def test_home_has_quick_access_and_no_video_message(client, monkeypatch):
    monkeypatch.delenv("VIDEO_URL", raising=False)
    html = client.get("/").get_data(as_text=True)
    assert 'data-testid="quick-access"' in html
    assert "Video: link pending" in html


@pytest.mark.parametrize("url, expected", [
    ("https://youtu.be/abcdefghijk", "youtube-nocookie.com/embed/abcdefghijk"),
    ("https://www.youtube.com/watch?v=abcdefghijk", "youtube-nocookie.com/embed/abcdefghijk"),
    ("https://vimeo.com/123456", "player.vimeo.com/video/123456"),
])
def test_video_url_is_embedded(client, monkeypatch, url, expected):
    monkeypatch.setenv("VIDEO_URL", url)
    assert expected in client.get("/").get_data(as_text=True)
    assert expected in client.get("/resources").get_data(as_text=True)


def test_other_video_urls_are_links_and_unsafe_ones_are_ignored(client, monkeypatch):
    monkeypatch.setenv("VIDEO_URL", "https://example.com/video")
    assert 'data-testid="video-link"' in client.get("/resources").get_data(as_text=True)
    monkeypatch.setenv("VIDEO_URL", "javascript:alert(1)")
    assert "Video: link pending" in client.get("/resources").get_data(as_text=True)


@pytest.mark.parametrize("path", ["/", "/resources", "/manual", "/methodology/"])
def test_public_pages_answer_200(client, path):
    assert client.get(path).status_code == 200


def test_resources_link_the_published_documents_and_evidence(client):
    html = client.get("/resources").get_data(as_text=True)
    assert "Activity1_Technical_Report.pdf" in html
    assert "Activity2_System_Report.pdf" in html
    assert "credit_risk_clustering.ipynb" in html and "credit_risk_dimensionality.ipynb" in html
    assert "github.com/Cristhian731/Credit-Risk" in html


def test_manual_is_a_readable_page(client):
    html = client.get("/manual").get_data(as_text=True)
    assert "User Manual" in html and "Getting started" in html
    assert "img/manual/figure_01.png" in html
