from __future__ import annotations

from typing import Any

from app.curation.checks import content_problems, default_context
from app.services.curation_keys import curated_id
from app.services.curation_records import gi_row
from app.services.curation_rows import CraftTarget

from .builders import changed_dossier

IMITATION = "market.imitation"


def imitation_problems(change: Any) -> list[str]:
    problems = content_problems(changed_dossier(change), default_context())
    return [problem.message for problem in problems if problem.where == IMITATION]


def gi_journal(plain: dict[str, Any], claim_id: str) -> None:
    claim = next(claim for claim in plain["claims"] if claim["id"] == claim_id)
    cited = {quote["sourceId"] for quote in claim["quotes"]}
    for source in plain["sources"]:
        if source["id"] in cited:
            source["kind"] = "GI_JOURNAL"


def test_a_sign_of_imitation_cites_a_gi_journal_and_is_kept_with_the_gi_record() -> None:
    def listed(plain: dict[str, Any]) -> None:
        plain["market"] = {"imitation": ["C006"]}

    assert imitation_problems(listed) == [
        "a sign of imitation is kept with the GI record, so market.gi is given",
        "C006 cites no GI journal, so it is no sign of imitation",
    ]


def test_a_sign_citing_a_gi_journal_beside_the_gi_record_passes() -> None:
    def listed(plain: dict[str, Any]) -> None:
        gi_journal(plain, "C006")
        plain["market"] = {"gi": {"claimIds": ["C002"]}, "imitation": ["C006"]}

    assert imitation_problems(listed) == []


def test_the_curated_import_stores_the_signs_on_the_gi_record() -> None:
    def listed(plain: dict[str, Any]) -> None:
        plain["market"] = {"gi": {"claimIds": ["C002"]}, "imitation": ["C006", "C007"]}

    dossier = changed_dossier(listed)
    craft = CraftTarget(id=curated_id("Kutch-Ajrakh", "craft"), slug="Kutch-Ajrakh", name="Kutch Ajrakh")
    row = gi_row(dossier, craft)
    assert row is not None
    assert row["imitationClaimIds"] == [
        curated_id("Kutch-Ajrakh", "C006"),
        curated_id("Kutch-Ajrakh", "C007"),
    ]
