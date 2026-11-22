from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from types import MappingProxyType
from typing import Any

from app.data.answer_kit import answer_kit, answer_view
from app.data.contributor_kit import SITE_SKILL_PATH, contributor_skill, design_tokens
from app.data.drawing_kit import DESIGN_KIT
from app.data.page_preview_view import PAGE_PREVIEW_VIEW, page_preview_view
from app.data.skill_library import (
    CONTRACTS,
    INDEX_URI,
    REFERENCES,
    SKILL_FILES,
    Contract,
    Reference,
    SkillFile,
    contract_text,
    reference_text,
    server_index,
    skill_file_text,
)
from app.research.mcp_ask import ANSWER_VIEW_MIME, ANSWER_VIEW_URI

from .mcp_component_schemas import (
    COMPONENT_KINDS,
    SCHEMA_MIME,
    component_schema_template,
    component_schema_text,
    component_schema_uri,
)
from .mcp_protocol import INVALID_PARAMS, RESOURCE_NOT_FOUND, RequestError

__all__ = [
    "ANSWER_KIT_URI",
    "ANSWER_VIEW_URI",
    "CONTRIBUTOR_SKILL_URI",
    "DESIGN_TOKENS_URI",
    "INDEX_URI",
    "RESOURCES",
    "VIEW_META",
    "resource_list",
    "resource_read",
    "resource_templates",
]

CONTRIBUTOR_SKILL_URI = "kalavigyan://skills/kalavigyan-contributor/SKILL.md"
DESIGN_TOKENS_URI = "kalavigyan://design/tokens.json"
ANSWER_KIT_URI = "kalavigyan://design/answer-kit.md"
MARKDOWN = "text/markdown"
JSON = "application/json"
VIEW_META: Mapping[str, Any] = MappingProxyType(
    {"ui": {"prefersBorder": True, "csp": {"connectDomains": [], "resourceDomains": []}}}
)


@dataclass(frozen=True)
class Resource:
    uri: str
    name: str
    title: str
    description: str
    mime_type: str
    text: Callable[[], str]
    meta: Mapping[str, Any] = field(default_factory=dict)

    def listed(self, site: str) -> dict[str, Any]:
        listed = {
            "uri": self.uri,
            "name": self.name,
            "title": self.title,
            "description": self.description.format(site=site),
            "mimeType": self.mime_type,
            "size": len(self.text().encode("utf-8")),
        }
        return {**listed, "_meta": dict(self.meta)} if self.meta else listed

    def contents(self) -> dict[str, Any]:
        content = {"uri": self.uri, "mimeType": self.mime_type, "text": self.text()}
        return {**content, "_meta": dict(self.meta)} if self.meta else content


def _reference(reference: Reference) -> Resource:
    return Resource(
        reference.uri,
        f"kalavigyan-reference-{reference.name}",
        f"{reference.title}, a KalaVigyan reference",
        f"{reference.holds}. One of the references the KalaVigyan skills follow, one source for each rule. "
        f"Also at {{site}}{reference.site_path}.",
        MARKDOWN,
        partial(reference_text, reference.name),
    )


def _contract(contract: Contract) -> Resource:
    return Resource(
        contract.uri,
        f"kalavigyan-contract-{contract.name}",
        f"{contract.title}, a KalaVigyan contract",
        f"{contract.holds}. The protocol a contributor's client follows, the same text as "
        f"{contract.repository_path} in KalaVigyan's repository.",
        MARKDOWN,
        partial(contract_text, contract.name),
    )


def _skill_file(skill_file: SkillFile) -> Resource:
    return Resource(
        skill_file.uri,
        skill_file.resource_name,
        skill_file.title,
        f"{skill_file.holds}. Also at {{site}}{skill_file.site_path}.",
        MARKDOWN,
        partial(skill_file_text, skill_file.uri),
    )


def _component_schema(kind: str) -> Resource:
    return Resource(
        component_schema_uri(kind),
        f"kalavigyan-component-{kind}",
        f"The {kind} spec schema",
        f"The JSON schema of a {kind} component's spec, checked by the server when a draft or bundle delivers one.",
        SCHEMA_MIME,
        partial(component_schema_text, kind),
    )


INDEX = Resource(
    INDEX_URI,
    "kalavigyan-index",
    "Everything the KalaVigyan MCP server offers",
    "Every tool, prompt and resource of the server with one line each: where to start and what to read.",
    MARKDOWN,
    server_index,
)
SKILLS = (
    Resource(
        CONTRIBUTOR_SKILL_URI,
        "kalavigyan-contributor",
        "The KalaVigyan contributor skill",
        "The method for researching and proposing to KalaVigyan, for agents that load skills: the tools in "
        "order, proposals and their progress, trust tiers and allowances, structure, components, pages and "
        "pictures. Its rules are the references it names. Also at {site}" + SITE_SKILL_PATH + ".",
        MARKDOWN,
        contributor_skill,
    ),
)
DESIGN = (
    Resource(
        DESIGN_TOKENS_URI,
        "kalavigyan-design-tokens",
        "The KalaVigyan design tokens",
        "The design system's tokens (Alum & Indigo): colours by role for light, dark and high contrast, "
        "type, spacing, motion and the components' specs, for agents that draw KalaVigyan content "
        "themselves.",
        JSON,
        design_tokens,
    ),
    Resource(
        ANSWER_KIT_URI,
        "kalavigyan-answer-kit",
        "How a KalaVigyan answer is drawn",
        "For agents that draw an ask result themselves: the order of an answer, its sections, citation "
        "clusters, component cards, sources and credit, with the light and dark tokens they use.",
        MARKDOWN,
        answer_kit,
    ),
    Resource(
        ANSWER_VIEW_URI,
        "kalavigyan-answer-view",
        "A KalaVigyan answer",
        "The MCP App that draws an ask result in KalaVigyan's design, from the result's structured data "
        "alone: it loads nothing from the network and shows every text as text.",
        ANSWER_VIEW_MIME,
        answer_view,
        VIEW_META,
    ),
    Resource(*PAGE_PREVIEW_VIEW, ANSWER_VIEW_MIME, page_preview_view, VIEW_META),
    *(Resource(*entry) for entry in DESIGN_KIT),
)
RESOURCES: Mapping[str, Resource] = MappingProxyType(
    {
        resource.uri: resource
        for resource in (
            INDEX,
            *SKILLS,
            *(_skill_file(skill_file) for skill_file in SKILL_FILES.values()),
            *(_reference(reference) for reference in REFERENCES.values()),
            *(_contract(contract) for contract in CONTRACTS.values()),
            *DESIGN,
            *(_component_schema(kind) for kind in COMPONENT_KINDS),
        )
    }
)


def resource_list(site: str) -> dict[str, Any]:
    return {"resources": [resource.listed(site) for resource in RESOURCES.values()]}


def resource_templates() -> dict[str, Any]:
    return {"resourceTemplates": [component_schema_template()]}


def resource_read(params: Mapping[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str):
        raise RequestError(INVALID_PARAMS, "resources/read needs the uri of a resource")
    resource = RESOURCES.get(uri)
    if resource is None:
        raise RequestError(RESOURCE_NOT_FOUND, f"no resource has the uri {uri}; resources/list gives them")
    return {"contents": [resource.contents()]}
