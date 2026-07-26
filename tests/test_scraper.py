import pytest

import scraper
from scraper import (
    ScraperError,
    fetch_pal_image_urls,
    fetch_pal_titles,
    fetch_pal_wikitext,
    parse_pal_wikitext,
)


PAL_WIKITEXT = """
{{Pal Navigation}}
{{Pal
|no = 001b
|alpha_title = Big Floof
|ele1 = Neutral
|ele2 = Dark
|partner_skill_name = Fluffy Shield
|partner_skill_desc = Becomes a [[Wool|woolly shield]] with {{i|Grass}} power.
|work_suitability = Handiwork@2; Mining@1
<!-- Basics -->
|hunger = 2
<!-- Skills -->
|active_skills = Roly Poly@1; Holy Burst@70
<!-- Stats -->
|hp = 70
|attack = 80
|defense = 90
}}
{{Palpedia|A round and woolly Pal.}}
==Drops==
{{Item Drop
|target_name = Lamball
|normal_drops = Wool*1-3@100; Lamball Mutton*1@60
|alpha_drops = Ring +1*1@2.5
}}
"""


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


def test_parse_pal_wikitext_builds_complete_record():
    record = parse_pal_wikitext("Lamball", "001B", PAL_WIKITEXT)

    assert record == {
        "name": "Lamball",
        "id": "001B",
        "element": [
            {"name": "Dark", "id": "dark"},
            {"name": "Neutral", "id": "neutral"},
        ],
        "suitability": [
            {"id": "handiwork", "name": "Handiwork", "level": 2},
            {"id": "mining", "name": "Mining", "level": 1},
        ],
        "alphaTitle": "Big Floof",
        "image": "https://paldeck.pages.dev/images/pals/001B",
        "stats": {"hp": "70", "attack": "80", "defense": "90"},
        "description": "A round and woolly Pal.",
        "partnerSkill": {
            "name": "Fluffy Shield",
            "description": "Becomes a woolly shield with Grass power.",
            "id": "fluffy_shield",
        },
        "activeSkills": [
            {"name": "Roly Poly", "level": 1, "id": "roly_poly"},
            {"name": "Holy Burst", "level": 70, "id": "holy_burst"},
        ],
        "possibleDrops": [
            {
                "name": "Wool",
                "id": "wool",
                "amount": "1-3",
                "dropRate": 100,
                "dropType": "regular",
            },
            {
                "name": "Lamball Mutton",
                "id": "lamball_mutton",
                "amount": "1",
                "dropRate": 60,
                "dropType": "regular",
            },
            {
                "name": "Ring +1",
                "id": "ring_1",
                "amount": "1",
                "dropRate": 2.5,
                "dropType": "alpha",
            },
        ],
        "food": 2,
    }


def test_parse_pal_wikitext_rejects_id_mismatch():
    with pytest.raises(ScraperError, match="ID mismatch"):
        parse_pal_wikitext("Lamball", "999", PAL_WIKITEXT)


def test_parse_pal_wikitext_rejects_missing_pal_template():
    with pytest.raises(ScraperError, match="no Pal template"):
        parse_pal_wikitext("Lamball", "001", "{{Palpedia|Description}}")


def test_parse_pal_wikitext_preserves_incomplete_source_fields():
    incomplete = (
        PAL_WIKITEXT.replace(
            "|partner_skill_name = Fluffy Shield",
            "|partner_skill_name =",
        )
        .replace(
            "|active_skills = Roly Poly@1; Holy Burst@70",
            "|active_skills =",
        )
        .replace("|hp = 70", "|hp =")
        .replace("{{Palpedia|", "{{paldeck|")
    )

    record = parse_pal_wikitext("Lamball", "001B", incomplete)

    assert record["partnerSkill"] == {
        "name": "unknown",
        "description": "Becomes a woolly shield with Grass power.",
        "id": "unknown",
    }
    assert record["activeSkills"] == [
        {"name": "unknown", "level": 0, "id": "unknown"}
    ]
    assert record["stats"]["hp"] == "0"
    assert record["description"] == "A round and woolly Pal."


def test_parse_pal_wikitext_fills_missing_lists_with_unknown_values():
    incomplete = (
        PAL_WIKITEXT.replace(
            "|work_suitability = Handiwork@2; Mining@1",
            "|work_suitability =",
        )
        .replace(
            "|normal_drops = Wool*1-3@100; Lamball Mutton*1@60",
            "|normal_drops =",
        )
        .replace("|alpha_drops = Ring +1*1@2.5", "|alpha_drops =")
    )

    record = parse_pal_wikitext("Lamball", "001B", incomplete)

    assert record["suitability"] == [
        {"id": "unknown", "name": "unknown", "level": 0}
    ]
    assert record["possibleDrops"] == [
        {
            "name": "unknown",
            "id": "unknown",
            "amount": "0",
            "dropRate": 0,
            "dropType": "unknown",
        }
    ]


def test_fetch_pal_titles_uses_template_transclusion_index():
    session = FakeSession(
        {
            "continue": {"eicontinue": "next", "continue": "-||"},
            "query": {
                "embeddedin": [
                    {"title": "Lamball"},
                    {"title": "Cattiva"},
                ]
            },
        },
        {
            "query": {
                "embeddedin": [
                    {"title": "Cattiva"},
                    {"title": "Chikipi"},
                ]
            }
        }
    )

    assert fetch_pal_titles(session) == ["Lamball", "Cattiva", "Chikipi"]
    parameters = session.calls[0][1]["params"]
    assert parameters["list"] == "embeddedin"
    assert parameters["eititle"] == "Template:Pal"
    assert parameters["maxlag"] == "5"
    assert session.calls[1][1]["params"]["eicontinue"] == "next"


def test_fetch_pal_wikitext_uses_batched_revision_api(monkeypatch):
    monkeypatch.setattr(scraper, "API_BATCH_SIZE", 1)
    session = FakeSession(
        {
            "query": {
                "pages": [
                    {
                        "title": "Lamball",
                        "revisions": [
                            {"slots": {"main": {"content": "Lamball source"}}}
                        ],
                    }
                ]
            }
        },
        {
            "query": {
                "pages": [
                    {
                        "title": "Cattiva",
                        "revisions": [
                            {"slots": {"main": {"content": "Cattiva source"}}}
                        ],
                    }
                ]
            }
        },
    )

    pages = fetch_pal_wikitext(["Lamball", "Cattiva"], session)

    assert pages == {
        "Lamball": "Lamball source",
        "Cattiva": "Cattiva source",
    }
    assert len(session.calls) == 2
    assert session.calls[0][1]["params"]["prop"] == "revisions"


def test_fetch_pal_image_urls_uses_imageinfo():
    session = FakeSession(
        {
            "query": {
                "pages": [
                    {
                        "title": "File:Lamball icon.png",
                        "imageinfo": [
                            {
                                "url": "https://example.test/Lamball.png",
                                "mime": "image/png",
                            }
                        ],
                    }
                ]
            }
        }
    )

    assert fetch_pal_image_urls(["Lamball"], session) == {
        "Lamball": "https://example.test/Lamball.png"
    }
    assert (
        session.calls[0][1]["params"]["titles"]
        == "File:Lamball icon.png"
    )


def test_api_errors_are_reported():
    session = FakeSession(
        {"error": {"code": "badvalue", "info": "Invalid query"}}
    )

    with pytest.raises(ScraperError, match="badvalue.*Invalid query"):
        fetch_pal_titles(session)
