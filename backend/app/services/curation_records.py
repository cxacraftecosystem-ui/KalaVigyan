from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlsplit

from app.core.errors import InvalidInput
from app.curation.dossier import Dossier
from app.curation.records import Picture, Term as DossierTerm
from app.data.district_register import DistrictCodes
from app.research.licences import open_licence
from app.research.media_refs import MediaRef
from app.research.subject_keys import term_key
from app.research.terms import TERM_LABEL_MAX_CHARS

from .curation_keys import MEDIA_PROVIDER, TERM_NAME_SEPARATOR, curated_id
from .curation_rows import ConceptPlan, CraftTarget
from .curation_structure import place_codes
from .media_ref_store import TEXT_RELEVANCE, media_ref_id, media_ref_values, media_url_key
from .term_glossary import term_id

__all__ = [
    "gi_row",
    "glossary_key",
    "label_key",
    "media_claim_rows",
    "media_rows",
    "picture_media_id",
    "price_rows",
    "term_concept_rows",
    "term_craft_rows",
    "term_names",
    "term_rows",
    "workforce_rows",
]

INLINE = "INLINE"
LINK_CARD = "LINK_CARD"


def picture_media_id(picture: Picture) -> uuid.UUID:
    return media_ref_id(media_url_key(MEDIA_PROVIDER, picture.page_url, picture.url))


def media_rows(dossier: Dossier) -> list[dict[str, Any]]:
    rows: dict[uuid.UUID, dict[str, Any]] = {}
    for picture in dossier.pictures:
        url_key = media_url_key(MEDIA_PROVIDER, picture.page_url, picture.url)
        ref = _media_ref(picture, media_ref_id(url_key), dossier)
        rows.setdefault(ref.id, media_ref_values(ref, url_key))
    return list(rows.values())


def _media_ref(picture: Picture, media_id: uuid.UUID, dossier: Dossier) -> MediaRef:
    licensed = open_licence(picture.licence) or open_licence(picture.licence_url)
    return MediaRef(
        id=media_id,
        display=INLINE if licensed else LINK_CARD,
        provider=MEDIA_PROVIDER,
        page_url=picture.page_url,
        image_url=picture.url,
        width=picture.width,
        height=picture.height,
        title=picture.caption,
        alt=picture.caption,
        author=picture.author,
        site=urlsplit(picture.page_url).hostname or picture.page_url,
        credit=None if licensed else picture.author,
        licence=picture.licence,
        licence_url=picture.licence_url,
        source_id=None,
        retrieved_at=dossier.curated_at,
    )


def media_claim_rows(dossier: Dossier) -> list[dict[str, Any]]:
    slug = dossier.slug
    links = {
        (picture_media_id(picture), curated_id(slug, claim_id))
        for picture in dossier.pictures
        for claim_id in picture.claim_ids
    }
    return [
        {"mediaRefId": media_id, "claimId": claim_id, "relevance": TEXT_RELEVANCE}
        for media_id, claim_id in sorted(links, key=lambda pair: (str(pair[0]), str(pair[1])))
    ]


def term_names(term: DossierTerm) -> list[str]:
    names = [name.strip() for name in term.term.split(TERM_NAME_SEPARATOR)]
    return list(dict.fromkeys(name for name in names if name))


def glossary_key(term: DossierTerm) -> str | None:
    return label_key(term_names(term)[0])


def label_key(label: str) -> str | None:
    if len(label) > TERM_LABEL_MAX_CHARS:
        return None
    try:
        return term_key(label)
    except InvalidInput:
        return None


def term_rows(dossier: Dossier) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for term in dossier.glossary:
        key = glossary_key(term)
        if key is None:
            continue
        names = term_names(term)
        rows.setdefault(
            key,
            {
                "id": term_id(key),
                "key": key,
                "label": names[0],
                "meaning": term.meaning,
                "localNames": [],
                "aliases": names[1:],
                "wikidataId": None,
            },
        )
    return list(rows.values())


def term_craft_rows(dossier: Dossier, craft: CraftTarget) -> list[dict[str, Any]]:
    keys = dict.fromkeys(key for key in map(glossary_key, dossier.glossary) if key)
    return [{"termId": term_id(key), "craftId": craft.id} for key in keys]


def term_concept_rows(dossier: Dossier, concepts: ConceptPlan) -> list[dict[str, Any]]:
    links = {
        (term_id(key), concepts.ids[term.id]): {"termId": term_id(key), "conceptId": concepts.ids[term.id]}
        for term, key in ((term, glossary_key(term)) for term in dossier.glossary)
        if key
    }
    return list(links.values())


def gi_row(dossier: Dossier, craft: CraftTarget) -> dict[str, Any] | None:
    gi = dossier.market.gi
    if gi is None:
        return None
    return {
        "craftId": craft.id,
        "applicationNumber": gi.application_number,
        "certificateNumber": gi.certificate_number,
        "filedOn": gi.filed_on,
        "registeredOn": gi.registered_on,
        "journalIssue": gi.journal_issue,
        "proprietors": list(gi.proprietors),
        "authorisedUserCount": gi.authorised_user_count,
        "claimIds": [curated_id(dossier.craft_slug, claim_id) for claim_id in gi.claim_ids],
    }


def price_rows(dossier: Dossier, craft: CraftTarget, codes: DistrictCodes) -> list[dict[str, Any]]:
    places = {place.id: place for place in dossier.places}
    rows = []
    for price in dossier.market.prices:
        place = places[price.place_id]
        state_lgd, district_lgd = place_codes(place, codes)
        rows.append(
            {
                "id": curated_id(dossier.craft_slug, "price", price.claim_id, price.place_id, price.date),
                "craftId": craft.id,
                "claimId": curated_id(dossier.craft_slug, price.claim_id),
                "pricedOn": price.date,
                "placeName": place.name,
                "stateLgd": state_lgd,
                "districtLgd": district_lgd,
            }
        )
    return rows


def workforce_rows(dossier: Dossier, craft: CraftTarget) -> list[dict[str, Any]]:
    return [
        {
            "id": curated_id(dossier.craft_slug, "workforce", entry.claim_id, str(entry.year)),
            "craftId": craft.id,
            "claimId": curated_id(dossier.craft_slug, entry.claim_id),
            "year": entry.year,
        }
        for entry in dossier.market.workforce
    ]
