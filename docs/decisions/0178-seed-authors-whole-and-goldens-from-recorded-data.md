# 0178. The seed names an organisation as one author, Kutch Ajrakh's fixture market shows its curated price, and the goldens show recorded rain, a placed component and a craft's own names

The seed claims are converted again from the two sibling checkouts so that an organisation is one
author; the phase D fixture's Kutch Ajrakh market shows the dossier's 1975 Barmer price; the
goldens show Kachchh's recorded CHIRPS monthly normals, the Kutch Ajrakh red player placed with the
sources its monograph load records, and the craft's own names from its dossier; and the seed
converter, the claim seed and the map points are cut into named steps.

Date: 2026-11-23. Status: accepted (the lead's evening round brief of 2026-11-23, lane B, within
the owner's go-ahead of 2026-11-22 to clear the register "not just for this round, also for all
time"). It amends [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md)
(the goldens that show every served field, and the Python left over budget) and follows
[decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) (the authors' split rule and
the seed's restamp). The contracts are `docs/contracts/crafts.md` (the seed claims),
`docs/contracts/craft-page.md` (`LocalName`) and `docs/contracts/region.md` (the Geo ETL extract).

| For | Read |
|---|---|
| The goldens' field check and the Python split it continues | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md) |
| The split rule for authors and the seed's restamp of a stored import source | [decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) |
| Signs of imitation from GI journal text only | [decision 0066](0066-local-measures-and-market-gi.md) |
| Components as a labelled registry a model can place | [decision 0101](0101-knowledge-architecture-for-every-craft.md) |
| What is still below standard | [TECH_DEBT.md](../TECH_DEBT.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Four register entries were open in lane B's area. `backend/app/data/seed_claims.json` still held
authors split on commas and "and" (the V&A as "Victoria" and "Albert Museum", the GI journal's
applicant note as two authors, the AIACA as two), and so did 24 goldens and the citation export
built from them. The phase D fixture's Kutch Ajrakh market showed no price although the dossier
states one. `backend/tests/contracts/unshown_fields.json` listed 40 fields no golden showed, among
them the seasons block's rainfall, the placed component block and `PageCraft.local_names`, which
nothing filled. `etl/crafts/seed_claims.py` (637 lines), `claim_seed.seed_claims`, its database
test and `knowledge_view.map_points` were over budget.

The immersive-episteme and inferential-system checkouts are beside the repository, and every input
the seed records by sha1 is unchanged, so a conversion run changes only what the conversion code
changed. The Geo ETL's run 44204618054 kept its `geo-district-env` artifact, whose CHIRPS file
holds the twelve `monthly_precipitation` normals of Kachchh that the recorded extract left out.
The design system's principle 8 already says a craft's names appear in their own scripts only
where a source states them and names the craft, and the Kutch Ajrakh dossier states two (claim
C152).

## Decision

1. **The seed is converted, not patched.** `python etl/crafts/seed_claims.py` against the two
   checkouts rewrote `seed_claims.json`; the only change is 15 sources' authors, by
   `source_authors.split_authors`. Every golden that carries one of those sources takes the new
   list, and `shared/learning.citations.golden.json` is rebuilt through `citation_entries` and
   `apa_references`, so its APA, BibTeX and RIS read "Victoria and Albert Museum. (2007)." and the
   registry with its applicant note as one author. The authored Kutch Ajrakh monograph keeps the
   sources it was written with (`content.json`, `monograph.document.golden.json`): this lane does
   not change what that page draws.
2. **The phase D market shows the curated price by its curated id.** `s5.b1` carries C049's price
   as the market builder writes it from the dossier (`curation_keys.curated_id`), cited to the
   Sahapedia page (S13), which joins the fixture's sources in order of first citation. Its APA text
   is "Mushtak Khan. (n.d.). Ajrakh: An Introduction. Sahapedia. Retrieved November 17, 2026, from
   https://www.sahapedia.org/ajrakh-introduction-0", checked by hand against APA 7 for an undated web
   page with the house's literal author names. Kutch Ajrakh still shows no sign of imitation: no
   GI journal text states one (decision 0066).
3. **Recorded rain sits beside the extract's values, not in them.** The extract's new `monthlyRain`
   holds the twelve rows read from run 44204618054's CSV, in the columns of `values`;
   `golden_region.kachchh_rainfall` reads them as the database keeps them and the phase B seasons
   block shows them with the CHIRPS row the climate block cites. Adding them to `values` would have
   changed every golden and database test built from Kachchh's rows.
4. **A placed component's golden is a block fixture recorded by a database test.**
   `shared/explainer.component.golden.json` holds the red player as the catalogue places it, with
   its eight sources; `tests/db/test_component_sources_db.py` imports the dossiers and categories,
   loads the Kutch Ajrakh monograph and checks the stored piece's sources and their records against
   it, so the golden is what the load records, not a value chosen for the test.
5. **A craft's own names come from its dossier.** `craft_page` fills `PageCraft.local_names` from
   the dossier's `nativeNames` whose claim the page shows, in the dossier's order, rather than
   retiring the field. The web already parses the field; the craft page golden shows the two names.
6. **The over-budget Python is split along its steps.** The seed converter is `seed_terms`,
   `seed_immersive`, `seed_inferential` and `seed_claims` (build and the command); the same inputs
   give the same file byte for byte. `claim_seed.seed_claims`, its idempotence test and
   `knowledge_view.map_points` keep their behaviour in named steps. Only the initial migration
   stays over budget, by choice (decision 0168).

## Consequences

- The next deploy's seed restamps the 15 stored import sources' authors (decision 0166); nothing
  else in the database changes. The Kutch Ajrakh monograph's sources keep the split GI journal
  author until its own content is rebuilt.
- `unshown_fields.json` falls from 40 fields to 21; what is left waits on a groundwater load, a
  stated regional factor or ΔH, a reaction player that infers formulas, a recorded live-research
  paper with its journal, and the owner's decision on translated category pages.
- The craft page golden changes by its two local names; the lead regenerates whichever of this
  lane's and the shell lane's craft page goldens merges second.
- The hygiene baseline falls to 1 oversized file, 1 long function and no wide function.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `etl/crafts/tests/test_seed_authors.py`,
`backend/tests/contracts/test_explainer_phase_d.py`, `backend/tests/answering/test_market_builder.py`,
`backend/tests/contracts/test_seasons_rainfall_contract.py`,
`backend/tests/contracts/test_component_block_contract.py`,
`backend/tests/db/test_component_sources_db.py`, `backend/tests/curation/test_craft_page_context.py`
and `backend/tests/contracts/test_golden_fields.py`.
