from __future__ import annotations

from collections.abc import Callable, Mapping

from app.research.open_work import SUBJECT_KINDS

from .mcp_prompt_steps import CLAIM_STEP

__all__ = [
    "CURATE_PAGE_PROMPT",
    "CURATE_REFERENCES",
    "CURATE_SECTIONS",
    "SOURCES_LANE_TOOLS",
    "curate_intro",
    "curate_page_prompt",
    "curate_steps",
]

CURATE_PAGE_PROMPT = "curate_page"
CURATE_TITLE = "Curate a page, start to finish"
CURATE_DESCRIPTION = (
    "Walk the whole job of one craft, family or category page: pick the work, research with your own reach, "
    "supply and check sources, build facts, structure, components, figures and pictures in a draft, preview it "
    "against the checklist report, fix, submit once and follow the outcome."
)
CURATE_SECTIONS = (
    "Proposals and their progress",
    "Finding and reading sources",
    "Structure and sources",
    "Components",
    "Pages",
    "Pictures",
)
CURATE_REFERENCES = ("sources", "quotes", "fields", "page-checklist", "components", "datasets")
SOURCES_LANE_TOOLS = (
    "search_sources",
    "read_source",
    "check_quote",
    "lookup_compound",
    "lookup_entity",
    "find_pictures",
    "archive_source",
)
CATEGORY = "category"
KIND_DESCRIPTION = f"Optional, the page's kind: {', '.join(SUBJECT_KINDS)}"
SLUG_DESCRIPTION = "Optional, the page's slug, from find_crafts; without it, pick the page in step 1"
REFUSALS = (
    "When a gate refuses, read its reasons and fix the part, never argue: QUOTES means a quote is not verbatim in "
    "the fetched page or in the text you supplied, so copy it exactly (test it with `check_quote`) or supply the "
    "text you read; SOURCE means every source is graded D or a declared open licence is contradicted, so add an "
    "A to C source or give the licence the source states; DUPLICATE means the fact is held, so add your source "
    "to the held fact with `propose_source` naming it as claim_id; NOVELTY means the section already says it, "
    "so drop it; STATED means a name, colour or number of a structure item is in none of its quotes; a delivered "
    "component is refused when a unit states a number its facts do not; a stale layout means `get_layout` moved, "
    "so build on its new version; a spent allowance names the minutes to wait. A refused part leaves the others "
    "standing: fix it and send it in a new draft or alone."
)


def curate_page_prompt[P, A](make: Callable[..., P], argument: Callable[..., A]) -> P:
    arguments = (
        argument("subject_kind", KIND_DESCRIPTION, required=False),
        argument("slug", SLUG_DESCRIPTION, required=False),
    )
    return make(
        CURATE_PAGE_PROMPT,
        CURATE_TITLE,
        CURATE_DESCRIPTION,
        arguments,
        curate_intro,
        curate_steps,
        CURATE_SECTIONS,
        CURATE_REFERENCES,
    )


def curate_intro(values: Mapping[str, str]) -> str:
    kind, slug = values.get("subject_kind"), values.get("slug")
    page = f"the {kind or 'craft'} page {slug}" if slug else "one page you choose"
    return (
        f"Curate {page} of KalaVigyan to the page checklist, start to finish: research it with your own reach, "
        "supply the sources only you can read, build every part in one draft, preview it against the report, "
        "and submit it once."
    )


def curate_steps(values: Mapping[str, str]) -> list[str]:
    return [
        _pick(values),
        CLAIM_STEP,
        _lists(values),
        "Research with your own reach first: your own search, the papers, books and archives your access opens. "
        "Then ask `search_sources` across the scholarly indexes and `lookup_compound` or `lookup_entity` for the "
        "names a fact gives, and `find_pictures` for open-licensed pictures, where this server lists them.",
        "Read every source you will quote: `read_source` for a page KalaVigyan can fetch. For a source only you can "
        "read (a paywalled paper through your subscription, a PDF or book you hold, an archive, a site that "
        "refuses the fetcher), call `supply_source` with its identity, how and when you read it, and its "
        "passages with their locators (or the whole text, or upload pdf), with draft_id; cite it as its cite_as "
        "gives it. Test each quote of a page KalaVigyan reads with `check_quote` before you propose it; a supplied "
        "source's quotes are checked against your text when you propose them, so copy them from it exactly. "
        "`archive_source` keeps a page at risk.",
        "Call `propose_facts` with batches of up to 25 facts for the fields the page lacks, each with its quotes, "
        "locators, an idempotency_key and the task it completes as task_key. Facts a figure or component of the "
        "page will cite go into the draft instead, with `add_to_draft`, so the preview draws them and the figure "
        "cites them as fact:0 and on.",
        "Call `add_to_draft` with the structure items the page needs, each with the fact that states it: a "
        "stage's colour after and its why, native names, reactions with every formula, botanical names, glossary "
        "terms, the GI record, conflicts and open questions.",
        "Call `list_components` first and place an existing component by its label. Build what is missing "
        "finished, by the component guide below: its spec and units, a general kind for a chart, table, timeline "
        "or map layer from a dataset, every value stated by a cited fact. Call `add_to_draft` with each as "
        "{proposal, cites}, and with the layout on `get_layout`'s version.",
        _pictures_step(),
        "Call `preview_draft`. Fix every rule the report fails with `add_to_draft` or `remove_from_draft`, open the "
        "private link at 360 and 1440 px in light and dark for every rule left to you to judge, and preview again "
        "until no failure you can fix remains.",
        "Call `submit_draft` once. Its report gives each part's outcome and id: follow facts and structure with "
        "`get_proposal` or `my_tasks`, send the person each new picture's upload link, and read `get_draft` for "
        "the outcome later.",
        REFUSALS,
    ]


def _pick(values: Mapping[str, str]) -> str:
    kind, slug = values.get("subject_kind") or "craft", values.get("slug")
    if not slug:
        return (
            "Pick the page: call `my_crafts` for the crafts you steward and their new gaps, or `list_open_work` for "
            "the open tasks across the catalogue; `adopt_craft` makes a craft yours to watch. Choose one page and "
            "work on it alone until it is submitted."
        )
    if kind == CATEGORY:
        return (
            f'Call `get_coverage` with category_slug "{slug}" and `list_open_work` with category_slug "{slug}": '
            "the fields the page holds, the thin ones and the open tasks."
        )
    return (
        f'Call `get_coverage` with craft_slug "{slug}" and `list_open_work` with {kind}_slug "{slug}": the fields '
        "the page holds, the thin ones and the open tasks; `my_crafts` shows a page you steward with its new gaps."
    )


def _lists(values: Mapping[str, str]) -> str:
    kind, slug = values.get("subject_kind") or "craft", values.get("slug") or "<slug>"
    return (
        f'Call `get_facts`, `get_section` and `get_layout` for the {kind} "{slug}", then derive the page\'s own '
        "lists by the page checklist below: its mechanisms, its ambiguous terms and its signature fact. Call "
        f'`create_draft` with subject_kind "{kind}", slug "{slug}" and those lists; it gives back the draft you '
        "hold for the page if there is one."
    )


def _pictures_step() -> str:
    return (
        "Give the pictures the page lacks: an illustration you generate is declared AI-made with its tool, model, "
        "prompt and the facts it shows; a photograph comes from the person who holds its rights. Ask the person "
        "for the declaration in their own words, never fill it in, then call `give_image` (or `give_images`) and "
        "`add_to_draft` with each picture as {contribution_id}. A Commons picture `find_pictures` finds is placed "
        "by a curator: name its file page in the draft's note."
    )
