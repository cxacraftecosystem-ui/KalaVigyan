# 0102. Fields on facts, section records and the component registry: step 1 as built

Build step 1 of decision 0101 is built as a vocabulary of 16 fields, a field on every claim with a
backfill, `ArticleSection` records and the component registry's fields on `KnowledgePiece`. The new
tables are closed to the public roles.

Date: 2026-11-19. Status: accepted (built without the owner present, on the owner's instruction to
continue on Claude's recommendations; each choice below can be revisited).

| For | Read |
|---|---|
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): build step 1 |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0101's build order starts with the schema: fields on every claim with a backfill,
`ArticleSection`, registry fields and subject links on `KnowledgePiece`, and two new fields in the
vocabulary. The decision names the records but leaves their exact columns, the backfill's order and
where the two new fields sit in the answer engine open.

## Decision

1. **The vocabulary has 16 fields.** `SOCIETY` (communities, families, livelihoods) and `POLICY`
   (Geographical Indication, law, public schemes) join the 14.
   - Chapters: `SOCIETY` reads in "People and voices", `POLICY` in "Market and GI".
   - Expert seats: the anthropologist, economist and artisan seats cover `SOCIETY`; the GI and
     policy expert leads on `POLICY`, and the economist covers it too.
   - Builders: the market and GI block joins `POLICY` as well as `ECONOMICS`. A field interview may
     support a `SOCIETY` sentence on its own, as it already may for process, materials, design and
     economics.
   - Question cues are conservative (community, caste, tribe, guild, livelihood, women; GI,
     geographical indication, law, legal, scheme, policy, regulation, registration, and the Hindi
     words), so no existing question changes field.
   - An Expert answer may hold one section per field, so up to 16, and a lesson may take all of
     them: `LESSON_SECTIONS_MAX` is the field count on both sides, not a typed number.
2. **A claim's field.** `Claim.field` (the primary field, nullable) and `Claim.fields` (secondary
   fields, never containing the primary, empty when there is no primary).
   - A null field means "not known", never a guess. Nothing falls back to `OVERVIEW` in storage;
     a reader that needs a field keeps its own fallback.
   - The backfill (migration `0032_knowledge_fields`) takes, in order: the curated dossier's
     discipline, the curated category's discipline, the artisan contribution's discipline, the
     facet of the earliest stored piece that cites the claim, then the claim's concept type through
     `CONCEPT_TYPE_DISCIPLINES`. Concept types with no field there (`OUTCOME`, `OPEN_QUESTION`,
     `COMPARISON`, `CONCEPT`) stay null.
   - Secondary fields are the other facets of every stored piece that cites the claim.
   - Writers stamp the primary field from now on: the curation and category importers (the
     dossier's discipline, compared like any other column, so a changed discipline updates the
     claim), live research write-back (the subject's concept type), artisan testimony (the
     contribution's discipline) and the claim seed (the subject concept's type).
3. **`ArticleSection`** holds one subject's prose for one field, as versions.
   - The subject is `craftId` or `categoryId`, exactly one, each with a foreign key, rather than a
     loose subject type and id, so a deleted craft takes its sections with it.
   - `sentences` is a JSON array of `{text, claimIds}`, never empty; `research/article_sections`
     is its contract and renders it as tagged text for a model, escaping angle brackets so a
     sentence cannot close its tag.
   - `status` is `PROPOSED`, `PUBLISHED`, `SUPERSEDED` or `RETRACTED`. At most one version per
     subject and field is published, and each version number is used once.
   - `writtenByKind`, `writtenById`, `reviewedById` and `reviewedAt` keep who wrote and who
     reviewed it, privately (decision 0101, item 13).
4. **The component registry** is four nullable columns on `KnowledgePiece`: `label`, `title`,
   `description` (at most 600 characters) and secondary `fields`.
   - A label is `<owner>/<field>/<name>` or longer, lower-case words joined by hyphens, unique, and
     needs a title and a description. Pieces stored before today have none; step 2 registers them.
   - `KnowledgePieceSubject` links a piece to each subject it shows. The kind is `CRAFT`, `CONCEPT`,
     `PLACE` or `COMPOUND`, with exactly the matching column set. Crafts, concepts and compounds
     are foreign keys. A place is a key, `lgd:<code>` or `basin:<id>`, the same prefixes stored
     pieces already use, now defined once in `models/enums`.
5. **New tables are closed to the public roles** like every other table (row level security on,
   `anon` and `authenticated` revoked).

## What follows

- Step 2 fills `ArticleSection` and registers the Ajrakh page's components from the approved page,
  without changing what a reader sees.
- The downgrade maps `SOCIETY` to `OVERVIEW` and `POLICY` to `ECONOMICS` before restoring the
  14-field checks, so a database can go back without losing rows.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-19; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
