import pytest

from app.core.errors import NotConfigured
from app.scripts import build_open_data


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
