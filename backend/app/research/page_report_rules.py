from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from .component_specs_general import is_declared
from .coverage_chapters import field_chapter
from .elements import ELEMENTS
from .monograph_document import MonographDocument
from .monograph_page import MonographContent
from .page_drafts import PageLists
from .page_report_design import DESIGN_RULE, design_evidence
from .page_report_drawable import DRAWABLE_RULE, HeldShapes, drawable_evidence, opportunities
from .page_report_read import OPENING, PICTURE_KIND, ReadPage, Sentence, node_text
from .page_report_sources import counted_apart
from .quotes import quote_key, unsupported_figures
from .structure_proposals import ReactionItem

__all__ = [
    "DENSE_SENTENCES",
    "EVIDENCE_MAX",
    "FAIL",
    "HEADING_TAG",
    "JUDGE",
    "OPENING",
    "PASS",
    "PICTURE_KIND",
    "VERDICTS",
    "ReadPage",
    "ReportInput",
    "Sentence",
    "Verdict",
    "checked_rules",
    "node_text",
]

PASS, FAIL, JUDGE = VERDICTS = ("PASS", "FAIL", "JUDGE")
HEADING_TAG = "h3"
LEDE_MAX = 3
DENSE_SENTENCES = 3
MECHANISM_MIN = 2
EVIDENCE_MAX = 12
CATEGORY, CHART_KIND = "category", "chart"
REPEAT_MIN_CHARS = 40
PROGRESS = re.compile(
    r"\bwriting (the )?section\b"
    r"|\b\d+\s+of\s+\d+\s+(scenes|sections|chapters|steps)\b"
    r"|\b\d{1,3}\s?%\s+(done|complete)\b",
    re.IGNORECASE,
)
GAP = re.compile(
    r"\b(not yet|coming soon|to be (added|written|researched)|no information|no data|nothing (is )?known)\b",
    re.IGNORECASE,
)
SYMBOL = re.compile(r"[A-Z][a-z]?")
DENSE_PASSED = "each of {fields} fields has {least} or more cited sentences, in its prose or its figures"
GAP_TEXT = "edit_draft: remove {unit} and add it back saying what its facts state"
GAP_FACT = (
    "{unit} draws fact {facts}; propose_facts a fact of {field} stating what its source does find, and an "
    "Admin retracts fact {facts} with stage_reviews (kind FACTS, action retract)"
)
JUDGE_HINTS: Mapping[int, str] = {
    8: "look at the media chapter as a gallery keyed to the section titles",
    11: "the site draws toasts and announcements; check them on the private link",
    12: "the site draws the bars and the chapter rail; check them on the private link",
    13: "look for empty bands beside pictures and boxes larger than their content",
    16: "read the close of the page and its length at 1440 px",
    19: "read each transformation for what changes and what does it",
    22: "check that each quoted error is marked [sic] beside its correction",
    28: "preview_page draws the page at 390 and 1440 px and checks what a reader sees; read its pictures",
}

Verdict = tuple[str, list[str]]


@dataclass(frozen=True)
class ReportInput:
    document: MonographDocument
    lists: PageLists | None = None
    statements: Mapping[str, str] = field(default_factory=dict)
    reactions: tuple[ReactionItem, ...] = ()
    supplied: Mapping[str, str] = field(default_factory=dict)
    bar: MonographContent | None = None
    held: HeldShapes | None = None


def checked_rules(given: ReportInput) -> dict[int, Verdict]:
    page = ReadPage.of(given.document)
    checks: dict[int, Callable[[ReadPage, ReportInput], Verdict]] = {
        1: _headline,
        2: _masthead_picture,
        3: _one_masthead,
        4: _true_counts,
        5: _counted_apart,
        6: _signature,
        7: _pictures_once,
        9: _figures_cite,
        10: _at_rest,
        14: _credits,
        15: _cards_hold_text,
        17: _charts,
        18: _ambiguous,
        20: _mechanisms,
        21: _equations,
        23: _fields_placed,
        24: _dense,
        25: _no_repeats,
        26: _no_holes,
        DESIGN_RULE: _designed,
        DRAWABLE_RULE: _drawable,
    }
    found = {number: check(page, given) for number, check in checks.items()}
    found |= {number: (JUDGE, [hint]) for number, hint in JUDGE_HINTS.items()}
    return {
        number: (verdict, evidence[:EVIDENCE_MAX]) for number, (verdict, evidence) in sorted(found.items())
    }


def _verdict(problems: list[str], passed: str) -> Verdict:
    return (FAIL, problems) if problems else (PASS, [passed])


def _headline(page: ReadPage, given: ReportInput) -> Verdict:
    titles = [given.document.title, *(c.title for c in page.document.content.components)]
    problems = [
        f"'{title}' is a question; state the finding" for title in titles if title.rstrip().endswith("?")
    ]
    lede = len(page.lede())
    if lede > LEDE_MAX:
        problems.append(f"the lede holds {lede} sentences; keep it to {LEDE_MAX}")
    return _verdict(problems, f"no title is a question and the lede holds {lede} sentences")


