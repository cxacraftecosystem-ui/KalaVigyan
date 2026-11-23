import inspect

from fastapi.routing import APIRoute

from app.main import create_app

ROTATING = {
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/auth/two-factor/enable"),
    ("POST", "/api/auth/two-factor/disable"),
}
WEB_RELAYED_PREFIX = "/api/auth/"
READS = {"GET", "HEAD", "OPTIONS"}


def _answers_a_session_token(route: APIRoute) -> bool:
    return "SESSION_TOKEN_HEADER" in inspect.getsource(route.endpoint)


def test_every_route_that_answers_a_new_session_is_a_write_under_auth_which_the_web_relays() -> None:
    routes = [route for route in create_app().routes if isinstance(route, APIRoute)]
    rotating = {
        (method, route.path)
        for route in routes
        if _answers_a_session_token(route)
        for method in route.methods
    }
    assert rotating == ROTATING
    for method, path in rotating:
        assert path.startswith(WEB_RELAYED_PREFIX) and method not in READS
