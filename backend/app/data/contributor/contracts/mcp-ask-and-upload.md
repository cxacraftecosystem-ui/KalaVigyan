# MCP ask and the picture tools (decision 0101, items 15 and 17; decision 0109)

Four signed-in MCP tools. `ask` runs our answer pipeline for the signed-in person and returns the
finished answer as structured data, with a design kit and an MCP App view to draw it.
`start_image_upload` hands out a single-use link to our site (and, for agents with a shell, a
presigned upload slot), so a picture travels outside the chat. `give_image` and `give_images` take
a picture that is already in the chat, by link or as base64, with the declaration the person
confirmed there.

## Code

| Part | Where |
|---|---|
| The ask result contract, the answer link, the view's URI and MIME type | `research/mcp_ask.py` |
| Running the pipeline to the end and collecting its outcome | `services/answer_runs.py` |
| The web route's guards, the pipeline per call, the timeout | `api/mcp_ask_run.py` |
| The tool `ask` (`ASK_TOOLS`, which also lists `start_image_upload`) | `api/mcp_ask_tools.py`, registered in `api/mcp_tools.py` |
| The tools `start_image_upload`, `give_image`, `give_images` (`PICTURE_TOOLS`) and their texts | `api/mcp_picture_tools.py`, `api/mcp_picture_texts.py`, registered in `api/mcp_tools.py` |
| Giving pictures from the chat: per picture checks, screens, one declaration | `services/upload_links_give.py`, contracts in `research/image_contributions_give.py` |
| Fetching a picture's link | the fetcher's `POST /fetch-picture` (`fetcher/pictures.py`), its client `services/upload_links_fetch.py`, contract `research/image_intake_fetch.py` |
| The vision screen's call | `api/picture_vision.py` |
| The answer kit and the answer view resources | `api/mcp_resources.py`, `data/answer_kit.py`, `data/design/answer-kit.md`, `data/design/answer-view.html` |
| The page preview view (decision 0110) | `data/page_preview_view.py`, `data/design/page-preview-view.html`, named by `preview_page` and `preview_draft` |
| A supplied source's file slot (decision 0110) | `services/supplied_sources.py`, `api/routes/supplied_sources.py` (`knowledge-writes.md`, Supplied sources) |
| Upload link contract, states, addresses | `research/upload_links.py` |
| Issuing, reading, renewing and filling a link or slot | `services/upload_links.py` |
| HTTP routes | `api/routes/upload_links.py` |
| Table | `models/upload_links.py` (`UploadLink`), migration `0040_upload_links` (after `0039_upkeep`); `materialId`, `slot`, `taskKey` from `0050_image_screens` |
| The landing page | `frontend/app/(protected)/contributions/pictures/upload/page.tsx`, `components/contributions/LinkedSlot.tsx`, `LinkedPictureForm.tsx`, `PicturePreview.tsx`, `HeldReasons.tsx`, `ClosedUploadLink.tsx`, `lib/uploadLinkContract.ts` |

## `ask` (scope `ask`, signed in, a write)

