# Next

Start here in a new session: what is live now, the release status, the owner's decisions, the two
big tracks and how to work. The lead keeps it current. Every choice made without the owner is
recorded below or in decisions 0102 and 0103 for review.

| For | Read |
|---|---|
| Everything done, in order | [PROGRESS.md](PROGRESS.md) |
| What is knowingly below standard | [TECH_DEBT.md](TECH_DEBT.md) |
| How to deploy, switch on and roll back | [RUNBOOK.md](RUNBOOK.md) |
| The owner's standing direction | [PLAN.md](PLAN.md), section 0 |

This handoff began in the night session of 2026-11-19: the owner went to sleep and asked Claude to
finish the release and start on decision 0101's database and MCP work on its own recommendations.

## Live now

- **KalaVigyan `main` at `53d8b43`** (2026-11-21), round 7 shipped in steps (`d0167f9`, `90b79f6`,
  `53d8b43`), each checked on GitHub and its Vercel build confirmed READY:
  - **Contribution at scale:** the queued gates, batches, idempotency keys, trust tiers, task leases,
    stewardship, delivered components and pages with a private preview, pictures in every format with
    screens, healing (held facts, link rot) and the expert seats' capped research.
  - **The MCP studio (decisions 0110, 0111):** 21 tools in six groups (reading, sources, work,
    proposing, pages, pictures); KalaVigyan's own source registries, fetcher and quote matcher as
    tools; sources only a contributor can read, supplied and checked against their text; a draft per
    page with a preview report on the 26 checklist rules, drawn in the chat; the `curate_page` prompt;
    every skill, reference and contract teaching it.
  - **Pages:** every borrowed component drawn in its home's styles (the Textiles chemistry), figures
    beside the sentences they illustrate, a view missing a unit left out instead of breaking the page,
    and a parity check of each borrowed component after every deploy; Kutch Ajrakh at 90 on a phone.
  - **Maps:** the Natural Earth base, relief, rivers and mineral layers with their palettes, the Survey
    of India state lines on every map, and switching layers without an error.
  - **Open, being built:** the round 7 fix lanes (release proof, integrity, connect and speed,
    monograph follow-ups, artisan photographs), then questions becoming work, why here, kinds and
    datasets, and design conformance (`docs/TECH_DEBT.md`, round 7).
- **Portals 0.0.8** (designer-portal `2d468af3`, documentation-portal `28abc96d`), released together:
  - field voices for KalaVigyan;
  - question takes name their section;
  - the designer portal's identity-photo PENDING stamp.
  - Android is not published with this release; the `PUBLICATION` consent value ships with the
    next Android build.
- **Switches set this session:**
  - Parameter Store:
    - `ALERT_DIGEST_ENABLED=true` (SES has production access, and the domain is verified with DKIM);
    - `ARTISAN_CONVERSATION_ENABLED=true` with `ELEVENLABS_ARTISAN_AGENT_ID=agent_0901m7rcnsz5f379ejhxyd47bbqv`
      (key permissions checked from the box: all four answer 200; the agent id is also a GitHub secret);
    - `FIELD_VOICES_ENABLED=true` and `FIELD_VOICES_IMAGE_HOSTS`;
    - `MCP_SERVER_ENABLED=true`.
  - Both portal repositories' Actions variables: `CROSS_PORTAL_FIELD_VOICES_ENABLED=true` and
    `FIELD_VOICES_RIGHTS_HOLDER`.
  - The `field-voices/*` grant is applied to both portals' media keys.
  - The box policy reads `/kalavigyan/e2e/*`; the Professor and Admin E2E accounts are provisioned.
