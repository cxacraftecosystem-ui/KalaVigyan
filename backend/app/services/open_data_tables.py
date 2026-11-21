from __future__ import annotations

from .open_data_schema import Table, col
from .open_data_structure_tables import STRUCTURE_TABLES

__all__ = [
    "CATEGORIES",
    "CITATIONS",
    "CLAIMS",
    "COMPONENTS",
    "CRAFTS",
    "CRAFT_PLACES",
    "DATASETS",
    "FAMILIES",
    "SOURCES",
    "TABLES",
    "TABLES_BY_NAME",
]


CLAIMS = Table(
    name="claims",
    title="Facts",
    description="Every fact KalaVigyan publishes: one sentence each, resting on cited sources.",
    key=("id",),
    columns=(
        col("id", "string", "The fact's permanent identifier.", required=True),
        col("text", "string", "The sentence as KalaVigyan states it.", required=True),
        col("language", "string", "The sentence's language as a BCP 47 code.", required=True),
        col(
            "field",
            "string",
            "The field it belongs to first, one of the sixteen (CHEMISTRY, HISTORY and so on).",
        ),
        col("fields", "array", "The other fields it also informs."),
        col(
            "level",
            "string",
            "Its evidence level: VERIFIED, REVIEWED, PROVISIONAL or HYPOTHESIS.",
            required=True,
        ),
        col(
            "status", "string", "APPROVED, or PROPOSED or IN_REVIEW while a reviewer reads it.", required=True
        ),
        col(
            "subject_kind",
            "string",
            "The kind of thing it is about (MATERIAL, PROCESS_STAGE and so on).",
            required=True,
        ),
        col("subject", "string", "The name of the thing it is about.", required=True),
        col("relation", "boolean", "True when it states how two things connect.", required=True),
        col("craft", "string", "The craft's slug, when the fact belongs to one craft."),
        col("family", "string", "The craft family's slug (a sub-category of the craft list)."),
        col("category", "string", "The category's slug."),
        col("value", "number", "The quantity the sentence states, when it states one."),
        col("unit", "string", "The unit of that quantity."),
        col("sources_differ", "boolean", "True when its sources give different readings.", required=True),
        col(
            "version",
            "integer",
            "The fact's version; a corrected fact supersedes the one before.",
            required=True,
        ),
        col("supersedes", "string", "The identifier of the fact this one replaced."),
        col("created", "datetime", "When the fact was first stored, in UTC.", required=True),
    ),
)

CITATIONS = Table(
    name="citations",
    title="Citations",
    description=(
        "Which source supports which fact, and where in the source. The verbatim quote stays at its "
        "source under the source's own terms: follow the locator to read it."
    ),
    key=("id",),
    columns=(
        col("id", "string", "The citation's identifier.", required=True),
        col("claim_id", "string", "The fact it supports (claims.id).", required=True),
        col("source_id", "string", "The source (sources.id).", required=True),
        col(
            "locator",
            "string",
            "Where the supporting words stand: a page, section, paragraph, line or table row.",
        ),
        col(
            "relation",
            "string",
            "DIRECT when the source states the fact, or how else it supports it.",
            required=True,
        ),
        col(
            "quoted", "boolean", "True when a verbatim quote of the source supports the fact.", required=True
        ),
        col(
            "quote_check",
            "string",
            "PASS when the quote was found again in the source's text, else its last check.",
        ),
        col("retrieved", "date", "The day the source was read for this fact."),
    ),
)

SOURCES = Table(
    name="sources",
    title="Sources",
    description="The works the facts cite, graded A to D by KalaVigyan's source rubric. Each keeps its own licence.",
    key=("id",),
    columns=(
        col("id", "string", "The source's identifier.", required=True),
        col(
            "kind", "string", "PAPER, BOOK, WEB_PAGE, GI_JOURNAL, GOVERNMENT_REPORT and so on.", required=True
        ),
        col("title", "string", "The title as the source states it.", required=True),
        col("authors", "array", "Its authors as the source names them."),
        col("publisher", "string", "Its publisher."),
        col("year", "integer", "The year it was published."),
        col("doi", "string", "Its DOI."),
        col("url", "string", "Its address."),
        col("archived_url", "string", "A Wayback Machine snapshot of it."),
        col("language", "string", "The language of the source."),
        col("access", "string", "OPEN, ABSTRACT_ONLY or RESTRICTED, as recorded."),
        col("grade", "string", "A (primary or authoritative) to D (other web pages).", required=True),
        col("licence", "string", "The source's own licence, as recorded."),
        col("attribution", "string", "The attribution the source asks for."),
        col("retrieved", "date", "The day KalaVigyan last read it."),
    ),
)