def _masthead_picture(page: ReadPage, given: ReportInput) -> Verdict:
    if given.document.subject_kind == CATEGORY:
        return JUDGE, ["a category's masthead picture is the site's own"]
    heroes = [p.label for p in page.pictures if p.chapter == OPENING]
    if not heroes:
        return FAIL, ["no picture holds the masthead; give one for the MASTHEAD slot"]
    return PASS, [f"{heroes[0]} holds the masthead"]


def _one_masthead(page: ReadPage, given: ReportInput) -> Verdict:
    heroes = [p.label for p in page.pictures if p.chapter == OPENING]
    if len(heroes) > 1:
        return FAIL, [f"{len(heroes)} pictures share the masthead: {', '.join(heroes)}"]
    return PASS, [f"{len(heroes)} picture in the masthead"]


def _true_counts(page: ReadPage, given: ReportInput) -> Verdict:
    citations = page.document.content.citations
    problems: list[str] = []
    for sentence in page.sentences:
        quotes = [q.quote for q in citations.get(sentence.unit_id, []) if q.quote]
        missing = unsupported_figures(sentence.text, quotes) if quotes else []
        if missing:
            problems.append(f"{sentence.unit_id} states {', '.join(missing)}, which no quote it cites holds")
    return _verdict(problems, f"every number in {len(page.sentences)} sentences is in a quote they cite")


def _counted_apart(page: ReadPage, given: ReportInput) -> Verdict:
    return JUDGE, [counted_apart(page.document)]


def _signature(page: ReadPage, given: ReportInput) -> Verdict:
    signature = given.lists.signature if given.lists is not None else None
    if signature is None:
        return JUDGE, ["name the signature fact in the draft's lists to have it checked"]
    wanted = str(signature)
    statement = given.statements.get(wanted)
    told = [
        s.unit_id
        for s in page.sentences
        if wanted in s.claim_ids or (statement is not None and quote_key(s.text) == quote_key(statement))
    ]
    if not told:
        return FAIL, [f"the signature fact {wanted} is on no sentence of the page"]
    if len(told) > 1:
        return FAIL, [f"the signature fact is told {len(told)} times ({', '.join(told)}); tell it once"]
    return PASS, [f"the signature fact is told once, in {told[0]}"]


def _pictures_once(page: ReadPage, given: ReportInput) -> Verdict:
    sources = Counter(page.plate(p.label)[0] for p in page.pictures)
    repeated = [f"{src} is drawn {count} times" for src, count in sources.items() if src and count > 1]
    return _verdict(repeated, f"{len(page.pictures)} pictures, each file drawn once")


def _figures_cite(page: ReadPage, given: ReportInput) -> Verdict:
    uncited = [
        f"figure {f.label} cites nothing through its units" for f in page.figures if not page.cited(f.label)
    ]
    return _verdict(uncited, f"all {len(page.figures)} figures cite through their units")


def _at_rest(page: ReadPage, given: ReportInput) -> Verdict:
    texts = [page.text(unit) for unit in page.document.content.units]
    found = [f"'{text[:80]}' shows progress" for text in texts if PROGRESS.search(text)]
    return _verdict(found, "no text shows a progress state")


def _credits(page: ReadPage, given: ReportInput) -> Verdict:
    missing = [f"{p.label} has no credit under it" for p in page.pictures if not page.plate(p.label)[2]]
    return _verdict(missing, f"each of {len(page.pictures)} pictures carries its credit after its caption")


def _cards_hold_text(page: ReadPage, given: ReportInput) -> Verdict:
    empty = [
        f"{f.label} holds no sentence"
        for f in page.figures
        if not any(page.text(unit) for unit in page.named(f.label)) and not page.cited(f.label)
    ]
    return _verdict(empty, f"each of {len(page.figures)} figures holds its text")


def _charts(page: ReadPage, given: ReportInput) -> Verdict:
    charts = [f for f in page.figures if f.kind == CHART_KIND]
    loose = [
        f"{f.label} is an authored {f.kind}; check its scale"
        for f in charts
        if not is_declared(page.document.specs.get(f.label))
    ]
    return (JUDGE, loose) if loose else (PASS, [f"{len(charts)} charts, each drawn by the site from zero"])


def _ambiguous(page: ReadPage, given: ReportInput) -> Verdict:
    terms = given.lists.ambiguous_terms if given.lists is not None else []
    if not terms:
        return JUDGE, ["list the page's ambiguous terms in the draft to see where each is used"]
    return JUDGE, [f"'{term}' is used in {len(_naming(page, term))} sentences" for term in terms]


