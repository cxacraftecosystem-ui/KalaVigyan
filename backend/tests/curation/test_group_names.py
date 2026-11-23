from typing import Any

from app.curation.dossier import parse_dossier
from app.curation.files import CURATION_DIR, dossier_paths
from app.curation.group_names import stated_group_names
from app.research.structure_proposals import GroupNameItem
from app.research.structure_proposals_values import stated_check

from .builders import changed_dossier

AJRAKH_NAMES = {"Khatri", "Maldhari", "Ismail Mohammad Khatri", "Abduljabbar M. Khatri"}


def _groups(plain: dict[str, Any]) -> None:
    plain["communities"] = [
        {"id": "G01", "kind": "COMMUNITY", "name": "Khatri", "claimIds": ["C006"]},
        {"id": "G02", "kind": "ORGANISATION", "name": "Khatri printers", "claimIds": ["C006"]},
        {"id": "G03", "kind": "PERSON", "name": "Ismail Khatri", "claimIds": ["C006"]},
        {"id": "G04", "kind": "COMMUNITY", "name": "Rabari", "localNames": ["KHATRI"], "claimIds": ["C006"]},
    ]


def test_a_community_or_person_is_listed_only_by_a_name_its_own_quotes_state() -> None:
    found = stated_group_names(changed_dossier(_groups))
    assert [(name.name, name.kind, name.source.id) for name in found] == [("Khatri", "COMMUNITY", "S02")]
    assert "Khatri printers" in found[0].quote.quote


def test_every_name_taken_from_the_dossiers_is_stated_by_its_own_quote() -> None:
    checked = 0
    for path in dossier_paths(CURATION_DIR):
        dossier = parse_dossier(path.read_text(encoding="utf-8"))
        quotes = {(quote.source_id, quote.quote) for claim in dossier.claims for quote in claim.quotes}
        for stated in stated_group_names(dossier):
            item = GroupNameItem(name=stated.name, group_kind=stated.kind)
            assert (stated.source.id, stated.quote.quote) in quotes, (path.name, stated.name)
            assert stated_check(item, [stated.quote.quote]).passed, (path.name, stated.name)
            checked += 1
    assert checked > 0


def test_kutch_ajrakh_lists_its_stated_community_and_people_and_no_organisation() -> None:
    dossier = parse_dossier((CURATION_DIR / "Kutch-Ajrakh.json").read_text(encoding="utf-8"))
    assert {stated.name for stated in stated_group_names(dossier)} == AJRAKH_NAMES
