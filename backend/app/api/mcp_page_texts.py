from __future__ import annotations

__all__ = [
    "ADD",
    "CREATED",
    "EDIT_DESCRIPTION",
    "FOLLOW",
    "HELD",
    "PREVIEW",
    "PREVIEW_DESCRIPTION",
    "PROPOSE_DESCRIPTION",
    "SUBMITTED",
]

CREATED = "The draft for {kind} {slug} is open: build the page in it over as many calls as you need."
HELD = "The draft holds {facts} facts, {structure} structure items, {components} components and {pictures} pictures."
ADD = (
    "Add facts, structure, components, a layout, pictures and supplied sources with edit_draft's add, then "
    "preview_page with the draft_id."
)
PREVIEW = "Call preview_page with the draft_id to see the page and its checklist report; fix each failure and preview again."
SUBMITTED = "Follow each part with get_proposal or my_work; the draft stays readable until it expires."
FOLLOW = "Follow each part with get_proposal or my_work."
EDIT_DESCRIPTION = (
    "Build one craft, family or category page in a private draft over many calls, kept for this account for 14 "
    "days after its last change (one open draft a page, ten at once, 600 kB each). Name the page as subject: the "
    "first edit opens its draft, and an edit with nothing to change returns it whole; a draft_id reads one, a "
    "submitted one with its outcome too. add takes facts, structure items, finished components and dataset "
    "figures ({proposal, cites}, cites naming the draft's facts as fact:0 and on), the layout, pictures and "
    "supplied sources; remove takes parts by kind and index (removing a fact renumbers the later ones wherever "
    "they are named; a fact still named is kept); lists sets the page's mechanisms, ambiguous terms and "
    "signature fact, which the preview checks. Each part is checked for its shape and the draft for its limits "
    "(20 facts, 20 structure items, 10 components, 10 pictures, 40 supplied sources); nothing is proposed "
    "until propose_page."
)
PREVIEW_DESCRIPTION = (
    "Assemble the page a draft (draft_id) or a bundle would make, the stored page with its facts, structure, "
    "components, layout and pictures, without proposing anything: a private link for this account for 24 hours, "
    "drawn exactly as the site draws its pages. Each part says whether it is shown, listed or would be refused "
    "by the checks that run without fetching sources; the gates read the sources on propose_page. With it comes "
    "the page checklist report: each of the 27 rules that can be checked mechanically passed or failed with its "
    "evidence, the rest listed for you to judge on the link, coverage by field, figures, sources by grade and "
    "pictures by licence, drawn by ui://kalavigyan/page-preview.html in clients that show MCP Apps. A "
    "translation draws the page in its language, authored pages too."
)
PROPOSE_DESCRIPTION = (
    "Propose a draft once (draft_id), or a bundle, which may hold one part alone: a finished component or a "
    "figure after searching list_components, the page's layout built on get_page's version, or any mix of facts, "
    "structure, components, layout and pictures for one page. Every part is checked on its own as it would be "
    "alone: facts through the gates, structure through its checks, a component against its kind's spec model "
    "(kalavigyan://components/<kind>.schema.json), its units' facts and the library, where a close match refuses "
    "it with the matches and two ways on, the layout against the page's version, a new picture starting its "
    "upload, a translation's passages against their current English (a TRANSLATE task's). "
    "A refused part leaves the others standing; the report gives each part's outcome, id and reason. "
    "Each part counts against its own hour's allowance, and a draft or a bundle of several parts also against "
    "the page bundles. Preview it first with preview_page."
)
