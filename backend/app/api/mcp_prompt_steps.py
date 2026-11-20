from __future__ import annotations

from collections.abc import Mapping

from app.models.component_kinds import GENERAL_KINDS
from app.research.component_specs_general import GENERAL_DRAWING

__all__ = [
    "CLAIM_STEP",
    "DATA_KINDS",
    "SOURCE_STEPS",
    "component_steps",
    "dataset_steps",
    "page_steps",
    "picture_steps",
    "research_steps",
    "section_steps",
]

DATA_KINDS = tuple(kind for kind in GENERAL_KINDS if kind != GENERAL_DRAWING)

CLAIM_STEP = (
    "Call `claim_task` with the key of the task you take, or `claim_tasks` with up to 10 keys: each stays yours "
    "for two hours, and `release_task` gives one back if you stop."
)
SEARCH_STEP = (
    "Call `search_sources` with words for what is missing and the craft_slug: it searches the scholarly "
    "registries, reference works and web KalaVigyan searches itself, and gives each result its grade, "
    "licence and any open copy. Search yourself as well where it finds nothing, by the rules below."
)
READ_STEP = (
    "Call `read_source` with a result's url or doi, with around for the words you need, and copy each quote "
    "from the passages it returns with their locator: they are the text the gates will check. When a page "
    "blocks reading or may vanish, call `archive_source` and cite its snapshot beside it."
)
CHECK_STEP = (
    "Call `check_quote` with every quote before you propose it: a quote that fails here fails the QUOTES "
    "gate, so fix it from the nearest passage it shows, or drop it."
)
LOOKUP_STEP = (
    "For a compound a fact names, call `lookup_compound` for its PubChem record and hazards; for a place, a "
    "plant or a craft, call `lookup_entity` for its Wikidata item and a plant's taxon name."
)
SOURCE_STEPS = (SEARCH_STEP, LOOKUP_STEP, READ_STEP, CHECK_STEP)
FOLLOW_STEP = (
    "Call `get_proposal` with each proposal id, or `my_tasks`, until it is DONE: a fact that passed the gates "
    "completes its task, and a refused one gives the task back with each gate's reasons. A FAILED proposal "
    "stored nothing: send it again with the same idempotency_key."
)
CATEGORY = "category"


def research_steps(values: Mapping[str, str]) -> list[str]:
    craft, field = values["craft_slug"], values["field"]
    return [
        f'Call `list_open_work` with craft_slug "{craft}" and field "{field}" to see the open tasks for this field.',
        CLAIM_STEP,
        f'Call `get_facts` with craft_slug "{craft}" and field "{field}", and `get_section` with the same, to see '
        "what is held. Never propose a held fact: a second source for one goes to `propose_source`, naming the "
        "fact as claim_id.",
        *SOURCE_STEPS,
        "Call `propose_facts` with up to 25 new facts, or `propose_fact` for one, each with its quotes, locators "
        "and sources, an idempotency_key of your own, and the key of the task you claimed as task_key. The reply "
        "gives each fact a proposal id at once, QUEUED.",
        FOLLOW_STEP,
    ]


def section_steps(values: Mapping[str, str]) -> list[str]:
    craft, field = values["craft_slug"], values["field"]
    return [
        f'Call `list_open_work` with craft_slug "{craft}", field "{field}" and kind "SECTION".',
        CLAIM_STEP,
        f'Call `get_facts` with craft_slug "{craft}", field "{field}" and limit 50, and `get_section` with the '
        "same: the facts are all a section may say.",
        "Write the section from those facts only, by Writing a section below.",
        "Where a sentence the section needs has no fact, find a source with `search_sources` or yourself, "
        "read it with `read_source`, check each quote with `check_quote`, and call `propose_facts` with the "
        "facts it needs, each with an idempotency_key and the task as task_key; the section is published only "
        "through KalaVigyan's own rebuild from the facts that pass.",
        FOLLOW_STEP,
    ]


def component_steps(values: Mapping[str, str]) -> list[str]:
    craft, need = values["craft_slug"], values.get("need")
    narrowed = f' for the need "{need}"' if need else ""
    return [
        f'Call `list_open_work` with craft_slug "{craft}" and kind "MISSING_COMPONENT"{narrowed}.',
        CLAIM_STEP,
        f'Call `get_facts` and `get_section` with craft_slug "{craft}" for the fields the component shows: it '
        "rests on stored facts.",
        f'Call `list_components` first, with craft_slug "{craft}" and with words for what the component shows; '
        "when one fits, place it by its label and stop.",
        "For anything the component needs that is not held, call `search_sources` or search yourself, read "
        "each source with `read_source` and check each quote with `check_quote`; a molecule's compounds come "
        "from `lookup_compound`.",
        "Build it finished by the component guide below: the spec of its kind, or of a general kind for "
        f"anything new ({', '.join(GENERAL_KINDS)}), and its units, each text by its unit id (u0001 and on) with "
        "the ids of the shown facts it rests on.",
        f'Call `preview_page` with a bundle for the craft "{craft}" holding the component and any new facts it '
        "rests on (cited as fact:0 and on), open the private link, and check it is drawn as you meant.",
        "Call `propose_page` with that bundle, or `propose_component` with the labels you considered, its "
        "subjects, spec, units and the task as task_key when it rests only on held facts.",
    ]


