from datetime import date

import pytest

from app.core.errors import InvalidInput
from app.services.open_data_changes import release_changes
from app.services.open_data_deposit import ReleaseFolder, checked_scope, deposit_files, release_folder
from app.services.open_data_files import release_files
from app.services.open_data_release import ReleaseStamp
from app.services.open_data_scope import WHOLE, ReleaseScope
from app.services.open_data_zenodo import deposit_metadata

from .release_fixtures import AJRAKH, AJRAKH_STAMP, SITE, STAMP, empty_tables
from .zenodo_fake import FakeZenodo, fake_deposit

TITLE = "Kutch Ajrakh: KalaVigyan open knowledge"
PAGE = "https://kalavigyan.example/crafts/Kutch-Ajrakh"
CRAFT_METADATA = deposit_metadata(
    version="2026.11.22", released=date(2026, 11, 22), counts={}, site=SITE, scope=AJRAKH
)


def _folder(stamp: ReleaseStamp, scope: ReleaseScope) -> ReleaseFolder:
    changes = release_changes({}, None, None)
    return release_folder(release_files(empty_tables(), stamp, changes, site=SITE, scope=scope).files)


def test_the_craft_s_metadata_adds_its_name_and_monograph_and_keeps_the_creator_and_licence() -> None:
    whole = deposit_metadata(version="2026.11.22", released=date(2026, 11, 22), counts={}, site=SITE)
    assert CRAFT_METADATA["title"] == TITLE
    assert CRAFT_METADATA["keywords"] == [*whole["keywords"], "Kutch Ajrakh"]
    for same in ("creators", "license", "access_right", "language", "upload_type"):
        assert CRAFT_METADATA[same] == whole[same], same
    assert [(item["identifier"], item["relation"]) for item in CRAFT_METADATA["related_identifiers"]] == [
        ("https://kalavigyan.example/data", "isDocumentedBy"),
        (PAGE, "isDocumentedBy"),
        ("https://github.com/cxacraftecosystem-ui/KalaVigyan", "isSupplementedBy"),
    ]
    assert CRAFT_METADATA["description"].startswith(
        "<p>The slice of KalaVigyan&#x27;s knowledge about Kutch Ajrakh"
    )


def test_a_first_craft_release_opens_a_record_of_its_own() -> None:
    fake = FakeZenodo()
    draft = fake_deposit(fake).open_draft(None, CRAFT_METADATA)
    assert draft.record_id == 200
    assert fake.calls == [("POST", "/api/deposit/depositions"), ("PUT", "/api/deposit/depositions/200")]
    assert fake.described[0]["title"] == TITLE


def test_a_craft_release_is_never_a_new_version_of_the_whole_knowledge_record() -> None:
    fake = FakeZenodo(inherited_title="KalaVigyan open knowledge")
    with pytest.raises(
        InvalidInput, match="is a version of 'KalaVigyan open knowledge', not of 'Kutch Ajrakh"
    ):
        fake_deposit(fake).open_draft(150, CRAFT_METADATA)
    assert fake.calls == [
        ("POST", "/api/deposit/depositions/150/actions/newversion"),
        ("GET", "/api/deposit/depositions/200"),
    ]
    own = FakeZenodo(inherited_title=TITLE)
    assert fake_deposit(own).open_draft(150, CRAFT_METADATA).record_id == 200


def test_a_craft_deposit_describes_the_record_by_the_files_own_scope() -> None:
    fake = FakeZenodo()
    deposit_files(fake_deposit(fake), _folder(AJRAKH_STAMP, AJRAKH), record_id=200, publish=False, site=SITE)
    described = fake.described[-1]
    assert (described["title"], described["keywords"][-1]) == (TITLE, "Kutch Ajrakh")
    assert PAGE in {item["identifier"] for item in described["related_identifiers"]}
    assert "<li>Facts (claims): 0</li>" in described["description"]
    assert "Left out:" in described["description"]


def test_a_deposit_refuses_files_built_for_another_scope_than_the_run_names() -> None:
    craft, whole = _folder(AJRAKH_STAMP, AJRAKH), _folder(STAMP, WHOLE)
    assert checked_scope(craft, "Kutch-Ajrakh") is craft and checked_scope(whole, None) is whole
    with pytest.raises(InvalidInput, match="hold the craft Kutch-Ajrakh, but this run releases the whole"):
        checked_scope(craft, None)
    with pytest.raises(InvalidInput, match="hold the whole knowledge base, but this run releases the craft"):
        checked_scope(whole, "Kutch-Ajrakh")