def _mechanisms(page: ReadPage, given: ReportInput) -> Verdict:
    mechanisms = given.lists.mechanisms if given.lists is not None else []
    if not mechanisms:
        return JUDGE, ["list the page's mechanisms in the draft to have their depth counted"]
    counts = {name: len(_naming(page, name)) for name in mechanisms}
    thin = [f"'{name}' is told in {n} sentences" for name, n in counts.items() if n < MECHANISM_MIN]
    told = ", ".join(f"{name} {n}" for name, n in counts.items())
    return _verdict(thin, f"every mechanism is told in {MECHANISM_MIN} or more sentences: {told}")


def _equations(page: ReadPage, given: ReportInput) -> Verdict:
    problems: list[str] = []
    checked = 0
    for reaction in given.reactions:
        species = [*reaction.reactants, *reaction.products]
        if any(s.formula is None for s in species):
            continue
        checked += 1
        before = {e for s in reaction.reactants for e in _elements(s.formula or "")}
        after = {e for s in reaction.products for e in _elements(s.formula or "")}
        if before != after:
            names = " + ".join(s.name for s in reaction.reactants)
            problems.append(f"{names} loses or gains {', '.join(sorted(before ^ after))}")
    if not checked:
        return JUDGE, ["no reaction with every formula given; check each equation by hand"]
    return _verdict(problems, f"the elements of {checked} reactions are the same on both sides")


def _fields_placed(page: ReadPage, given: ReportInput) -> Verdict:
    problems = [
        f"{s.unit_id} ({s.field}) sits in {s.chapter}, not {field_chapter(s.field)}"
        for s in page.sentences
        if s.field and s.chapter != OPENING and s.chapter != field_chapter(s.field)
    ]
    coverage = given.document.coverage
    shown = page.told_by_field()
    if coverage is not None:
        problems += [
            f"{c.field} holds {c.claims} facts but no sentence on the page"
            for c in coverage.fields
            if c.claims and not shown.get(c.field)
        ]
    return _verdict(problems, f"{len(shown)} fields, each in its chapter")


def _dense(page: ReadPage, given: ReportInput) -> Verdict:
    shown = page.told_by_field()
    thin = [f"{name} has {n} sentences" for name, n in shown.items() if n < DENSE_SENTENCES]
    return _verdict(thin, DENSE_PASSED.format(fields=len(shown), least=DENSE_SENTENCES))


def _no_repeats(page: ReadPage, given: ReportInput) -> Verdict:
    told: dict[str, list[str]] = {}
    for s in page.sentences:
        told.setdefault(quote_key(s.text).casefold(), []).append(s.unit_id)
    problems = [
        f"'{s.text[:80]}' is told twice, in {' and '.join(told[key])}"
        for s in page.sentences
        if len(told[key := quote_key(s.text).casefold()]) > 1
    ]
    problems += [
        f"{unit} in {figure.label} repeats {told[key][0]}: '{text[:80]}'"
        for figure in page.figures
        for unit in page.held(figure.label)
        if len(text := page.text(unit)) >= REPEAT_MIN_CHARS and (key := quote_key(text).casefold()) in told
    ]
    return _verdict(list(dict.fromkeys(problems)), "no sentence is told twice")


def _no_holes(page: ReadPage, given: ReportInput) -> Verdict:
    units = page.document.content.units
    problems = [_gap(page, ref) for ref in units if GAP.search(page.text(ref))]
    shown = page.by_field()
    problems += [
        f"the heading of {unit.field} has no sentence under it"
        for unit in units.values()
        if unit.tag == HEADING_TAG and unit.field and not shown.get(unit.field)
    ]
    return _verdict(problems, "no empty heading and no admitted gap")


def _gap(page: ReadPage, ref: str) -> str:
    unit = page.document.content.units[ref]
    said = f"'{page.text(ref)[:80]}'"
    if not unit.claim_ids:
        owner = page.within.get(ref)
        where = f"{ref} in {owner}" if owner else ref
        return f"{said} admits a gap: {GAP_TEXT.format(unit=where)}"
    facts = ", ".join(unit.claim_ids)
    return f"{said} reads as a gap: {GAP_FACT.format(unit=ref, facts=facts, field=unit.field or 'its field')}"


def _designed(page: ReadPage, given: ReportInput) -> Verdict:
    figures = [(figure.label, figure.kind) for figure in page.figures]
    pictures = [picture.label for picture in page.pictures]
    found = design_evidence(figures, page.document.specs, page.held, page.text, pictures)
    passed = f"every delivered figure and {len(pictures)} pictures speak the design's vocabulary"
    return _verdict(found, passed)


def _drawable(page: ReadPage, given: ReportInput) -> Verdict:
    passed, evidence = drawable_evidence(opportunities(page.document.content, page.sentences, given.held))
    return (PASS if passed else JUDGE), evidence


def _naming(page: ReadPage, term: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(term.casefold())}\b")
    return [s.unit_id for s in page.sentences if pattern.search(s.text.casefold())]


def _elements(formula: str) -> set[str]:
    return {symbol for symbol in SYMBOL.findall(formula) if symbol in ELEMENTS}