CRAFTS = Table(
    name="crafts",
    title="Crafts",
    description="The crafts of KalaVigyan's craft list, with their identifiers and curated page versions.",
    key=("slug",),
    columns=(
        col("slug", "string", "The craft's identifier on KalaVigyan.", required=True),
        col("name", "string", "Its English name.", required=True),
        col("category", "string", "Its category's slug."),
        col("family", "string", "Its family's slug."),
        col("states_of_origin", "array", "The states the craft list names as its home."),
        col("states_of_practice", "array", "The states the craft list says it is practised in."),
        col("gi_status", "string", "GI when the craft list records a geographical indication."),
        col("status", "string", "ACTIVE, or LEGACY for an older craft-list entry.", required=True),
        col(
            "wikidata",
            "string",
            "The Wikidata item of the craft itself, when one was matched with confidence.",
        ),
        col("craft_code", "string", "The code the craft shares with the craft portals."),
        col("page_url", "string", "The craft's page on KalaVigyan.", required=True),
        col("curated_version", "integer", "The version of its curated page, when it has one."),
        col("curated_at", "datetime", "When that version was curated, in UTC."),
        col("coverage", "string", "How fully the curated page covers its fields."),
    ),
)

CRAFT_PLACES = Table(
    name="craft_places",
    title="Places of crafts",
    description="Where each craft is practised, by the Local Government Directory (LGD) codes of states and districts.",
    key=("id",),
    columns=(
        col("id", "string", "The place record's identifier.", required=True),
        col("craft", "string", "The craft's slug.", required=True),
        col("label", "string", "The place as recorded."),
        col("state", "string", "The state's name."),
        col("state_lgd", "integer", "The state's LGD code."),
        col("district", "string", "The district's name."),
        col("district_lgd", "integer", "The district's LGD code."),
        col("precision", "string", "STATE, DISTRICT or a finer place.", required=True),
        col("role", "string", "The place's role for the craft (a centre, a source of material and so on)."),
        col("level", "string", "The evidence level of the place record.", required=True),
    ),
)

CATEGORIES = Table(
    name="categories",
    title="Categories",
    description="The categories of the craft list, with the version of each curated category page.",
    key=("slug",),
    columns=(
        col("slug", "string", "The category's identifier.", required=True),
        col("name", "string", "Its name.", required=True),
        col("sort_order", "integer", "Its place in the craft list.", required=True),
        col("page_url", "string", "Its page on KalaVigyan.", required=True),
        col("curated_version", "integer", "The version of its curated page, when it has one."),
        col("curated_at", "datetime", "When that version was curated, in UTC."),
    ),
)

FAMILIES = Table(
    name="families",
    title="Families",
    description="The families (sub-categories) of the craft list.",
    key=("slug",),
    columns=(
        col("slug", "string", "The family's identifier.", required=True),
        col("name", "string", "Its name.", required=True),
        col("category", "string", "Its category's slug.", required=True),
        col("sort_order", "integer", "Its place in its category.", required=True),
    ),
)

COMPONENTS = Table(
    name="components",
    title="Components",
    description="The catalogue of KalaVigyan's figures and interactive components, and the facts each rests on.",
    key=("label",),
    columns=(
        col("label", "string", "The component's identifier.", required=True),
        col("kind", "string", "Its kind (a chart, a process ladder, a dip player and so on).", required=True),
        col("title", "string", "Its title.", required=True),
        col("description", "string", "What it shows."),
        col("field", "string", "The field it belongs to.", required=True),
        col("fields", "array", "Other fields it informs."),
        col("craft", "string", "The craft it was made for."),
        col("subjects", "array", "What it is about, each as {kind, key, name}."),
        col("claim_ids", "array", "The facts it rests on (claims.id).", required=True),
    ),
)

DATASETS = Table(
    name="datasets",
    title="Datasets",
    description="The open datasets behind the site's maps: their records, licences and citations, never their values.",
    key=("code",),
    columns=(
        col("code", "string", "The dataset's short code.", required=True),
        col("title", "string", "Its title.", required=True),
        col("publisher", "string", "Its publisher."),
        col("edition", "string", "The edition or version read."),
        col("period", "string", "The period it covers."),
        col("native_resolution", "string", "Its native resolution."),
        col("crs", "string", "Its coordinate reference system."),
        col("licence", "string", "Its licence."),
        col("licence_url", "string", "The licence's address."),
        col("attribution", "string", "The attribution it asks for."),
        col("redistributable", "boolean", "True when its licence lets its values be shared.", required=True),
        col("citation", "string", "How to cite it."),
        col("url", "string", "Its landing page."),
        col("retrieved", "date", "The day it was read."),
        col("sha256", "string", "The SHA-256 of the file read."),
        col("layers", "array", "The site's map layers drawn from it."),
    ),
)

TABLES: tuple[Table, ...] = (
    CLAIMS,
    CITATIONS,
    SOURCES,
    CRAFTS,
    CRAFT_PLACES,
    CATEGORIES,
    FAMILIES,
    *STRUCTURE_TABLES,
    COMPONENTS,
    DATASETS,
)
TABLES_BY_NAME = {table.name: table for table in TABLES}
