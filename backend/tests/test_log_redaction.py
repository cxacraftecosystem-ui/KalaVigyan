import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.logging import logged_path, redact_secrets
from app.main import create_app
from app.research.oauth_rules import ACCESS_TOKEN_PREFIX, CODE_PREFIX, REFRESH_TOKEN_PREFIX
from app.services.credential_links import TOKEN_PREFIX

BODY = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"
LINK_TOKEN = "Qx7_r2-LmP9sTu4VwXy8Za1Bc3De5Fg6"


class Kept(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def request_log() -> Iterator[Kept]:
    logger = logging.getLogger("kalavigyan.request")
    kept, level = Kept(), logger.level
    logger.addHandler(kept)
    logger.setLevel(logging.INFO)
    try:
        yield kept
    finally:
        logger.removeHandler(kept)
        logger.setLevel(level)


@pytest.mark.parametrize("prefix", [ACCESS_TOKEN_PREFIX, REFRESH_TOKEN_PREFIX, CODE_PREFIX, TOKEN_PREFIX])
def test_kalavigyan_s_own_tokens_never_reach_a_log_line(prefix: str) -> None:
    assert redact_secrets(f"sent {prefix}{BODY} once") == "sent [redacted] once"


def test_a_database_error_keeps_its_message_and_loses_the_row_it_names() -> None:
    error = (
        'duplicate key value violates unique constraint "User_email_key"\n'
        "DETAIL:  Key (email)=(ravi@example.org) already exists.\n"
        "[SQL parameters hidden due to hide_parameters=True]"
    )
    assert redact_secrets(error) == (
        'duplicate key value violates unique constraint "User_email_key"\n'
        "DETAIL:  [redacted]\n"
        "[SQL parameters hidden due to hide_parameters=True]"
    )


def test_a_capability_token_in_a_path_is_masked_and_other_path_values_are_kept() -> None:
    shared = {"path": f"/api/shared/answers/{LINK_TOKEN}/citations", "path_params": {"token": LINK_TOKEN}}
    assert logged_path(shared) == "/api/shared/answers/[redacted]/citations"
    craft = {"path": "/api/crafts/Kutch-Ajrakh/page", "path_params": {"slug": "Kutch-Ajrakh"}}
    assert logged_path(craft) == "/api/crafts/Kutch-Ajrakh/page"
    assert logged_path({"path": "/health"}) == "/health"


def test_the_request_log_of_the_real_app_masks_an_upload_link_token(request_log: Kept) -> None:
    answer = TestClient(create_app()).get(f"/api/upload-links/{LINK_TOKEN}")
    assert answer.status_code == 401
    paths = [getattr(record, "path", None) for record in request_log.records]
    assert "/api/upload-links/[redacted]" in paths
    assert not any(LINK_TOKEN in str(path) for path in paths)
