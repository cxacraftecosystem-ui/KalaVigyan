# 0101. One knowledge architecture for every craft: facts, sections, components, monographs

Every craft follows one knowledge architecture: facts carry their fields, article sections are
records, components are a labelled registry and one monograph template renders every subject, with
the database as the source of truth. Knowledge heals itself through one gated write path, reached
through a Knowledge API and an MCP server, with review behind a switch.

Date: 2026-11-19. Status: accepted (owner direction, 2026-11-19).

| For | Read |
|---|---|
| What amended it | [0115 MCP clients sign in with their published identity](0115-client-id-metadata-documents.md): item 15, Authentication, for published client identities |
| What built on it | [0102 Fields on facts, section records and the component registry: step 1 as built](0102-knowledge-fields-schema-as-built.md): build step 1 |
| What built on it | [0103 The MCP server, slice 1: public read tools over our own JSON-RPC framing](0103-mcp-server-read-slice.md): slice 1 of the MCP server of items 7, 9 and 15 |
| What built on it | [0104 Image contributions: declared, read byte by byte, private until approved](0104-image-contributions-intake.md): the backend of item 17's contributed pictures |
| What built on it | [0105 The Ajrakh page as structured content, rebuilt by a static build](0105-ajrakh-page-as-structured-content.md): build step 2's first half, the Ajrakh page as structured content |
| What built on it | [0106 One monograph template for every page, reached through fragments](0106-one-monograph-template-for-every-page.md): build step 2's second half and item 14 |
| What built on it | [0108 An approved structure proposal becomes a curated fact of its dossier](0108-structure-proposals-become-curated-facts.md): contributions through the gates |
| What built on it | [0110 Sources a contributor's AI can read and we cannot, and a studio to build a page in](0110-contributor-supplied-sources.md): the gates, the review switch and trust tiers, which stand |
| What built on it | [0113 Questions KalaVigyan cannot answer well become open work](0113-questions-become-work.md): item 15's open work, which gains a task kind |
| The contracts it names | [knowledge-api.md](../contracts/knowledge-api.md), [research.md](../contracts/research.md), [knowledge-writes.md](../contracts/knowledge-writes.md), [nightly-upkeep.md](../contracts/nightly-upkeep.md), [review-queue.md](../contracts/review-queue.md), [mcp-oauth.md](../contracts/mcp-oauth.md), [open-work.md](../contracts/open-work.md), [mcp-ask-and-upload.md](../contracts/mcp-ask-and-upload.md), [dossier-export.md](../contracts/dossier-export.md), [contribution-screens.md](../contracts/contribution-screens.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner: KalaVigyan will be the reference that the government and educational institutions use,
for 500 or more crafts. What is built for Kutch Ajrakh must repeat for every craft, and be
maintainable, scalable and reusable. Every section is demarcated by its field, so an agent loads
only the field a question needs. Every interactive component (map, explainer, reaction player,
molecule, chart) carries a label and a description, so a model can name a component that already
exists instead of building it again. Research done for any reader that finds something new and
non-trivial goes into the craft's article, so the database fills and heals itself. People and
their agents can contribute. Every craft gets a complete monograph, with What-if and 3D molecules,
so a reader needs no other source.

What already exists:
- **Claims** (`Claim`) with verbatim quotes and locators (`ClaimSource`) and graded sources
  (`Source`).
- A 14-field vocabulary (`models/enums.DISCIPLINES`).
- Stored answer blocks (`KnowledgePiece`, keyed by craft, field (`facet`) and topic).
- Curated dossiers in git, imported on deploy.
- Page snapshots per curation version (decision 0098).
- The novelty rule for answer pieces joining a craft page (decision 0096).

The gaps:
1. A claim's field is recorded only for curated claims (`CuratedClaim.discipline`), not for claims
   that answers write.
2. A section's prose exists only inside a page or an answer, not as its own record.
3. A stored block has no label or description, and is found by topic, not by what it shows.
4. The approved Ajrakh page is static HTML outside the data (decision 0100).
5. Curation writes JSON files to git, which contributors and agents cannot use.

## Decision

**The fact is the unit; everything else is a view built from facts.** Nothing reader-facing is
stored as free text or HTML. Every record is typed, cited, versioned and append-only logged.

1. **Facts carry their fields.**
   - Every `Claim` gets a primary field and optional secondary fields from one controlled
     vocabulary.
   - The vocabulary is today's 14 plus `SOCIETY` (people, communities, livelihoods) and `POLICY`
     (GI, law, schemes).
   - Curated claims are backfilled from `CuratedClaim`, and answer claims from the field of the
     piece they were written for.
2. **Article sections are records.**
   - `ArticleSection {subject (craft, family or category), field, version, sentences[{text,
     claimIds}], status, writtenBy, reviewedBy}` is the monograph's prose for one field.
   - A model's context receives it rendered as tagged text, for example
     `<section craft="kutch-ajrakh" field="history" version="3">... [c:<id>]</section>`.
   - The tags are a rendering of the structure, never the storage.
3. **Components are a labelled registry.**
   - `KnowledgePiece` grows into the component registry. It adds:
     - a stable `label` (e.g. `kutch-ajrakh/chemistry/indigo-redox-player`);
     - a `title`;
     - a two- or three-sentence `description` written for a model;
     - its fields;
     - links to the subjects it shows: crafts, concepts, places and compounds.
   - The answer pipeline gives the model a catalogue of the components relevant to the question,
     one line each: label, kind and description.
   - The model names a label to place an existing component. A builder runs only when nothing in
     the catalogue fits, and what it builds is registered.
   - Components keyed by concept, place or compound are shared by every craft they apply to:
     - an indigo reduction player by every indigo-dyed craft;
     - a Kachchh map by every Kachchh craft;
     - a molecule by every craft that uses that compound.
4. **One monograph template for every subject.**
   - Fields map to the fixed chapters of decision 0095.
   - The approved Ajrakh page is decomposed into its sections and registered components, and its
     design becomes the one renderer for every craft, family and category.
   - Parity with the approved page is proven by screenshots before the static file is retired.
   - Each chapter has a completeness score per craft. Missing What-if, molecules, places or fields
     become research tasks.
5. **Self-healing, through one gated write path.**
   - Every new fact, whatever its origin, is a candidate:
     - an answer's research;
     - a curator;
     - an artisan's testimony;
     - a contributor;
     - an agent.
   - It is published only through these automatic gates, in order:
     1. every quote is verified verbatim against the fetched source text;
     2. the source is graded and its licence allows it;
     3. it is not a duplicate of the subject's facts in that field (embedding neighbours, then a
        fact-level comparison);
     4. it is not trivial: it adds to or changes what the section says. The judge's reasons are
        stored.
   - A disagreement with an existing fact is published as "sources differ", never resolved.
   - A fact that passes joins the article section as a new version, marked as added from research
     with its date, at a provisional level, and enters the professor review queue.
   - Review raises its level or retracts it, and the page rebuilds.
   - Nightly upkeep, bounded per night:
     - re-verifies quotes and archives sources at risk of link rot;
     - rebuilds sections and components whose facts changed;
     - turns coverage gaps into targeted research tasks.
6. **The database is the source of truth.**
   - The git dossiers become a versioned export (backup, diff and bulk import), not the place
     curation is written.
   - The curation skill keeps the method. The writes go through the API below.
7. **One Knowledge API, with an MCP server on it.**
   - Read: find crafts, get sections by field, list and get components by label, get facts with
     quotes and sources.
   - Write: propose a fact, a source or a component; review.
   - It is used by the web app, research jobs, Claude Code curation (the skill), institutions'
     agents and contributors, each with its role's rights.
   - The MCP server is remote over HTTPS with per-user authentication. It exposes the same
     operations, so any agent can read the database and propose to it, and every write passes the
     gates in 5.
8. **Contribution.**
   - Readers, researchers and artisans propose through the same path, under a contribution licence
     and with credit.
   - Trust follows role and record: a trusted contributor's facts are reviewed sooner, never
     ungated.
9. **Open and citable.**
   - Every craft's monograph is citable by version.
   - Public read API, MCP read tools, and a per-version bulk export (facts with quotes and sources,
     sections, component specs).
   - Closed-licence quotes are withheld from public views and exports.

10. **Retrieval is per fact, not per section** (owner, 2026-11-19).
    - A question loads only the facts it needs. Hybrid search runs over the facts of the craft
      and the question's fields:
      - keyword search on `Claim.tsv`;
      - vector neighbours on `Claim.embedding`;
      - entity matches on the question's materials, places and compounds.
    - The matches are re-ranked, and the top facts are sent with their quotes. A fact's
      neighbouring sentences come along only when it needs them to read clearly.
    - A whole section is sent only for a broad question ("tell me about its history").
    - The component catalogue is filtered the same way: only components whose field, subject and
      description match are listed.
11. **Pages are built nightly as static pages** (owner, 2026-11-19).
    - Every night after upkeep:
      1. the database rebuilds every changed page snapshot;
      2. a scheduled job triggers one production build;
      3. every craft, family and category page is pre-rendered from those snapshots and served
         from the CDN.
    - Whatever was added during the day appears the next morning and loads fast.
    - An admin can trigger the same build at any time.
    - Answers stay live.
12. **Review has a switch** (owner, 2026-11-19).
    - One admin setting, which may be set per origin (research, contribution, agent):
      - `AUTO`: a fact that passes every gate goes live, marked unreviewed, and stays in the
        review queue;
      - `APPROVAL`: a Professor or Admin approves before it goes live.
    - **The default** (owner, 2026-11-19): `AUTO` for our own research, `APPROVAL` for
      contributors and outside agents.
    - **Consent cannot be revoked** (owner, 2026-11-19). A published contribution stays
      published; a contributor can withdraw only what is still waiting for review.
    - **Reviewers' own contributions are approved at once** (owner, 2026-11-19). A proposal made
      by a Professor, Admin or Master Admin account, whether on the site, through the Knowledge
      API or through the MCP server, goes live as approved whatever the switch says. It still
      passes the automatic gates in 5, and it does not enter the review queue. The role is read
      from the signed-in account behind the token at the moment of the write, never from the
      request.
    - **Admins review everyone else's contributions in admin settings** (owner, 2026-11-19). An
      Admin or Master Admin sees every pending contribution from other people, whatever its
      origin (the site, the Knowledge API, the MCP server, an artisan's testimony), and approves
      or rejects each one there, with a reason kept for a rejection. The queue builds on the
      testimony review that exists (`/testimony/review`), so there is one review path, not two.
13. **No public credit for contributors** (owner, 2026-11-19).
    - Contributions show no contributor name.
    - Who proposed what is kept privately, for moderation, withdrawal and audit only.
    - Contributors accept terms that let the Centre publish their contribution without
      attribution.

14. **Formatting is a separate layer** (owner question, 2026-11-19). Content and presentation
    never mix. Formatting is controlled at three levels, and none of them lives in a fact:
    - **The template** (the design system and the monograph renderer) sets the look of every
      page. A change there reaches every page at the next nightly build.
    - **A layout record per page**, `PageLayout {subject, version, entries[{label, chapter,
      order, role (HERO, OPENER, PLATE, FIGURE, SIDEBAR, PULL_QUOTE, ...), crop, size, caption
      override}]}`. It refers to sections and components by label and sets:
      - chapter order;
      - which component leads;
      - where pictures sit and how they are cropped;
      - pull quotes and figure order.

      The dossier's picture placement and focal box (schema 2) move into it. Editing a fact
      never breaks a layout, and editing a layout never touches a fact.
    - **Inline marks in sentences**: a small fixed set of italic (native terms, species names),
      formula (subscripts and charges), term link and citation, stored as structured spans. Never
      HTML.

    A one-off visual for a single craft is built as a new component kind with its own spec, never
    as free-form HTML. The approved Ajrakh look is its template plus its layout record, proven by
    screenshot parity.

    **The Ajrakh switch-over changes nothing a reader sees** (owner, 2026-11-19).
    - The static page stays live until the page built from data matches it on three counts:
      1. text: every sentence, citation number and caption is identical (an automated diff);
      2. screenshots at 360, 834 and 1440, in light and dark;
      3. interactions: players, popovers, Listen, Ask and the chapter rail.
    - After the switch, new content never reorders an approved layout. A new fact joins its
      section in place, marked as added. A new component is placed at the end of its chapter and
      flagged for a layout review.

15. **The MCP server** (owner, 2026-11-19).
    - **Remote MCP over HTTPS.** Every tool is backed by the Knowledge API, so a write passes the
      gates in 5 and the review switch in 12.
    - **Read tools:**
      - find crafts;
      - get facts by craft and field (retrieval as in 10);
      - get sections;
      - list and get components by label;
      - get a page's layout;
      - search.
    - **Ask:** the reader's own agent gets an answer from our pipeline. The answer comes back as
      structured data (cited sentences, component labels and sources) and in our design:
      - as interactive UI the client renders, through the MCP Apps UI-resource extension where the
        client supports it;
      - otherwise as a link to the same answer on our site;
      - plus a design-kit resource (tokens and component specs) for agents that draw it
        themselves.
    - **Contribute:**
      - propose facts with quotes and sources;
      - propose components;
      - propose a page layout for a page not yet in the new form, or a change to one.
      All of these go through the same gates and the review switch.
    - **Authentication:** OAuth 2.1 as the MCP authorization spec defines, with our web app as the
      authorization server. The flow:
      1. The user adds our server URL in their MCP client.
      2. The client opens our site.
      3. The user signs in and accepts the MCP terms of use. The terms are versioned, and
         acceptance is recorded per user.
      4. The user approves the scopes (read, ask, contribute, review by role).
      5. The client receives a token and the user returns to the client.
      Settings lists every connected client, with revoke. A changed terms version asks again at
      the next sign-in.
    - **Guards:**
      - a rate limit per token, which protects the service and is not a spend cap;
      - an audit log of reads and proposals per token;
      - only public-level data: no personal data and no restricted field material;
      - closed-licence quotes withheld;
      - contributed and sourced text always returned as data, never as instructions;
      - new accounts' proposals can be held for approval by the switch;
      - versioned tool schemas, so institutions' integrations do not break.
    - Every response carries its citations and source licences, and the terms ask users to name
      KalaVigyan and the Centre when they show our content.
    - **Open work** (owner, 2026-11-19): contributors' agents can ask what still needs work.
      - `list_open_work` takes optional filters (craft, family, category, field, task kind, priority)
        and returns tasks from each subject's completeness score:
        - a missing or thin chapter or field;
        - a missing component (What-if, molecules, map, reaction player, pictures);
        - a page not yet in the new form or without a layout;
        - facts awaiting a second source;
        - sources-differ entries that need a deciding source;
        - dead or unarchived sources;
        - review queues, for reviewers only.
      - Each task carries what is needed, its acceptance rule (from the page checklist and the
        coverage targets) and its priority. Priority follows reader demand, GI status and the
        owner's order.
      - `claim_task` reserves a task for a set time, so two agents do not do the same work.
        `release_task` gives it back, and an expired reservation returns to the list.
      - A proposal that completes a task closes it once it passes the gates.
    - **The method travels with the server** (owner question, 2026-11-19). A contributor's agent
      researches and writes with the same method our curators use, in two forms built from the
      `kalavigyan-craft-pages` skill:
      - **MCP prompts** every client lists: research a field of a craft, write a section from
        facts, propose a component. Each carries the method (what counts as a source, verbatim
        quotes with locators, one fact per sentence, the field vocabulary, the page checklist) and
        names the tools to call in order: `list_open_work`, `claim_task`, `get_facts` and
        `get_section` to see what is held, the agent's own search, then `propose_fact` or
        `propose_component`.
      - **A downloadable `kalavigyan-contributor` skill**, the same method for agents that load
        skills, offered as an MCP resource and on the site.
      Contributors generate facts with their quotes and sources, never published prose. Our
      gates fetch each source and re-find each quote themselves, and the section prose is
      rebuilt on our side from the facts that pass.

16. **A component is made only when the library has none** (owner question, 2026-11-19).
    - `list_components` is the library's search: words over label, title and description, and a
      craft brings its own components plus every shared one keyed to its concepts, compounds and
      districts. Each result names what it is keyed to. Live in slice 1
      (`docs/contracts/knowledge-api.md`).
    - The method's first step, in the MCP prompts and the contributor skill, is that search.
    - `propose_component` (slice 3) runs the same search on the proposal's title, description and
      subjects, and the proposal lists the labels its agent considered. A close match refuses the
      proposal with the matches and two ways on: place the existing component by its label, or
      propose an extension of it (a new subject link or a variant). Never a copy.
    - `list_open_work` lists the components a page lacks, computed from the registry, so agents are
      sent to gaps rather than guessing.
    - The library is empty until build step 2 registers the Ajrakh page's components; no writer
      sets a label before then.
17. **Contributed images, AI-made ones included** (owner question, 2026-11-19).
    - **The image travels outside the chat.** An agent cannot hand over the bytes of an image it
      made (ChatGPT cannot pass them into a tool call), and base64 in a tool argument costs over a
      million characters for a 1 MB picture. So `start_image_upload` (MCP, signed in) returns a
      single-use link to our site, valid for 30 minutes and tied to the person and to the facts the
      picture illustrates. The person drops the file there, from a phone too. Agents with a shell
      get a presigned upload URL for the same slot instead.
    - **Declared at upload:**
      - its origin: photograph, drawing or AI-generated;
      - for an AI image, the tool and model and the prompt;
      - the stage and facts it shows;
      - that the uploader holds the rights to give it under the contribution licence.
    - **Checked on our side:**
      - the type from the bytes (PNG, JPEG or WebP), the size and dimensions;
      - location and camera metadata stripped;
      - Content Credentials (C2PA) read. A file whose credentials say AI-made but which is
        declared a photograph is refused.
    - **Stored as a `MediaAsset`**, the table the app's own generated pictures use, with the origin,
      the generator and the contributor. Private until approved, with the second approval that
      named-cluster pictures already need.
    - **Approval follows item 12.** A Professor's, Admin's or Master Admin's picture is approved at
      once; anyone else's waits in the admin review queue.
    - **An AI image is an illustration, never evidence.**
      - It is always labelled "Illustration, made with <tool>", never shown as a photograph.
      - It may show a mechanism, a diagram or a process step.
      - It may never stand for a real artisan, a named place, a GI product, a historical object
        or any real person's likeness.
      - The reviewer checks it against the facts it illustrates (the colour of leucoindigo, the
        order of the steps).
    - **Order of work:** the upload page and the review queue in the web app (they need only
      today's sign-in), then slice 2's OAuth, then the MCP tool that hands out the upload link.

Scale: 500 crafts at about 150 facts each is about 75,000 facts, 200,000 quotes, 10,000 sections
and 20,000 components. Postgres with pgvector and the page snapshots carry this without new
infrastructure.

## Build order (each step ships on its own)

1. Schema:
   - fields on every claim, plus the backfill;
   - `ArticleSection`;
   - registry fields and subject links on `KnowledgePiece`;
   - the two new fields in the vocabulary.
2. Decompose the Ajrakh page into sections and components, and make its design the template
   renderer. Prove screenshot parity, then render every curated craft with it.
3. Answers retrieve by field and place components by label.
   - Built 2026-11-19, the retrieval half: `KnowledgeQuery.fields` keeps the claims filed under
     the asked fields (as field or secondary field) and the claims with no field yet; the
     research planner searches each section's stored facts in its own field, the overview in
     every field; claims gain a third ranking, the scoped concepts the question names, fused
     with full text and vectors (`docs/contracts/research.md`).
4. The candidate gates, the review queue and nightly upkeep.
   - Built 2026-11-19: the gates and the review switch (`docs/contracts/knowledge-writes.md`),
     nightly upkeep with orphaned concepts and the nightly static build
     (`docs/contracts/nightly-upkeep.md`); the unified review queue (`docs/contracts/review-queue.md`).
5. The Knowledge API write path and the MCP server; switch the curation skill to it; the dossier
   export.
   - Built 2026-11-19: `propose_fact` on the API and MCP, MCP sign-in (`docs/contracts/mcp-oauth.md`),
     open work, task reservations, `propose_component`, MCP prompts and resources and the
     contributor skill (`docs/contracts/open-work.md`); `ask` and `start_image_upload`
     (`docs/contracts/mcp-ask-and-upload.md`); the curation skill on the write path and the dossier
     export (`docs/contracts/dossier-export.md`).
6. Completeness-driven research for every curated craft, then the rest: every chapter, What-if
   and molecules.
7. Contribution screens and the bulk export.
   - Built 2026-11-19, the bulk export: `GET /api/knowledge/crafts/{slug}/export` and
     `app.scripts.export_knowledge` give each craft's public facts with quotes and sources, its
     published sections and its components, citable by curation and section version
     (`docs/contracts/knowledge-api.md`); the contribution screens for facts and components
     (`docs/contracts/contribution-screens.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-19; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
