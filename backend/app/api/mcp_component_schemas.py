from __future__ import annotations

import json
from functools import cache
from typing import Any

from app.research.component_specs import CONTRIBUTABLE_KINDS, SPEC_MODELS

from .mcp_schemas import compact

__all__ = [
    "COMPONENT_KINDS",
    "COMPONENT_SCHEMA_PREFIX",
    "COMPONENT_SCHEMA_TEMPLATE",
    "SCHEMA_MIME",
    "component_schema_template",
    "component_schema_text",
    "component_schema_uri",
]

COMPONENT_SCHEMA_PREFIX = "kalavigyan://components/"
SCHEMA_SUFFIX = ".schema.json"
COMPONENT_SCHEMA_TEMPLATE = f"{COMPONENT_SCHEMA_PREFIX}{{kind}}{SCHEMA_SUFFIX}"
SCHEMA_MIME = "application/schema+json"
COMPONENT_KINDS = CONTRIBUTABLE_KINDS
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def component_schema_uri(kind: str) -> str:
    return f"{COMPONENT_SCHEMA_PREFIX}{kind}{SCHEMA_SUFFIX}"


@cache
def component_schema_text(kind: str) -> str:
    schema = compact(SPEC_MODELS[kind].model_json_schema(by_alias=True))
    described = {
        "$schema": DRAFT,
        "$id": component_schema_uri(kind),
        "description": f"The spec of a {kind} component, as the server checks it before it is drawn",
        **schema,
    }
    return json.dumps(described, ensure_ascii=False, separators=(",", ":"))


def component_schema_template() -> dict[str, Any]:
    return {
        "uriTemplate": COMPONENT_SCHEMA_TEMPLATE,
        "name": "kalavigyan-component-schema",
        "title": "A component kind's spec schema",
        "description": (
            "The JSON schema of one component kind's spec, the object a delivered component carries as spec; "
            f"kind is one of {', '.join(COMPONENT_KINDS)}."
        ),
        "mimeType": SCHEMA_MIME,
    }
