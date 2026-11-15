"""The home page shows the project documentation (PGC) as readable page content, not only as a file."""
import pytest

PGC_IDS = ["pgc-title", "pgc-problem", "pgc-objectives", "pgc-framework", "pgc-methodology", "pgc-references"]


@pytest.fixture
def home(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_home_has_every_pgc_section(home):
    for section in PGC_IDS:
        assert f'id="{section}"' in home
    for text in ("General objective", "Specific objectives", "Reference framework",
                 "Methodology and development schedule", "Bibliographic references"):
        assert text in home


def test_home_lists_the_six_phases_and_the_schedule(home):
    assert home.count("/methodology/phase") >= 6
    assert 'data-testid="schedule"' in home and "Responsible" in home and "Planned" in home and "Actual" in home


def test_home_cites_the_sources_of_the_framework(home):
    for author in ("Lessmann et al., 2015", "Dastile et al., 2020", "Bussmann et al., 2021"):
        assert author in home
    assert "https://doi.org/10.1016/j.ejor.2015.05.030" in home


def test_home_is_public_and_links_the_resources(home):
    assert 'href="/resources"' in home


def test_reference_framework_document_is_written():
    text = open("docs/pgc/reference_framework.md", encoding="utf-8").read()
    assert "> Guide:" not in text
    assert "Lessmann" in text and "Key concepts" in text
