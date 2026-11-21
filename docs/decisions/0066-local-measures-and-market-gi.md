# 0066. Local measures, and market and GI

The `measure` and `market_gi` blocks are built with no model choosing: units are Pint's, a regional
factor must be a stated equality, and GI status, imitation and prices are the registry's and the
sources' own words. There is one market block per craft.

Date: 2026-11-18. Status: accepted. Amended by 0070 (GI and price dates are shown
only as precisely as their quotes state them).

| For | Read |
|---|---|
| What amended it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md): GI and price dates are shown only as precisely as their quotes state them |
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase D lane 0066 (plan section 4, features 8 and 13; section 3, units; owner decision O5)
builds the `measure` and `market_gi` blocks to the fields decision 0062 fixed. Their renderers
exist (decision 0068), so this lane adds the builders and joins both kinds to
`BUILT_BLOCK_KINDS`. Rules that bind: a quantity in a local unit is converted only by a value a
cited source states for that region (O5) and is otherwise shown as written; a GI status is the
registry's (the curated `CraftGiRecord` of decision 0053, else the stored claims); signs of
imitation are GI journal text; a price carries its date and place; no number comes from a model;
nothing waits on a model or HTTP call while a connection is held (decision 0040).

## Decision

1. **No model chooses anything here.** The contract allowed a model to pick imitation claims. As
   in decision 0064, fixed server rules choose instead, so neither builder spends, touches the
   router or differs between readers, and every rule is testable by hand.
2. **Units are Pint's, words are fixed.** `research/measures` gains the fixed unit words
   (`DEFINED_UNITS[...].words`) and `LOCAL_UNITS`: fifteen Indian units (seer, maund, tola,
   chhatak, masha, ratti, pao, gaj, hath, bigha, biswa, kanal, marla, guntha, katha) with their
   spellings and the quantity each measures. `research/unit_registry` holds the one Pint registry
   (built on first use; the science engine's condition units now use it too, so the small box
   keeps one): each local unit is defined as a dimension of its own, so Pint knows it and can
   never convert it by itself, and Pint reads the metric unit a source states (with `kilo`,
   `kilos`, `gm`, `gms`) and checks that it measures the local unit's quantity. The arithmetic
   stays the contract's decimal rule (`metric_value`).
3. **A stated quantity.** `research/stated_quantities.stated_quantities` reads a number or a
   range (`10-15`, `2 to 2.5`) directly before a unit word (`6-foot` too); a bare word ("pounds
   it with the feet"), a word number ("one foot") or a falling range is not a quantity. Defined
   units convert by their exact definition, cited to the NIST row; a local unit converts only by
   a regional factor.
4. **A regional factor is a stated equality.** `stated_factors` reads "a seer of Kachchh weighs
   0.933 kg", "one maund was equal to 37.32 kilograms", "933 grams make a seer": a single local
   unit, an equality word, a number and a metric unit of the same quantity. A factor through
   another unit ("1 seer = 80 tolas"), a yield ("one maund of cotton yields 12 kg") or a price is
   refused. The region is the one register district or state the quote and its claim name
   (`services/measure_regions.stated_region`); two places, a district outside a named state, or
   a spelling the LGD register does not hold ("Kutch") give no region and no factor. A factor
   applies when its district holds the craft or its state holds one of the craft's places
   (`CraftLocation`, located points, the master list's states of practice); a district's value
   beats its state's, and two different values at the narrowest level convert nothing.
5. **The measure builder.** `services/measure_builder.MeasureBuilder` joins every field, reads
   the quantities of the section's fact-level cited claims, and only when one is in a local unit
   reads, in one short session, the craft's places and the stored claims whose quotes name that
   unit (`services/measure_store`, at most 60, by a Postgres word match). Rows are at most 12,
   each stated quantity of a claim once, each with its own sentence id; a row or conversion the
   contract refuses is left out; no row, no block. A measure is a piece in its section's slot and
   is not rebuilt on reuse.
6. **GI status.** `services/market_store` reads, per craft, its `CraftGiRecord`, its
   `CraftPrice` rows and the claims about its own concepts that cite a `GI_JOURNAL` or
   `GOVERNMENT_REPORT` source and name a registry or imitation word (at most 80), then the
   visible claims and sources, in one session. With a record, its fields and the record's claims
   whose every citation is a registry source are the status, or none (logged) when they do not
   state it. Without one, `research/gi_registry` reads the application and certificate numbers,
   journal issue, filing and registration dates, applicant names and authorised users from each
   registry claim's text and quotes by their labels (a logo application is not the craft's); two
   claims stating different values give no status. The status follows the contract:
   `REGISTERED` with a certificate or registration date, `APPLIED` with only an application,
   `WITHDRAWN` when a sentence says so; a sentence saying "registered" with no date or
   certificate gives none rather than "applied for".
7. **Imitation and prices.** Signs of imitation are fact-level claims citing a GI journal whose
   text names imitation or passing off (fake, imitation, counterfeit, spurious, knock-off, passed
   off, screen-printed, machine-made, power loom, mill-made), at most three, best ranked first.
   "Substitute" alone names a material's replacement (German indigo for natural), not an
   imitation, so it is not a sign. Prices are the curated `CraftPrice` rows only (the contract's
   source): the currency and numbers as the claim states them (`research/stated_prices`), `per`
   only from "per" or "/", at most six; a row whose date year or place its sentence and quotes do
   not state is dropped.
8. **One market block per craft.** `MarketGiBuilder` joins `ECONOMICS` sections and builds a
   block for the answer's craft and each compared craft. It is rebuilt on reuse for the crafts a
   reused section does not already show, and `piece_store.kept_for` keeps only the answer craft's
   block as a piece (`PieceLookup.craft_slug`), so a comparison's other crafts are always rebuilt.
9. **Built.** Both kinds join `BUILT_BLOCK_KINDS` on both sides and `PIECE_BLOCK_ORDER` after
   `supply_map`.

## Consequences

- After the deploy an economics section shows the curated GI record of Kutch Ajrakh and Bastar
  Dhokra (Kutch Ajrakh with its 1975 Barmer price, Bastar Dhokra with its 2025 brass price) and
  the registry claims of seeded crafts (Bagru with its GI journal sign of imitation); Tikuli's
  only price is dropped because no source states its year. Any section converts feet, inches,
  yards, miles and square feet; a local unit stays as written until a source states its value
  for the craft's region.
- No migration, no data run and no owner step.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
