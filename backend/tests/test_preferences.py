import pytest
from pydantic import ValidationError

from app.core.deps import PASSWORD_CHANGE_ALLOWED_ROUTES, TWO_FACTOR_SETUP_ALLOWED_ROUTES
from app.schemas.preferences import PreferencesUpdate


@pytest.mark.parametrize("theme", ["system", "light", "dark"])
def test_theme_values_accepted(theme: str) -> None:
    assert PreferencesUpdate(theme=theme).theme == theme


def test_unknown_theme_and_fields_refused() -> None:
    with pytest.raises(ValidationError):
        PreferencesUpdate(theme="sepia")
    with pytest.raises(ValidationError):
        PreferencesUpdate(fontSize=3)


def test_partial_update_keeps_only_sent_fields() -> None:
    sent = PreferencesUpdate(largerText=True).model_dump(exclude_unset=True, exclude_none=True)
    assert sent == {"largerText": True}


def test_me_alias_allowed_during_pending_steps() -> None:
    assert ("GET", "/api/me") in PASSWORD_CHANGE_ALLOWED_ROUTES
    assert ("GET", "/api/me") in TWO_FACTOR_SETUP_ALLOWED_ROUTES


@pytest.mark.parametrize("language", ["auto", "en", "hi", "ur"])
def test_answer_language_takes_auto_or_an_offered_language(language: str) -> None:
    assert PreferencesUpdate(answerLanguage=language).answerLanguage == language


@pytest.mark.parametrize("language", ["fr", "hi-IN", "Hindi", ""])
def test_answer_language_refuses_anything_else(language: str) -> None:
    with pytest.raises(ValidationError):
        PreferencesUpdate(answerLanguage=language)


def test_the_digest_opt_in_is_a_preference_kept_only_when_sent() -> None:
    assert PreferencesUpdate(alertDigest=True).model_dump(exclude_unset=True) == {"alertDigest": True}
    assert "alertDigest" not in PreferencesUpdate(theme="dark").model_dump(exclude_unset=True)


@pytest.mark.parametrize("contrast", ["system", "standard", "high"])
def test_contrast_takes_the_device_standard_or_high(contrast: str) -> None:
    assert PreferencesUpdate(highContrast=contrast).highContrast == contrast


@pytest.mark.parametrize(("flag", "contrast"), [(True, "high"), (False, "system")])
def test_an_old_client_s_contrast_flag_reads_as_high_or_the_device(flag: bool, contrast: str) -> None:
    assert PreferencesUpdate(highContrast=flag).highContrast == contrast


@pytest.mark.parametrize("contrast", ["more", "HIGH", "", 1])
def test_contrast_refuses_anything_else(contrast: object) -> None:
    with pytest.raises(ValidationError):
        PreferencesUpdate(highContrast=contrast)
