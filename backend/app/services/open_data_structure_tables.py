from __future__ import annotations

from .open_data_schema import Table, col

__all__ = ["GI_RECORDS", "MATERIALS", "NATIVE_NAMES", "REACTIONS", "STAGES", "STRUCTURE_TABLES"]

STAGES = Table(
    name="stages",
    title="Stages",
    description="The stages of each curated craft's process, in order, with the facts that describe them.",
    key=("craft", "key"),
    columns=(
        col("craft", "string", "The craft's slug.", required=True),
        col("key", "string", "The stage's key on its craft's page.", required=True),
        col("order", "integer", "Its place in the process."),
        col("name", "string", "The stage's English name.", required=True),
        col("stage_type", "string", "What kind of step it is (a dyeing, a printing, a washing and so on)."),
        col("local_name", "string", "The local name a cited source gives it."),
        col("duration", "string", "How long it takes, as its cited fact states."),
        col("season", "string", "When in the year it is done, as its cited fact states."),
        col("after", "string", "What the work looks like after the stage, as its cited fact states."),
        col("colours_after", "array", "The colours named after the stage."),
        col("why_claim_id", "string", "The fact that says why the stage is done (claims.id)."),
        col("claim_ids", "array", "The facts about the stage (claims.id).", required=True),
    ),
)

MATERIALS = Table(
    name="materials",
    title="Materials and tools",
    description="The materials and tools of each curated craft, with their botanical names and PubChem records.",
    key=("craft", "key"),
    columns=(
        col("craft", "string", "The craft's slug.", required=True),
        col("key", "string", "The material's key on its craft's page.", required=True),
        col("name", "string", "Its English name.", required=True),
        col("tool", "boolean", "True for a tool, false for a material.", required=True),
        col("kind", "string", "What kind of material it is (a mordant, a dye, a resist and so on)."),
        col("role", "string", "What it does in the craft."),
        col("local_names", "array", "Local names cited sources give it."),
        col("botanical_name", "string", "Its botanical name, for a plant."),
        col("pubchem_cid", "integer", "Its PubChem compound identifier, for a compound."),
        col("claim_ids", "array", "The facts about it (claims.id).", required=True),
    ),
)

REACTIONS = Table(
    name="reactions",
    title="Reactions",
    description="The chemical and physical changes of each curated craft, with species as their cited facts state them.",
    key=("craft", "key"),
    columns=(
        col("craft", "string", "The craft's slug.", required=True),
        col("key", "string", "The reaction's key on its craft's page.", required=True),
        col("stage_key", "string", "The stage it happens in (stages.key)."),
        col("kind", "string", "What kind of change it is.", required=True),
        col("reactants", "array", "What goes in, each as {name, formula}."),
        col("products", "array", "What comes out, each as {name, formula}."),
        col("claim_ids", "array", "The facts that state it (claims.id).", required=True),
    ),
)

NATIVE_NAMES = Table(
    name="native_names",
    title="Native names",
    description="Names of crafts in their own languages and scripts, each stated by a cited fact.",
    key=("craft", "claim_id", "text"),
    columns=(
        col("craft", "string", "The craft's slug.", required=True),
        col("text", "string", "The name in its own script.", required=True),
        col("language", "string", "Its language as a BCP 47 code.", required=True),
        col("script", "string", "Its script as an ISO 15924 code."),
        col("claim_id", "string", "The fact that states the name (claims.id).", required=True),
    ),
)

GI_RECORDS = Table(
    name="gi_records",
    title="Geographical indications",
    description="The geographical indication of each curated craft that holds one, as the GI journal records it.",
    key=("craft",),
    columns=(
        col("craft", "string", "The craft's slug.", required=True),
        col("application_number", "string", "The GI application's number."),
        col("certificate_number", "string", "The registration certificate's number."),
        col("filed_on", "string", "When the application was filed (YYYY, YYYY-MM or YYYY-MM-DD)."),
        col("registered_on", "string", "When it was registered (YYYY, YYYY-MM or YYYY-MM-DD)."),
        col("journal_issue", "string", "The GI journal issue that published it."),
        col("proprietors", "array", "The registered proprietors."),
        col("authorised_users", "integer", "How many authorised users the record counts."),
        col("claim_ids", "array", "The facts that state the record (claims.id).", required=True),
    ),
)

STRUCTURE_TABLES: tuple[Table, ...] = (STAGES, MATERIALS, REACTIONS, NATIVE_NAMES, GI_RECORDS)
