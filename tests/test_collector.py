from gsis_notifier.collector import (
    _parse_crossref_items,
    _parse_doaj_results,
    _same_title,
    normalize_doi,
)


def test_normalize_doi_rejects_other_journals():
    assert normalize_doi("https://doi.org/10.1080/10095020.2026.12345")
    assert normalize_doi("10.9999/example") == ""


def test_crossref_and_doaj_records_can_be_joined_by_full_doi():
    doi = "10.1080/10095020.2026.2711549"
    crossref = _parse_crossref_items(
        [
            {
                "DOI": doi,
                "title": ["Identifying urban villages"],
                "container-title": ["Geo-spatial Information Science"],
                "published-online": {"date-parts": [[2026, 8, 11]]},
            }
        ]
    )
    doaj = _parse_doaj_results(
        [
            {
                "bibjson": {
                    "identifier": [{"type": "doi", "id": doi}],
                    "journal": {"title": "Geo-spatial Information Science"},
                    "title": "Identifying urban villages",
                    "abstract": "A complete, publisher-supplied abstract.",
                    "keywords": ["Urban villages", "graph neural network"],
                }
            }
        ]
    )

    assert crossref[doi].published_online == "2026-08-11"
    assert doaj[doi].abstract == "A complete, publisher-supplied abstract."
    assert doaj[doi].keywords == ["Urban villages", "graph neural network"]


def test_title_verification_accepts_crossref_inline_subscript_markup():
    crossref = _parse_crossref_items(
        [
            {
                "DOI": "10.1080/10095020.2026.2712868",
                "title": ["Sensitivity of NO <sub>2</sub> to daily activities"],
                "container-title": ["Geo-spatial Information Science"],
            }
        ]
    )
    title = crossref["10.1080/10095020.2026.2712868"].title
    assert title == "Sensitivity of NO2 to daily activities"
    assert _same_title(title, "Sensitivity of NO2 to daily activities")