def page_steps(values: Mapping[str, str]) -> list[str]:
    kind, slug = values["subject_kind"], values["slug"]
    return [
        _page_reading(kind, slug),
        f'Call `list_open_work` with {kind}_slug "{slug}", then `claim_tasks` with the keys of the tasks the '
        "bundle will complete.",
        "Call `list_components` first, and place an existing component by its label rather than delivering "
        "another.",
        *SOURCE_STEPS,
        "Build one bundle: the new facts (as propose_fact takes them, each with an idempotency_key and the task "
        "it completes as task_key), structure items, finished components (each {proposal, cites}, citing the "
        "bundle's facts as fact:0 and on), the layout on get_layout's version, and the pictures the person "
        "declared.",
        "Call `preview_page` with the bundle, open the private link, and read each part's report and the page "
        "against the page checklist below: fix what is refused or drawn wrong, and preview again.",
        "Call `propose_page` with the same bundle once the preview is right. Follow its facts with "
        "`get_proposal` or `my_tasks`, and send the person each picture part's upload link.",
    ]


def picture_steps(values: Mapping[str, str]) -> list[str]:
    craft = values["craft_slug"]
    return [
        f'Call `list_open_work` with craft_slug "{craft}" and kind "MISSING_PICTURE" to see the pictures the page '
        "lacks: its masthead, its GI record, a stage or a material.",
        CLAIM_STEP,
        f'Call `get_facts` with craft_slug "{craft}" for the facts the picture shows; an AI image names at least '
        "one.",
        "Ask the person, in their own words, that they took or made the picture or hold the right to share it, "
        "that the Centre may publish it without their name, which cannot be revoked once approved, and for an "
        "AI image the tool, the model and the prompt. Never fill the declaration in for them.",
        "When the picture is in the chat, call `give_image` with image_url or image_base64, the declaration, "
        "their words of confirmation and the task as task_key, or `give_images` for up to ten of the craft; "
        "otherwise call `start_image_upload` with the task as task_key and send the person its link.",
        "The reply says whether the picture waits for review or was refused, and why; `my_tasks` shows the task "
        "closed once an Admin approves it, and the picture is then drawn in its place on the page.",
        "When the person holds no picture of what the task needs, call `find_pictures` with words for it and "
        "the craft_slug, and tell the person which open-licence pictures fit: KalaVigyan's team places those, "
        "credited to their authors, and they are never given as the person's own.",
    ]


def dataset_steps(values: Mapping[str, str]) -> list[str]:
    craft, kind = values["craft_slug"], values.get("kind")
    shape = f"a {kind}" if kind else f"one of {', '.join(DATA_KINDS)}"
    return [
        f'Call `list_open_work` with craft_slug "{craft}" for the field the data fills (a MISSING_FIELD or '
        "THIN_FIELD task), then `claim_task` with its key.",
        f'Call `get_facts`, `get_coverage` and `get_layout` for the craft "{craft}", and `list_components` with '
        f'craft_slug "{craft}" and words for the data: when a component already draws it, place it by its '
        "label and stop.",
        "Find the dataset with `search_sources` (kinds web and scholarly) or yourself, and check its licence "
        "against the dataset guide below before you read a value; values measured by district over the land "
        "are the site's own layers, never this figure's.",
        "Call `read_source` on the dataset's page with around for each row's words, and `check_quote` on each "
        "row you quote, so every value rests on the text the gates will read.",
        "Write each value the figure needs as a fact, as propose_fact takes one, quoting its row with its "
        "locator, with the dataset's page as the source, an idempotency_key of your own and that field task "
        "as task_key.",
        f"Build {shape} by the component guide below: every value stated by its reading unit, and every reading "
        "unit citing its fact as fact:0 and on.",
        f'Call `preview_page` with one bundle for the craft "{craft}" holding the facts and the component, open '
        "the private link, and check the figure against the page checklist below.",
        "Call `propose_page` with the same bundle once the preview is right, and follow its parts with "
        "`get_proposal` or `my_tasks`.",
    ]


def _page_reading(kind: str, slug: str) -> str:
    if kind == CATEGORY:
        return (
            f'Call `get_coverage` with category_slug "{slug}" and `get_layout` with subject_kind "{kind}" and slug '
            f'"{slug}": what the page holds, which fields are thin, and the layout version to build on.'
        )
    return (
        f'Call `get_facts`, `get_section` and `get_coverage` with craft_slug "{slug}", and `get_layout` with '
        f'subject_kind "{kind}" and slug "{slug}": what the page holds, which fields are thin, and the layout '
        "version to build on."
    )
