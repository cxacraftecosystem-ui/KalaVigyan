# 0253. A stage player draws each stage's own scene, the molecule composer finds a compound the page's own facts name, and every map layer carries its dataset record

A `stage_player`'s stage may carry its own `scene`, a kit scene or a drawing, shown beside the
stage's text and in the stage box whenever that stage is shown; a stage without one keeps the scene
of the nearest stage before it that has one, and the player rests on its `drawing` as before.
`compose_component` composes a `molecule_3d` of a compound the page's own facts name, given as
`about.compound` by its PubChem CID, from PubChem's record and 3D conformer, and names what is
missing when it cannot. A physical map layer is credited from the dataset record its own file
carries, and every layer the maps draw is listed with its record in a guide page a contributor's
AI reads with `get_page`.

Date: 2026-11-28. Status: accepted (the lead's lane brief `ux-1126/page-kinds`, from the site gaps
an Opus agent filed with `report_site_gap` while building Sanganeri Hand Block Printing over MCP).
It amends [decision 0228](0228-players-molecules-and-timelines-that-play-and-a-reaction-s-species-drawn-from-the-kit.md)
(a stage player that is not Ajrakh's swaps in a stage's own kit scene),
[decision 0198](0198-a-craft-s-own-interactives-composed-and-played-on-every-page.md) (a molecule
from a compound its materials hold) and
[decision 0196](0196-a-contributor-s-map-drawn-by-the-site-from-places-it-resolves.md) (each layer's
dataset record written into the stored spec). No migration. The contracts are
`docs/contracts/component-specs-science.md` (stage_player, Kit scenes) and
`docs/contracts/component-specs-general.md` (the declared timeline map's placement), with the
component guide, the cookbook, the dataset guide, the contributor skill and the interactives skill.

| For | Read |
|---|---|
| The players drawn from the kit, and their scenes | [decision 0200](0200-players-and-cards-drawn-from-the-kit.md) |
| Players that play on their own, the owner's rule | [decision 0228](0228-players-molecules-and-timelines-that-play-and-a-reaction-s-species-drawn-from-the-kit.md) |
| The composer and its molecules | [decision 0198](0198-a-craft-s-own-interactives-composed-and-played-on-every-page.md), [decision 0202](0202-a-dip-s-colours-from-its-facts-the-crafts-dyes-and-pigments-and-twenty-atoms.md) |
| A contributor's map, its places and credits | [decision 0196](0196-a-contributor-s-map-drawn-by-the-site-from-places-it-resolves.md), [decision 0232](0232-every-places-map-drawn-on-the-site-s-own-map-base-and-told-what-it-is-about.md) |
| The one dataset registry | [datasets.md](../../backend/app/data/contributor/references/datasets.md), Recording a dataset |

## Context

The agent's Sanganeri page (2026-11-28) held 29 figures against Kutch Ajrakh's 71, 13 interactives
against 14 and 4 maps against 8. Three of its gaps were the site's. Each cause was read in the code
and checked against production before anything changed:

1. **One scene for every stage.** `StagePlayerSpec` held one `drawing` and `StageEntry` no scene, so
   `StagePlayer.tsx` drew the same picture in the stage box at every stage; the published
   `sanganeri-hand-block-printing/process/thirteen-stages-player` (read from
   `/api/crafts/sanganeri-hand-block-printing/monograph`) has one kit scene, a carved block over a
   printed length, for all thirteen stages. Kutch Ajrakh's authored living cloth redraws the cloth
   after each stage (`clothSVG(n)` from the page's `#tile-n` patterns, the vat stage dipping and
   oxidising). The kit's `genericStages` already looked for a stage's own `svg.kv-kit-scene` inside
   its list item since decision 0228, but no spec field and no view put one there, and it fell back
   to the player's rest drawing. The preview's report already told agents "a stage_player you write,
   each stage a kit scene of what its facts name" (`research/page_report_drawable.WRITTEN`).
2. **The composer looked only at materials.** `compose_molecule.molecule_candidates` took a
   compound only from a curated material whose PubChem CID or linked `Compound` was held
   (`compose_reads._compounds`), with the facts the page's structure references. Sanganeri's
   materials carry no CID (its turmeric is `M15`, no compound), so `compose_component` with kind
   `molecule_3d` replied (production, 2026-11-28) "a material of Sanganeri Hand Block Printing held
   with its PubChem compound and stated by its own facts", and with `about.compound` 969516 (the CID
   `lookup` gives for curcumin) "no material of Sanganeri-Hand-Block-Printing is held as that
   compound", though the page's fact `cd9ee2cf` names curcumin and its source is the curcumin
   article. Neither the craft's reactions (species by name, no CID) nor `lookup` (nothing kept) nor
   any fact carries a CID the composer could read.