Arguments: `question` (2 to the question limit), optional `craft_slug` (from `find_crafts`) or
`any_craft: true` (not both), optional `depth` (the person's default when absent) and `language`.

It runs for the signed-in person exactly as `POST /api/answers/stream` does, in this order, and
refuses with the site's own words before anything is spent:

1. a password change owed, two-step setup owed, a guardian's consent owed;
2. `ASK_STANDARD` and a depth the person may choose (`selectable_depths`);
3. a Student without a reader profile ("Finish setting up your profile first."), and a Student's
   reading style passed on;
4. the ask throttle, 30 asks in 10 minutes per person (`ask_attempt`, the web route's window),
   except an uncapped account; the refusal names the seconds to wait.

The database connection is released before the run. The pipeline is built per call with the
person's `Principal` and `AnswerSpend` for the depth (and its headroom for optional work), so the AI
budget, the routing and the usage records are the site's. A spent budget answers from stored facts
and keeps no answer; the tool then refuses and says so. Research that finds nothing returns the
pipeline's own message (what was searched). The person's name is withheld from searches as on the
site.

**Timeout.** The run is bounded at 600 seconds (`ASK_TIMEOUT_SECONDS`); past it the tool refuses
("The answer was not finished within 10 minutes") and returns nothing. The tool's description tells
agents to allow up to ten minutes. A client that accepts an event stream gets the call as one
(`knowledge-api.md`): progress notifications for its `progressToken`, or comment heartbeats, at least
every 15 seconds while the answer is written, then the result, so the edge in front of the API
(CloudFront's 120-second and nginx's 300-second idle timeouts) never sees an idle origin. A client
that takes only JSON gets one body when the answer is done; the edge may end such a call first, and
the answer still finishes and is kept with the person's answers on the site. A streamed call that
loses its client also runs to the end and is kept.

### `AskedAnswer`

`{schemaVersion: 1, answerId, version, question, crafts[{slug, name, pageUrl}], depth, language,
opening[], sections[{id, field, title, sentences[], components[]}], fields[], sources[], followUps[],
answerUrl, view{resourceUri, mimeType}, attribution, dataNote}`

- A sentence: `{text, level, claimIds[], sourceIds[], cites[]}`: the facts and sources it rests on
  and its citation numbers, sorted and de-duplicated, numbered in the order of `sources`.
- `opening` is the lede's sentences; sections are the ready ones, in order.
- `fields` is the answer's provenance by field: each field a ready section consulted, in vocabulary
  order, `{field, sections, sentences, sources, figures, seats[]}` (`answer-eval.md`).
- A placed component: `{label, title, kind, url}`, the registered component by label and its link
  on the site.
- A source: `{number, id, kind, title, authors, year, doi, url, publisher, licence, attribution,
  reliability}`.
- `answerUrl` is `<site>/ask?explainer=<id>&version=<n>`, the same answer on the site.
- `attribution` and `dataNote` are the read tools' (`knowledge-api.md`).

In `tools/list`, `ask` carries `_meta.ui.resourceUri` (and the older `_meta["ui/resourceUri"]`)
naming `ui://kalavigyan/answer.html`, with visibility `model` and `app`.

## Resources

| URI | MIME | What |
|---|---|---|
| `kalavigyan://design/answer-kit.md` | `text/markdown` | How an answer is drawn: the order, sentences and citation clusters, component cards, sources, the rules, and a table of the light and dark values of the colours an answer uses and the font stacks, generated from `tokens.json` |
| `ui://kalavigyan/answer.html` | `text/html;profile=mcp-app` | The MCP App that draws an `ask` result in our design |
| `ui://kalavigyan/page-preview.html` | `text/html;profile=mcp-app` | The MCP App that draws a `preview_page` or `preview_draft` result: the private link, the checklist report and each part's outcome (`open-work.md`) |

The view is one self-contained page: no network (`_meta.ui.csp` lists no domains; its own
Content-Security-Policy is `default-src 'none'` with the one inline script allowed by its SHA-256),
the four themes' colours inlined from `tokens.json`. It speaks the MCP Apps protocol over
`postMessage`: `ui/initialize`, then it draws the `structuredContent` of
`ui/notifications/tool-result`, follows the host theme, reports its size, and opens links through
`ui/open-link`. Every text is set with `textContent`, never as markup; only `https` links are
made. The page preview view is built the same way and also inlines the status colours (`success`,
`error`, `info` and their washes) for the verdicts, each always drawn with an icon and words.

## `start_image_upload` (scope `contribute`, signed in, a write)

Arguments: `craft_slug`, at most one of `stage_id` (one of the craft's stages), `material_id`
(one of its materials) and `slot` (`MASTHEAD`, `RECORD`), an optional `task_key` (a
`MISSING_PICTURE` task of the craft, whose target is used when none is given), `claim_ids` (1 to
20, each a fact a signed-out reader is shown, each once), and an optional `declaration`
`{origin, generator, prompt, caption, altText, rightsConfirmed: true, termsVersion: "2026-11-19"}`
(the rules of `ImageDeclaration` in `image-contributions.md`; the agent passes it only after the
person confirmed it).

`UploadStart`: `{schemaVersion: 1, link, expiresAt, uploadUrl, uploadMethod: "PUT", uploadTypes,
uploadMaxBytes, craft, stage, material, slot, taskKey, facts[{id, text}], declared, nextStep}`.
`uploadTypes` lists every accepted type: `image/png`, `image/jpeg`, `image/webp`, `image/avif`,
`image/gif`, `image/heic`, `image/heif`, `image/tiff`, `image/bmp`, `image/svg+xml`
(`image-contributions.md`, what the file goes through).

- `link` is `<site>/contributions/pictures/upload?link=<token>`, valid 30 minutes, tied to the
  person, the craft, the stage and the facts.
- `uploadUrl` is `<api>/api/upload-links/slots/<slot token>`, given only with a declaration and
  when the API origin is configured: PUT the picture's bytes to it.
- Link and slot are one slot: whichever is used first closes both.

Rules: Researcher and above (`PROPOSE_KNOWLEDGE`); at most 10 open links a person, and at most 20
picture uploads started an hour (`IMAGE_UPLOADS`, Admins exempt, `knowledge-writes.md`); the craft, stage
and facts are checked when the link is made and again when the picture is declared. Tokens are
`kvup_pg_` (page) and `kvup_sl_` (slot) followed by 32 random bytes; only their SHA-256 is stored.
A slot stops working when its account's sessions are ended (signing out everywhere, for one) or
the account is deleted, checked as an access token is (`token_matches_user` against the token
version and the moment of issue), or when the account loses the capability.

## `give_image` and `give_images` (scope `contribute`, signed in, open-world writes)

For a picture that is already in the chat, an AI tool's for one. The agent asks the person first,
in their words, for the declaration: that they took or made the picture or hold the right to share
it, that the Centre may publish it without their name (which cannot be revoked once approved), and
for an AI image the tool and model and the prompt. It never fills the declaration in for them.

- `give_image`: `craft_slug`, a target as for `start_image_upload` (`stage_id`, `material_id`,
  `slot`, `task_key`), `claim_ids` (0 to 20; an AI image names one), `declaration` (the slot
  declaration: origin, generator and prompt for an AI image, caption, altText, rightsConfirmed true,
  termsVersion), `confirmation` (the person's words, 2 to 500 characters), and exactly one of
  `image_url` (https) or `image_base64` (base64 or a `data:` URI, at most 6 MB decoded).
- `give_images`: `craft_slug`, `declaration` (the shared part: origin, generator, rightsConfirmed,
  termsVersion), `confirmation`, and `pictures[]`, one to ten, each with its own target, `claimIds`,
  `prompt`, `caption`, `altText` and `imageUrl` or `imageBase64` (12 MB of base64 at most in one
  call).

A link is fetched by the fetcher process, never by the API: `POST /fetch-picture` with `{url,
maxBytes}` checks the URL (https, port 443, no credentials), resolves it to public addresses only,
pins TLS to the named host, follows at most three redirects, streams at most 10 MB, and answers the
bytes with their type read from the bytes and `X-Final-Url`, or the fetcher's refusal (403) or
failure (502) body. A link that is refused, or gives no picture, refuses that picture only.

Each picture is checked and screened on its own, in order: the upload limit (`IMAGE_UPLOADS`, one
count a picture), its declaration, target and facts, then the screens of `image-contributions.md`
(the intake, an exact or perceptual repeat, within the call too, and the vision call). The pictures
that pass are filed together under one `PictureDeclaration` (channel `MCP`, with the person's words)
and stored as contributions, so they reach the review queue and the person's pictures like any
other.

`GivenPictures`: `{schemaVersion: 1, craft, declarationId, given, refused, pictures[{position,
contributionId, status, label, received, mime, width, height, screen{verdict, flags, reasons},
refused}], nextStep}`. A refused picture carries only its position and the reason.

## HTTP routes (`/api/upload-links`)

| Route | Who | Body | Answer |
|---|---|---|---|
| `GET /{token}` | the link's owner (`PROPOSE_KNOWLEDGE`) | none | `UploadLinkView {state, craft, stage, facts, expiresAt, contributionId}`, `Cache-Control: private, no-cache` |
| `POST /{token}/picture` | the owner | multipart: `declaration` (the slot declaration as JSON) and `picture` (the file) | 201 `ImageContributionView`; the link is used |
| `POST /{token}/renew` | the owner | none | 201 `RenewedLink {token, link, expiresAt}`: a new link for the same craft, stage and facts, only for a used or expired link |
| `PUT /slots/{slot token}` | anyone holding the slot token, no session (counted as an anonymous read) | the picture's bytes | `ImageContributionView`; the slot and its link are used |

`state` is `OPEN`, `USED` or `EXPIRED`; a used link stays used after it expires. Refusals: 404 for
a token that is not the caller's or does not exist, 409 for renewing an open link or a repeat
picture, 410 with the reason for a used or expired link or a slot whose account changed, 413 over
10 MB, 422 for a declaration or file that fails its checks, 503 without the media bucket. The
picture is screened before the link is locked (cleaning, AI mark, repeats, the vision call), then
goes through `image_contributions.declare` and `store_screened` (storage, approval at once for a
Professor and above when the screen clears it), so it lands in the review queue and in the
contributor's own pictures like any other. In the route inventory the three owner routes are
`ADMIN` class (refused to a Student) and the slot is `SERVICE`.

## `UploadLink`

`{id, userId, userTokenVersion, craftId, stageId, materialId, slot, taskKey, claimIds[], linkHash,
slotHash, declaration, expiresAt, usedAt, contributionId, createdAt, updatedAt}`. Checks: a slot hash exactly when a
declaration is stored; at least one fact; a contribution only on a used link. Unique link and slot
hashes, an index on `(userId, expiresAt)` and on `contributionId`. Row level security is on and
the public roles have no grants.

## The landing page

`/contributions/pictures/upload?link=<token>`, inside the signed-in shell, so a signed-out reader
(a phone too) signs in and comes back to the same address; the page needs Researcher access. It
shows the craft, the stage, material or picture slot and the facts already chosen, and the
existing picture declaration: what it is, the AI tool and model and the prompt for an AI picture,
the caption, the description, the file with a preview of it as it will be shown (caption first,
credit after; a file the browser cannot draw says it is made WebP on arrival) and the
declaration (version 2026-11-19). Once sent it says whether the picture is shown or waits, and
why the screen held it. A used or expired link says so and offers Get a
new link; a link of another account says so and points to the picture page without a link.
