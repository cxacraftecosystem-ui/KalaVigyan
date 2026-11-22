import pytest

from app.core.errors import InvalidInput, NotConfigured
from app.scripts import build_open_data

STEP_ARGUMENTS = {
    "latest": [],
    "draft": [
        "--version",
        "2026.11.22",
        "--site",
        "https://kalavigyan.example",
        "--craft-name",
        "Kutch Ajrakh",
    ],
    "build": [
        "--version",
        "2026.11.22",
        "--doi",
        "10.5072/zenodo.400",
        "--concept-doi",
        "10.5072/zenodo.399",
        "--record-id",
        "400",
        "--concept-record-id",
        "399",
        "--out",
        "release",
    ],
    "deposit": ["--record-id", "400", "--files", "release", "--site", "https://kalavigyan.example"],
    "record": [
        "--version",
        "2026.11.22",
        "--doi",
        "10.5072/zenodo.400",
        "--record-url",
        "https://sandbox.zenodo.org/records/400",
        "--published-at",
        "2026-11-22T10:00:00+00:00",
    ],
}


@pytest.mark.parametrize("step", sorted(STEP_ARGUMENTS))
def test_every_step_takes_a_craft_and_without_one_releases_the_whole_knowledge_base(step: str) -> None:
    parser = build_open_data._parser()
    scoped = parser.parse_args(
        [step, "--target", "SANDBOX", "--craft", "Kutch-Ajrakh", *STEP_ARGUMENTS[step]]
    )
    whole = parser.parse_args([step, "--target", "SANDBOX", *STEP_ARGUMENTS[step]])
    assert (scoped.craft, whole.craft) == ("Kutch-Ajrakh", None)


def test_a_craft_draft_needs_the_craft_s_name_before_anything_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZENODO_TOKEN", "sandbox-token")
    base = ["draft", "--target", "SANDBOX", "--version", "2026.11.22", "--site", "https://kalavigyan.example"]
    with pytest.raises(InvalidInput, match="--craft-name"):
        build_open_data.main([*base, "--craft", "Kutch-Ajrakh"])
    with pytest.raises(InvalidInput, match="slug"):
        build_open_data.main([*base, "--craft", "Kutch Ajrakh", "--craft-name", "Kutch Ajrakh"])
    assert build_open_data._named_scope("Kutch-Ajrakh", " Kutch Ajrakh ").title == (
        "Kutch Ajrakh: KalaVigyan open knowledge"
    )
    assert build_open_data._named_scope(None, None).craft is None


def test_the_command_takes_its_five_steps_and_only_the_two_targets() -> None:
    parser = build_open_data._parser()
    built = parser.parse_args(
        [
            "build",
            "--target",
            "SANDBOX",
            "--version",
            "2026.11.21",
            "--doi",
            "10.5072/zenodo.200",
            "--concept-doi",
            "10.5072/zenodo.199",
            "--record-id",
            "200",
            "--concept-record-id",
            "199",
            "--out",
            "release",
        ]
    )
    assert (built.step, built.record_id, built.concept_record_id) == ("build", 200, 199)
    with pytest.raises(SystemExit):
        parser.parse_args(["latest", "--target", "PRODUCTION"])
    with pytest.raises(SystemExit):
        parser.parse_args(["deposit", "--target", "ZENODO", "--record-id", "1"])


def test_a_zenodo_step_without_a_token_stops_before_anything_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZENODO_TOKEN", raising=False)
    with pytest.raises(NotConfigured, match="ZENODO_TOKEN"):
        build_open_data.main(
            [
                "draft",
                "--target",
                "SANDBOX",
                "--version",
                "2026.11.21",
                "--site",
                "https://kalavigyan.example",
            ]
        )