3. **The physical layers' records lived only in their files.** `timeline_maps.map_credits` read each
   layer's records from the database's `EnvDataset` rows. The geo ETL loads only its own datasets
   there; `ETOPO1_ICE` and `NATURAL_EARTH_10M_PHYSICAL` (build `maplayers`) are in the registry and
   in `relief.json` and `rivers.json` with their day read and SHA-256, and in no migration or load,
   and `sync_registry` updates rows and inserts none. So a declared timeline map naming `relief` or
   `rivers` was refused at delivery ("the layer relief rests on ETOPO1_ICE, which the site holds no
   dataset record for"); the DB test passed only because its fixture inserts those rows by hand. The
   published Sanganeri map names no layer. No tool gave a contributor's AI the records to read.

## Decision

1. **A stage's own scene** (`component_specs_science_players.StageEntry.scene`, `SceneDrawing`):
   a kit scene of one to three parts, or of species, which may name one motion since the scene is
   shown again whenever its stage is, or a drawing whose root is one `svg` (`DRAWN_STAGE`), held to
   the bar for drawn art like the player's own. The last stage carries none (`REST_SCENE`): the
   player rests on it, and its picture is the `drawing`. The view (`StageList.tsx`) draws the scene
   in the stage's list item (`.lc-scene`, its key beside a kit scene), and the kit's `genericStages`
   clones it into the stage box when the stage is shown and plays its motion with the stage band.
   A stage without its own scene keeps the nearest earlier stage's scene, and with none before it
   the player's `drawing`; the last stage always shows the `drawing`. A spec with no stage scene is
   drawn exactly as before. Paper draws every stage's scene after the rest drawing. The owner's rule
   that players play on their own (decision 0228) holds: a stage's motion plays when the stage is
   shown, and never under either reduced-motion switch.
   Refused: one scene per stage required (the old specs would stop drawing); the player's rest
   drawing as the fallback for every stage (a stage between two drawn ones would jump to the finished
   work and back); a scene on the last stage beside the `drawing` (two pictures for one state).
2. **A compound the page's facts name** (`services/compose_named`): with `about.compound` a CID no
   stated material holds, the composer reads PubChem's record for it (`CompoundRecords`, the lookup
   sources' PubChem adapter), then the page's own facts (`page_facts`: the facts `get_facts` lists
   whose subject is one of the craft's own concepts, as open work counts a craft's facts, at fact
   level and unit length) and keeps those that name the compound by PubChem's title as whole words,
   or by a synonym made of words when none names the title. They state the model and stand beside
   it; the model is PubChem's conformer as before. When it cannot, it says what is missing:
   `NO_RECORD` (PubChem holds no compound under that CID), `RECORD_UNREAD` (PubChem could not be read
   just now) or `UNNAMED` (no fact of the page names it; propose one). With no `about` the composer
   still composes from the materials, and its refusal now names `about.compound` as the other way.
   The tool list stays at 26; the tool's description and its `compound` argument say what the CID may
   be, naming no other tool.
   Refused: scanning every held `Compound` name against the facts with no `about` (common names such
   as lead, lime, gold and copper match ordinary words and would compose element models no fact is
   about); reading PubChem's name search for every capitalised word of the facts (many calls and
   guesses); a fact from another craft or the family (the composer cites only the craft's own).
3. **Every map layer's dataset record** (`services/layer_records`, `services/layer_guide`): a
   physical layer (`relief`, `rivers`, `minerals`) is credited from the records its own file holds
   (`physical_records`, each code once, the first download's day read and SHA-256), whether or not
   the database holds a row, and a file that names none is refused by name (`NO_LAYER_RECORD`); a
   district layer is credited from its stored `EnvDataset` row as before. The guide page `map-layers`
   (`get_page` with `guide` `map-layers/1`, listed in `contents/1`) lists every layer a map draws, the
   three physical layers, OpenStreetMap's small waters and every district layer of
   `geo/layers.MAP_LAYERS`, each with the dataset it rests on, and every record whole (code, title,
   publisher, edition, version, period, native resolution, CRS, licence and its address, attribution,
   whether it may be redistributed, citation, DOI, landing page, file, day read, SHA-256), from the
   layer files and the registry; a layer with no record is marked as refused until one is held.
   Refused: inserting the maplayers datasets into `EnvDataset` with a migration (a second copy of a
   record its file already carries, which a layer build would leave behind); a new tool (the list
   stays at 26 and `get_page` already reads guides).

## Consequences

- A page agent gives each stage the scene its facts state; Sanganeri's carving, scouring, harda,
  printing, dabu, vat, washing and sun-bleaching can each be drawn from the kit (`block`, `cloth`,
  `bath`, `water`, `heat`, `paste` and their motions).
- `compose_component` with `about.compound` 969516 composes curcumin on Sanganeri from its fact
  `cd9ee2cf`; alizarin (6293) and purpurin (6683) compose the same way from the facts naming them.
- A timeline map naming `relief` or `rivers` is delivered and credits ETOPO1 and Natural Earth with
  their versions, licences, citations, days read and SHA-256s; an agent reads the same records with
  `get_page` before it delivers.
- Tests: `backend/tests/research/test_kit_scenes.py` (a stage with its own scene kept as written and
  one without kept with none, a stage scene that moves while the drawing rests, an old spec
  unchanged, the last stage refused a scene, a drawn scene one svg held to the bar, a stage scene's
  label cited); `frontend/e2e/stage-scenes-unit.spec.ts` (the shape reads both forms and refuses an
  empty scene and a moving drawing; each stage's scene drawn beside its text and in the stage box; a
  stage without one keeping the nearest earlier stage's, or the drawing, and the last stage the
  drawing; a player with one scene drawing it at every stage); `backend/tests/compose/test_compose_named.py`
  (a fact naming the compound by whole word, the compound found by PubChem's name and composed, a
  synonym read only when the name is named by no fact, a compound no fact names refused with what to
  propose, a CID PubChem lacks or cannot read just now refused by name, a material's compound
  composed without a lookup) and `backend/tests/db/test_compose_components_db.py` (alizarin composed
  on Sanganeri from its own facts and none of Kutch Ajrakh's, curcumin refused because the curated
  facts never name it); `backend/tests/mcp/test_map_layer_records.py` (each physical layer's records
  read from its file with version, licence, citation, day and SHA-256, a file with none reading none,
  every layer listed with its record and one without flagged, the page read over MCP) and
  `backend/tests/db/test_timeline_map_places_db.py` (the physical layers credited with no database
  row, a file with no record refused by name).

## What is left

- No composer writes a stage player yet; the agent fills each stage's `scene` from the kit by hand in
  its draft, as it filled the `drawing`.
- With no `about`, the composer still finds only the compounds the materials hold; a page names a
  compound to compose by its CID.
- The `kalavigyan-craft-pages` skill's tables are the lead's to extend (the lane's report names the
  rows).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the decisions README links the two both ways. It records the choice as taken on
2026-11-28; what the code does today is in the contracts named above and in the tests listed under
Consequences.
