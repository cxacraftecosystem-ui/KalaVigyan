# 0114. Component kinds any craft can use, and one dataset record

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "check whether the items that we have added in
proposed component types are generalizable or not, optimize over there too. And the dataset
structure, has it proven to be any good?"). Amends decision 0092 (the design tokens), the delivered
components of round 7 (`component-specs-general.md`) and decision 0111 (the MCP tools).

## Context

Every registered component was Kutch Ajrakh's; other pages only borrowed them, so no kind had been
proven on a second craft. Most spec models are structural and generalise, but three things did not:
a depicted material could only be one of Kutch Ajrakh's dye tokens, so Bidri's blackened alloy or
Jaipur's cobalt could not be drawn; the dip player's phases were dyeing words in code (vat, lifted,
air) and it demanded an equation; and the page-tool kinds held Kutch Ajrakh's interface text and
per-page counts. Four pairs of kinds did one job twice (chart and general_chart, fact_table and
general_table, timeline and general_timeline, map_layer and general_map_layer). The environment data
was well structured but lived in two registries with two record shapes (`etl/geo/geo_etl/catalog.py`
and `tools/maplayers/sources.py`), the served records lacked the fields the dataset guide requires,
CHELSA's licence field held a citation, USGS MRDS was recorded twice, and the contributed-data path
(one quoted fact per value, at most 20 in a bundle) did not scale to a real table.

## Decision

1. **Materials are records.** A depicted material is a record in `tools/design/materials.json`: the
   token, the craft, its dossier material id, the dossier facts that state or show its colour, the
   colour (hex or oklch) and what the swatch shows; `stated: false` marks the one colour (Ajrakh's
   vat liquor) whose facts name the material but not its colour. The design generator turns each
   into its specimen token, records the nearest reserved colour and the frame ratios, and refuses a
   record within 3 delta E of a reserved colour in any theme, a blue at the interactive indigo's
   chroma (0.15) or a swatch whose edge does not read. It also writes the names a spec may depict,
   `backend/app/research/depicted_materials.py` and `frontend/lib/depictedMaterials.ts`. Kutch
   Ajrakh's 21 dye and dip tokens are the first records and draw exactly as before (the CSS lines are
   unchanged); Bidriware (alloy white, black patina, silver), Blue Pottery of Jaipur (quartz white,
   cobalt, copper turquoise) and Bastar Dhokra (field soil, sem green, riverside soil) follow. The CSS
   family keeps its 1.1 name `--dye-<name>` so that stored documents and the Kutch Ajrakh page stay
   identical; the swatch key `dye` keeps its name for the same reason.
2. **Words are data.** A dip player's phase is a key of the spec's own (`pose`, a lower-case word,
   each once), so Ajrakh's spec carries vat, lifted and air and Bidri's carries solution, lifted and
   oiled; its equation is shown only where a source states one. A stage player's label before each
   stage's colour after is the spec's (`afterLabel`: Ajrakh's "Cloth after", a dhokra mould's "Model
   after"), and a stage may name a recorded material as its swatch instead of the page's tile pattern.
   A map sequence card without a visual draws no empty frame. A `--dye-` token in any drawing must be
   a recorded material.
3. **One kind per job.** `chart`, `fact_table`, `timeline` and `map_layer` take the authored spec
   and the declared spec (a spec with a `head`); `general_drawing` is now `drawing`; the general_*
   names are retired in the kind lists, the stored pieces, the proposals and the stored documents
   (migration `0056_datasets_and_materials`). The page tools (14 kinds), the authored art (5) and the
   authored scripts (`model_explainer`, which runs a sandboxed document, and `timeline_map`, which
   drives the page's route-map script) leave the contributable list with a reason; 22 kinds remain.
   An `experiment_lab` rests on its toggles' facts.
4. **One dataset record.** `backend/app/data/datasets/registry.json` holds every dataset once, in one
   shape (code, title, publisher, edition and version, period, native resolution, CRS, licence with
   its address, attribution, redistributable, citation with DOI, landing page, the file's address and
   its build); the geo ETL reads its rows, a physical layer names its dataset by code, and the day
   read and SHA-256 come from each build. CHELSA is recorded under CC0 1.0 with its EnviDat DOI, as
   its landing page states; MRDS is one record. The map layers route, the region records and
   `DatasetCredit` (now also drawing the physical layers' credits) serve the whole record.
5. **Contributed datasets.** `propose_dataset` (a 22nd tool, in the proposing group) takes the record
   and the CSV file's SHA-256, checks the licence is open and redistributable, the citation names its
   DOI, the code is new and the landing page reads, and returns a single-use upload slot
   (`PUT /api/dataset-uploads/{token}`, 30 minutes, 5 MB, 20000 rows); the stored `DatasetTable`
   then backs any declared chart, table or map layer that names the dataset and each value's `cell`,
   and the gates check every value against its row instead of one quoted fact per value.
6. **Proof on other crafts.** Each contributable kind has a fixture for a craft other than Kutch
   Ajrakh in `frontend/lib/kindFixtures/`, built from that craft's dossier facts word for word; it
   passes its spec model and the delivery gates (backend), is drawn by its view (unit spec), and all
   of them are placed on one page, `/design/kinds`, through the monograph renderer.

## Consequences

- A new craft's material needs a record and a generator run before it can be drawn; proposing a
  material's colour over MCP (through `propose_structure`) is left open.
- Stored rows reach the registry's record when `etl/geo/load.py` runs or after
  `python -m app.scripts.sync_dataset_registry`; until then the served record of an older row is the
  short one.
- The page tools are the site's to build for every page; those the site does not yet build from
  data stay on the Kutch Ajrakh page as authored.
- The swatch's weave pattern is the page's; a generated page that places a swatch draws it without
  the weave until the site defines one for every page.
