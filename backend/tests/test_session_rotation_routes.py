import inspect

from fastapi.routing import iter_route_contexts

from app.main import create_app

ROTATING = {
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/auth/two-factor/enable"),
    ("POST", "/api/auth/two-factor/disable"),
}
WEB_RELAYED_PREFIX = "/api/auth/"
READS = {"GET", "HEAD", "OPTIONS"}


def _answers_a_session_token(endpoint: object) -> bool:
    return inspect.isfunction(endpoint) and "SESSION_TOKEN_HEADER" in inspect.getsource(endpoint)


def test_every_route_that_answers_a_new_session_is_a_write_under_auth_which_the_web_relays() -> None:
    rotating = {
        (method, str(route.path))
        for route in iter_route_contexts(create_app().routes)
        if _answers_a_session_token(route.endpoint)
        for method in route.methods or ()
    }
    assert rotating == ROTATING
    for method, path in rotating:
        assert path.startswith(WEB_RELAYED_PREFIX) and method not in READS
