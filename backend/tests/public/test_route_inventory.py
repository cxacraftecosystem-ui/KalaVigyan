import re
import uuid
from typing import Any

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.api.artisan_deps import artisan_conversation_enabled
from app.api.public_deps import public_asset_reader, public_reader
from app.api.voice_deps import voice_call_enabled
from app.core.deps import get_current_user_any_step, get_optional_user
from app.main import create_app
from app.models import User

from ..readers import sign_in_as

PUBLIC = "PUBLIC"
SIGN_IN_FLOW = "SIGN_IN_FLOW"
SERVICE = "SERVICE"
ASKING = "ASKING"
OWN_RECORDS = "OWN_RECORDS"
ADMIN = "ADMIN"
CONSENT = "CONSENT"
OPEN_CLASSES = frozenset({PUBLIC, SIGN_IN_FLOW, SERVICE})
GUARDED_CLASSES = frozenset({ASKING, OWN_RECORDS, ADMIN, CONSENT})

PUBLIC_ROUTES = {
    ("GET", "/api/categories"),
    ("GET", "/api/categories/{slug}"),
    ("GET", "/api/categories/{slug}/coverage"),
    ("GET", "/api/categories/{slug}/monograph"),
    ("GET", "/api/families/{slug}/monograph"),
    ("GET", "/api/pages/{kind}/{slug}/layout"),
    ("GET", "/api/compare"),
    ("GET", "/api/crafts/catalogue"),
    ("GET", "/api/crafts/contributed/{contribution_id}"),
    ("GET", "/api/crafts/{slug}/coverage"),
    ("GET", "/api/crafts/{slug}/field-voices"),
    ("GET", "/api/crafts/{slug}/monograph"),
    ("GET", "/api/crafts/{slug}/page"),
    ("GET", "/api/crafts/{slug}/process"),
    ("GET", "/api/crafts/{slug}/region"),
    ("GET", "/api/crafts/{slug}/shared-science"),
    ("GET", "/api/knowledge/crafts/{slug}/export"),
    ("GET", "/api/knowledge/open-work"),
    ("GET", "/api/site/pages"),
    ("GET", "/api/field-voices/images/{image_id}"),
    ("GET", "/api/field-voices/recordings/{recording_id}"),
    ("GET", "/api/map/crafts"),
    ("GET", "/api/map/districts/{district_lgd}"),
    ("GET", "/api/map/layers"),
    ("GET", "/api/map/layers/{layer}"),
    ("GET", "/api/molecules/{pubchem_cid}/conformer"),
    ("GET", "/api/open-data"),
    ("GET", "/api/places/districts"),
    ("GET", "/api/public/summary"),
    ("GET", "/api/rivers/{main_riv}"),
    ("GET", "/api/shared-science/{term_key}"),
    ("GET", "/api/shared/answers/{token}"),
    ("GET", "/api/shared/answers/{token}/citations"),
    ("GET", "/api/shared/answers/{token}/citations/{fmt}"),
    ("GET", "/api/shared/answers/{token}/pdf"),
    ("GET", "/api/shared/lessons/{token}"),
    ("GET", "/api/shared/lessons/{token}/files/{fmt}"),
    ("GET", "/api/terms/{key}"),
}
ASSET_ROUTES = {
    ("GET", "/api/crafts/contributed/{contribution_id}"),
    ("GET", "/api/field-voices/images/{image_id}"),
    ("GET", "/api/map/layers/{layer}"),
    ("GET", "/api/molecules/{pubchem_cid}/conformer"),
    ("GET", "/api/rivers/{main_riv}"),
}
SIGN_IN_ROUTES = {
    ("GET", "/api/auth/config"),
    ("GET", "/api/auth/set-password"),
    ("GET", "/api/privacy/notice"),
    ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/google/nonce"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/oidc/nonce"),
    ("POST", "/api/auth/set-password"),
    ("POST", "/api/auth/set-password/check"),
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/two-factor/verify"),
    ("GET", "/api/oauth/terms"),
}
SERVICE_ROUTES = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/api/artisan/llm/v1/chat/completions"),
    ("POST", "/api/voice/llm/v1/chat/completions"),
    ("POST", "/api/mcp"),
    ("GET", "/.well-known/oauth-protected-resource"),
    ("GET", "/.well-known/oauth-protected-resource/api/mcp"),
    ("GET", "/.well-known/oauth-authorization-server"),
    ("POST", "/api/oauth/register"),
    ("POST", "/api/oauth/token"),
    ("POST", "/api/oauth/revoke"),
    ("PUT", "/api/upload-links/slots/{token}"),
    ("PUT", "/api/knowledge/supplied-sources/slots/{token}"),
}
ASKING_ROUTES = {
    ("GET", "/api/answers/config"),
    ("POST", "/api/answers/stream"),
    ("GET", "/api/answers/{answer_id}/film-score"),
    ("GET", "/api/answers/{answer_id}/listen"),
    ("GET", "/api/media/options"),
    ("POST", "/api/media/jobs"),
    ("GET", "/api/media/jobs/{job_id}"),
    ("POST", "/api/voice/session"),
    ("POST", "/api/voice/session/{session_id}/end"),
    ("POST", "/api/voice/session/{session_id}/turns"),
    ("GET", "/api/voice/session/{session_id}/transcript"),
    ("GET", "/api/voice/session/{session_id}/turns/{turn_id}/speech"),
    ("POST", "/api/artisan/conversations"),
    ("POST", "/api/artisan/conversations/{conversation_id}/end"),
    ("POST", "/api/artisan/conversations/{conversation_id}/turns"),
    ("GET", "/api/artisan/conversations/{conversation_id}/turns/{turn_id}/speech"),
}
OWN_RECORD_ROUTES = {
    ("GET", "/api/answers/{answer_id}/quiz"),
    ("GET", "/api/artisan/contributions"),
    ("GET", "/api/artisan/contributions/{contribution_id}/audio"),
    ("POST", "/api/artisan/contributions/{contribution_id}/withdraw"),
    ("GET", "/api/artisan/conversations"),
    ("GET", "/api/artisan/conversations/{conversation_id}"),
    ("DELETE", "/api/artisan/conversations/{conversation_id}"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/me"),
    ("GET", "/api/auth/two-factor"),
    ("POST", "/api/auth/two-factor/setup"),
    ("POST", "/api/auth/two-factor/setup/cancel"),
    ("POST", "/api/auth/two-factor/enable"),
    ("POST", "/api/auth/two-factor/disable"),
    ("POST", "/api/auth/two-factor/recovery-codes"),
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/auth/first-password/nonce"),
    ("POST", "/api/auth/google/link"),
    ("POST", "/api/auth/google/link-nonce"),
    ("GET", "/api/explainers/{explainer_id}"),
    ("GET", "/api/explainers/{explainer_id}/versions"),
    ("GET", "/api/explainers/{explainer_id}/versions/{version}"),
    ("GET", "/api/explainers/{explainer_id}/versions/{version}/citations"),
    ("GET", "/api/explainers/{explainer_id}/versions/{version}/citations/{fmt}"),
    ("GET", "/api/explainers/{explainer_id}/versions/{version}/pdf"),
    ("GET", "/api/explainers/{explainer_id}/versions/{version}/share"),
    ("PUT", "/api/explainers/{explainer_id}/versions/{version}/share"),
    ("DELETE", "/api/explainers/{explainer_id}/versions/{version}/share"),
    ("GET", "/api/lessons"),
    ("POST", "/api/lessons"),
    ("GET", "/api/lessons/{lesson_id}"),
    ("DELETE", "/api/lessons/{lesson_id}"),
    ("GET", "/api/lessons/{lesson_id}/files/{fmt}"),
    ("GET", "/api/lessons/{lesson_id}/share"),
    ("PUT", "/api/lessons/{lesson_id}/share"),
    ("DELETE", "/api/lessons/{lesson_id}/share"),
    ("GET", "/api/notifications"),
    ("POST", "/api/notifications/{notification_id}/read"),
    ("POST", "/api/notifications/read-all"),
    ("GET", "/api/preferences/me"),
    ("PUT", "/api/preferences/me"),
    ("GET", "/api/profile/me"),
    ("PUT", "/api/profile/me/artisan"),
    ("PUT", "/api/profile/me/student"),
    ("GET", "/api/saved-explainers"),
    ("PUT", "/api/saved-explainers/{explainer_id}"),
    ("DELETE", "/api/saved-explainers/{explainer_id}"),
    ("GET", "/api/usage/me"),
    ("GET", "/api/oauth/connections"),
    ("DELETE", "/api/oauth/connections/{connection_id}"),
}
ADMIN_ROUTES = {
    ("POST", "/api/contributions/images"),
    ("POST", "/api/contributions/images/batch"),
    ("POST", "/api/knowledge/facts"),
    ("POST", "/api/knowledge/layouts"),
    ("POST", "/api/knowledge/structure"),
    ("POST", "/api/knowledge/pages"),
    ("POST", "/api/knowledge/pages/preview"),
    ("GET", "/api/knowledge/pages/previews/{token}"),
    ("GET", "/api/knowledge/pages/pictures/{contribution_id}"),
    ("GET", "/api/knowledge/supplied-sources/{supplied_id}"),
    ("POST", "/api/knowledge/open-work/claim"),
    ("POST", "/api/knowledge/open-work/release"),
    ("GET", "/api/knowledge/review-switch"),
    ("PUT", "/api/knowledge/review-switch"),
    ("POST", "/api/knowledge/proposals/facts"),
    ("GET", "/api/knowledge/proposals"),
    ("GET", "/api/knowledge/proposals/{proposal_id}"),
    ("GET", "/api/knowledge/open-work/mine"),
    ("POST", "/api/knowledge/open-work/claims"),
    ("GET", "/api/knowledge/stewardship"),
    ("PUT", "/api/knowledge/stewardship/{slug}"),
    ("DELETE", "/api/knowledge/stewardship/{slug}"),
    ("GET", "/api/knowledge/trust-tiers"),
    ("GET", "/api/knowledge/trust-tiers/{user_id}"),
    ("PUT", "/api/knowledge/trust-tiers/{user_id}"),
    ("GET", "/api/knowledge/contribution-costs"),
    ("GET", "/api/site/build"),
    ("POST", "/api/site/build"),
    ("PUT", "/api/pages/{kind}/{slug}/layout"),
    ("PUT", "/api/contributions/images/{contribution_id}/file"),
    ("GET", "/api/contributions/images/mine"),
    ("POST", "/api/contributions/images/{contribution_id}/withdraw"),
    ("GET", "/api/contributions/images/review"),
    ("POST", "/api/contributions/images/review/{contribution_id}/approve"),
    ("POST", "/api/contributions/images/review/{contribution_id}/reject"),
    ("GET", "/api/review-queue"),
    ("POST", "/api/review-queue/{kind}/{item_id}/approve"),
    ("POST", "/api/review-queue/{kind}/{item_id}/reject"),
    ("POST", "/api/review-queue/FACTS/{claim_id}/raise"),
    ("POST", "/api/review-queue/FACTS/{claim_id}/retract"),
    ("GET", "/api/upload-links/{token}"),
    ("POST", "/api/upload-links/{token}/picture"),
    ("POST", "/api/upload-links/{token}/renew"),
    ("GET", "/api/contributions/proposals/mine"),
    ("POST", "/api/contributions/proposals/facts/{claim_id}/withdraw"),
    ("POST", "/api/contributions/proposals/components/{proposal_id}/withdraw"),
    ("POST", "/api/contributions/proposals/components"),
    ("GET", "/api/contributions/proposals/library"),
    ("GET", "/api/contributions/proposals/form"),
    ("POST", "/api/contributions/proposals/terms"),
    ("GET", "/api/access/roster"),
    ("POST", "/api/access/roster"),
    ("GET", "/api/access/roster/pending-count"),
    ("PATCH", "/api/access/roster/{row_id}"),
    ("DELETE", "/api/access/roster/{row_id}"),
    ("POST", "/api/access/roster/{row_id}/decision"),
    ("PUT", "/api/answers/{answer_id}/simulations/{block_id}/hidden"),
    ("PUT", "/api/crafts/{slug}/explainers/{piece_id}/hidden"),
    ("PUT", "/api/crafts/{slug}/media/{asset_id}/hidden"),
    ("PUT", "/api/crafts/{slug}/pieces/{piece_id}/hidden"),
    ("GET", "/api/field-voices/held-images"),
    ("PUT", "/api/field-voices/held-images/visibility"),
    ("GET", "/api/field-photos/review"),
    ("POST", "/api/field-photos/{image_id}/decision"),
    ("POST", "/api/field-photos/screen"),
    ("POST", "/api/auth/password-links"),
    ("POST", "/api/auth/password-links/{link_id}/revoke"),
    ("GET", "/api/secrets"),
    ("PUT", "/api/secrets/{key}"),
    ("DELETE", "/api/secrets/{key}"),
    ("POST", "/api/secrets/{key}/test"),
    ("GET", "/api/settings/ai-budget"),
    ("PUT", "/api/settings/ai-budget"),
    ("GET", "/api/settings/ai-catalogue"),
    ("GET", "/api/settings/ai-routing"),
    ("GET", "/api/settings/ai-routing/{task}"),
    ("PUT", "/api/settings/ai-routing/{task}"),
    ("POST", "/api/settings/ai-routing/{task}/test"),
    ("GET", "/api/testimony/review"),
    ("GET", "/api/testimony/review/{contribution_id}"),
    ("PUT", "/api/testimony/review/{contribution_id}"),
    ("GET", "/api/testimony/review/{contribution_id}/corroboration"),
    ("POST", "/api/testimony/review/{contribution_id}/approve"),
    ("POST", "/api/testimony/review/{contribution_id}/reject"),
    ("GET", "/api/usage/report"),
    ("GET", "/api/usage/summary"),
    ("GET", "/api/users"),
    ("GET", "/api/users/{user_id}"),
    ("PATCH", "/api/users/{user_id}"),
    ("DELETE", "/api/users/{user_id}"),
    ("POST", "/api/users/{user_id}/guardian-consent"),
    ("POST", "/api/users/{user_id}/restore"),
    ("POST", "/api/users/{user_id}/sign-out-everywhere"),
    ("POST", "/api/users/{user_id}/suspend"),
    ("DELETE", "/api/users/{user_id}/two-factor"),
}
CONSENT_ROUTES = {
    ("POST", "/api/auth/consent"),
    ("GET", "/api/artisan/recording-notice"),
    ("POST", "/api/profile/me/recording-consent"),
    ("DELETE", "/api/profile/me/recording-consent"),
    ("GET", "/api/voice/notice"),
    ("GET", "/api/oauth/authorize/request"),
    ("POST", "/api/oauth/authorize/approve"),
    ("POST", "/api/oauth/authorize/deny"),
}
ROUTE_CLASSES: dict[tuple[str, str], str] = {
    **dict.fromkeys(PUBLIC_ROUTES, PUBLIC),
    **dict.fromkeys(SIGN_IN_ROUTES, SIGN_IN_FLOW),
    **dict.fromkeys(SERVICE_ROUTES, SERVICE),
    **dict.fromkeys(ASKING_ROUTES, ASKING),
    **dict.fromkeys(OWN_RECORD_ROUTES, OWN_RECORDS),
    **dict.fromkeys(ADMIN_ROUTES, ADMIN),
    **dict.fromkeys(CONSENT_ROUTES, CONSENT),
}
STUDENT = User(id=uuid.UUID(int=31), name="Ravi Shah", email="ravi@example.org", role="STUDENT")
PATH_VALUES = {
    "slug": "Kutch-Ajrakh",
    "key": "GEMINI_API_KEY",
    "task": "TRANSLATE",
    "block_id": "simulation-1",
}
A_UUID = "6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f"
GROUPS = (
    PUBLIC_ROUTES,
    SIGN_IN_ROUTES,
    SERVICE_ROUTES,
    ASKING_ROUTES,
    OWN_RECORD_ROUTES,
    ADMIN_ROUTES,
    CONSENT_ROUTES,
)


def _calls(dependant: Any) -> set[Any]:
    calls: set[Any] = set()
    for sub in dependant.dependencies:
        calls.add(sub.call)
        calls |= _calls(sub)
    return calls


def _routes() -> dict[tuple[str, str], set[Any]]:
    found: dict[tuple[str, str], set[Any]] = {}
    for route in iter_route_contexts(create_app().routes):
        if route.dependant is None:
            continue
        calls = _calls(route.dependant)
        for method in sorted(route.methods or ()):
            found[(method, route.path)] = calls
    return found


ROUTES = _routes()


def _classed(classes: frozenset[str]) -> set[tuple[str, str]]:
    return {route for route, kind in ROUTE_CLASSES.items() if kind in classes}


def _filled(path: str) -> str:
    return re.sub(r"\{([^}]+)\}", lambda found: PATH_VALUES.get(found.group(1), A_UUID), path)


def test_each_route_is_listed_in_one_class_only() -> None:
    assert sum(len(group) for group in GROUPS) == len(ROUTE_CLASSES)


def test_every_route_carries_a_class_and_every_class_names_a_real_route() -> None:
    assert sorted(set(ROUTES) - set(ROUTE_CLASSES)) == [], "unclassified routes"
    assert sorted(set(ROUTE_CLASSES) - set(ROUTES)) == [], "classified routes that do not exist"


def test_exactly_the_open_classes_answer_without_a_session() -> None:
    open_routes = {route for route, calls in ROUTES.items() if get_current_user_any_step not in calls}
    assert sorted(open_routes ^ _classed(OPEN_CLASSES)) == []


def test_exactly_the_public_reads_take_the_optional_reader() -> None:
    optional = {route for route, calls in ROUTES.items() if get_optional_user in calls}
    assert sorted(optional ^ PUBLIC_ROUTES) == []
    assert {method for method, _path in PUBLIC_ROUTES} == {"GET"}


@pytest.mark.parametrize("route", sorted(_classed(GUARDED_CLASSES)), ids=" ".join)
def test_every_guarded_route_answers_401_to_an_anonymous_reader(route: tuple[str, str]) -> None:
    method, path = route
    app = create_app()
    app.dependency_overrides[voice_call_enabled] = lambda: True
    app.dependency_overrides[artisan_conversation_enabled] = lambda: True
    response = TestClient(app).request(method, re.sub(r"\{[^}]+\}", "1", path), json={})
    assert response.status_code == 401, route


def test_every_public_read_is_counted_and_only_the_named_assets_in_their_own_bucket() -> None:
    assert ASSET_ROUTES <= PUBLIC_ROUTES
    counted = {route for route, calls in ROUTES.items() if public_reader in calls}
    assets = {route for route, calls in ROUTES.items() if public_asset_reader in calls}
    assert sorted(assets ^ ASSET_ROUTES) == []
    assert sorted(counted ^ (PUBLIC_ROUTES - ASSET_ROUTES)) == []
    assert counted.isdisjoint(assets)


@pytest.mark.parametrize("route", sorted(ADMIN_ROUTES), ids=" ".join)
def test_every_admin_route_refuses_a_signed_in_student(route: tuple[str, str]) -> None:
    method, path = route
    app = create_app()
    sign_in_as(app, lambda: STUDENT)
    response = TestClient(app).request(method, _filled(path), json={})
    assert response.status_code == 403, route