- **Kutch Ajrakh.** `/crafts/Kutch-Ajrakh` serves the owner-approved monograph
  (`frontend/public/monographs/kutch-ajrakh/index.html`, decision 0100; published copy
  https://claude.ai/artifact/YBrq1VNAZosQTbppNziK9p; build scripts in `docs/design/monograph-build.zip`).
  - The served file now has one override block, `style#kv-release-fixes`. The published copy and
    the build scripts do not have it.
- **The institution's name** is "Centre of Excellence for Unified AI-Enabled Craft Ecosystem
  Platform", IIT Kharagpur. Never "for Handicrafts".

## Release status

- **Done:**
  - **Field voices refresh on both portal boxes:**
    - designer portal: 2 images;
    - documentation portal: 501 transcripts and 613 images, with 3 originals missing from the
      bucket;
    - KalaVigyan's `field-voices-sync.yml` applied all of them, ok.
  - **Both portals' release gates** pass (`44431722874`, `44431727650`).
- **Never flip `field_voices.artisan_images`** before a person has reviewed the held list. It may
  contain Aadhaar cards.
- **The production E2E** (latest run `44432649960`): 17 passed, 10 screen runs failed, 1 skipped.
  - The Professor and Admin accounts now pass.
  - Every curated craft page renders.
  - The failures that remain are findings, not regressions from this release:
    1. **The router's prefetch of `/crafts/Kutch-Ajrakh` answered 404** while the craft was
       rewritten to its static page. Gone since 2026-11-20: the craft draws its document.
    2. **Sanganeri's Region tab** runs about 70 screens before "All measurements", against a
       limit of 3. This is a design problem of the tabbed craft page; the redesign or track 1,
       step 2 replaces it.
    3. **The monograph** has no app theme attribute, and some small labels spill out of their
       boxes at some widths ("leucoindigo, on the fibre", the Devanagari brand). These are design
       details of the approved page; see the critique.
    4. **Occasional 500s from the five-connection database pool** under four parallel browsers
       (`docs/TECH_DEBT.md`, Infrastructure).

## Owner decisions (2026-11-19)

Settled:
- The rights holder stays the Centre; the MCP server stays on.
- Ajrakh: wordings 1 to 6 applied, the question removed from the page, design fixes 6, 7, 8, 11, 12
  and 13 applied; wordings 8, 9, 11 to 14 left as they are; wording 7 waits for a source
  (`docs/design/ajrakh-critique-2026-11-19.md`, Applied).
- The review switch defaults to `AUTO` for research and `APPROVAL` for contributors and agents.
- Consent cannot be revoked: an approved contribution stays published.
- When erased testimony leaves a concept with nothing else, the concept goes (to build with the
  review queue).
- The contribution terms, the image declaration and the MCP terms of use, version 2026-11-19, are
  approved (`docs/legal/`). The MCP terms are served from `backend/app/data/mcp_terms_of_use.md`,
  held equal to the approved text by a test; a new version changes both and
  `research/oauth_rules.MCP_TERMS_VERSION`.
- The nightly build's Vercel deploy hook (`nightly-pages`, branch `main`) is created and stored as
  SecureString at `/kalavigyan/env/VERCEL_DEPLOY_HOOK_URL`; the next deploy renders it into the
  box `.env`.

Open:
- Artisan testimony can still be withdrawn as built (decision 0083); say whether irrevocable
  consent applies to it too.

## The two big tracks

1. **The data architecture**: `docs/decisions/0101-knowledge-architecture-for-every-craft.md`.
   - **Done:** step 1 (schema, decision 0102), the MCP read slice (decision 0103), the Ajrakh page
     as structured content and loaded into the database (decision 0105).
   - **Round 1, integrated on `track1`:** step 3 (retrieval by field, components by label), step
     4's gates, review switch and nightly upkeep, MCP slices 2 (OAuth, terms, connected apps) and
     3 (open work, `propose_fact`, `propose_component`, prompts, the contributor skill), nightly
     static builds, the bulk export (`docs/PROGRESS.md`).
   - **Round 2, integrated on `track1`:** the unified review queue, MCP `ask` and
     `start_image_upload`, approved pictures on craft pages, contribution screens, the dossier
     export and the curation skill on the write path (`docs/PROGRESS.md`).
   - **Round 3 (decision 0106):** the split, the document API, `PageLayout`, generated documents,
     all 42 component kinds as specs with React views, the React renderer. The parity proof passed
     on 2026-11-20 and `/crafts/Kutch-Ajrakh` draws its document.
   - **Rounds 4 and 5 (2026-11-20, released):** retrieval and MCP finished, every craft as its
     English document (decision 0107), field coverage everywhere (`docs/contracts/coverage.md`).
     Curated crafts keep the tabbed page as a bridge until their documents carry their structure.
   - **Round 6 (2026-11-20, released):** every curated craft drawn as its document (the tabbed
     page retired), the structure write path (`propose_structure`, decision 0108), signed-out pages
     refreshed when content changes, 70 of Kutch Ajrakh's 79 components as native views under
     parity.
   - **Round 7 (2026-11-20):** MCP is where knowledge is created. Contributors work in parallel
     through a queued, batched, idempotent proposal flow with trust tiers, stewardship and a cost
     ledger; deliver facts, structure, components (42 kinds and five general kinds) and whole
     pages, previewed before submitting; give pictures in every format straight from the chat,
     screened before review; and follow one body of method served over MCP (the page checklist,
     source rubric, quotes, fields, component and dataset guides). Knowledge heals itself and
     expert seats research their thin fields live. The landing leads everyone into reading, the
     map is drawn from Natural Earth on the Survey of India outline with relief, rivers and
     minerals layers, curated documents read as the board, and the release gate checks every
     deploy (post-deploy pages and MCP, a real OAuth MCP client, accessibility and performance).
   - **Round 7 quality (running):** citation accessibility, mobile speed (Kutch Ajrakh LCP), a
     build that cannot time out on one slow page, answer maps matching /map.
   - **Content:** arrives through MCP over time; the paid completeness run stays off.
2. **The redesign of the whole app**:
   - the `kalavigyan-design` skill and the boards in `docs/design/`;
   - waves 1B, 3 and 4 released in rounds 4 and 5 (landing, shell, atlas, category hub, map,
     answer page, every signed-in screen); wave 5 (proof) runs in round 6: every screen matched to
     its board with **Capture screens** on previews (round 6 matched the landing, atlas, hub, map,
     sign-in, phone appbar and the craft without a monograph); the production E2E suite and the
     design guard brought to the redesign.
   - The craft page is shared with track 1, step 2.
   - Match boards with screenshots, not by reading code.
   - The landing's "426 crafts" counts the master list's named crafts plus six from the portals,
     without the 35 "Other …" rows. Give it context when the landing is redesigned.

Later: comics on Nano Banana Pro (`gemini-3-pro-image`), and Expert auto-media (pictures, video,
film). Bringing the other crafts and 9 categories to the Ajrakh level is track 1, step 6, using
`.claude/skills/kalavigyan-craft-pages` (run `scripts/gaps.py` first).

## How to work (owner rules learnt the hard way)

- **Cost.** Agents stay short: one bounded task, about 60 to 100 tool calls, a checkpoint, then
  stop. Use Sonnet or low effort for mechanical work. At most five agents per round, on files that do not
  conflict (owner, 2026-11-20), each in its own worktree. Never message a running agent. Ask before any heavy spend, with an estimate.
- **Ship approved work as built.** Do not plan rebuilds of approved pages.
- **Commits.** Author and committer are `ankits1802 <ankits1802@gmail.com>`. Never a
  Co-Authored-By line. Use `GH_TOKEN=$(gh auth token --user ankits1802)` for each gh command.
- **No code comments** anywhere; `tools/hygiene_check.py` enforces it.
- **This machine is for development only** (owner, 2026-11-20): no tests, type-checks, builds,
  dev servers or browsers run locally, only formatters and linters on changed files. Push the
  branch to `deploy` and open a (draft) PR; Backend checks, Frontend checks and Hygiene run on
  any PR. Visual checks go through the **Monograph parity** workflow or a Vercel preview.
- **Release backend before frontend** is automatic: a push to `main` that changes the API runs
  Deploy backend, whose last step starts the web build through the Vercel deploy hook; a push
  that changes only the web app runs **Deploy web app** at once (`docs/RUNBOOK.md`).
- **Portals release together.** Fix everything, then release once.
  - Both portals' terraform state is in the `default` workspace.
  - `REPO_FACTS.md` must be regenerated on a clean tree after the last change.
- **Git Bash rewrites `/kalavigyan/...` paths** in `aws ssm` calls; set `MSYS_NO_PATHCONV=1`.
- Debt is in `docs/TECH_DEBT.md`; progress is in `docs/PROGRESS.md`.

## How this document is kept true

| Part | Kept true by |
|---|---|
| Live now and release status | the lead, at each release, from the deployed commit (`/api/version`) and the Vercel deployment's state |
| Owner decisions | the owner's words, dated; settled ones also land in a decision record |
| The two big tracks | [PROGRESS.md](PROGRESS.md), which records each round as it is integrated |

Re-read it at the start of every session and after every release.
