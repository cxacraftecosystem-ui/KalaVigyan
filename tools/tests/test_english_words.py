from __future__ import annotations

from pathlib import Path

from english_words_build import folded, scowl_words


def test_a_word_is_folded_to_lower_case_ascii() -> None:
    assert folded("Appliqué\n") == "applique"


def test_the_lists_up_to_size_fifty_give_each_plain_word_once_in_order(tmp_path: Path) -> None:
    (tmp_path / "english-words.10").write_text("casting\nOK\nit's\ncat\n", encoding="latin-1")
    (tmp_path / "american-words.35").write_text("Pottery\ncasting\n", encoding="latin-1")
    (tmp_path / "british-words.50").write_text("appliqu\xe9\n", encoding="latin-1")
    (tmp_path / "english-words.55").write_text("terracotta\n", encoding="latin-1")
    assert scowl_words(tmp_path) == ["applique", "casting", "pottery"]
