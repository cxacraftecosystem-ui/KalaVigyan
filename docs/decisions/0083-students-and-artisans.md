# 0083. Students and artisans: profiles at first entry, the Artisan role, conversations and testimony

Students give an age band and gender at first entry, the age band becoming a reading style for
composition and the lede, and a student under 18 needs a guardian's consent confirmed by the
admitting institution. A new Artisan role (rank 18) talks with an interviewer agent, and its
testimony becomes a claim only after a person reviews it, a deliberate exception to "no review
gates".

Date: 2026-11-18. Status: accepted; the items under "Owner to confirm" wait for the owner.

| For | Read |
|---|---|
| The contracts it names | [roles-and-contributions.md](../contracts/roles-and-contributions.md), [voice.md](../contracts/voice.md), [craft-page.md](../contracts/craft-page.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner's direction of 2026-11-18 asks for two things.

- **(A) Students.** Students give their age band and gender when they first enter, so that the
  storytelling fits them.
- **(B) Artisans.** A new Artisan role asks questions as students do and also talks with the AI by
  voice, so that artisans can add what they know.
  - Their words are credited as the artisan chooses.
  - Professors and admins review them before anyone else sees them.
  - They are never shown as a verified fact unless corroborated.
  - The artisan can withdraw them.

The owner's addition: an artisan practises one or more crafts, chosen from the catalogue, and each
conversation and what comes of it belongs to one of them.

What exists today:

- **Roles.** Five roles whose capabilities follow rank (`core/roles.py`).
- **Admission.** A person admits every account through the access roster.
- **Age.** Email sign-up asks "I am 18 or older".
- **Voice.** The live call is built and switched off (decision 0035).
- **Field voices.** The portals' field quotes come through version 2 of the field voices contract
  (decision 0084), which shares the `artisan_voice` block and the craft page's Voices part with this
  testimony.
- **Claim readers.** Every shared claim reader takes only claims of sensitivity `OPEN`.
- **Review gates.** The plan's domain rules say there are none.

The contract is `docs/contracts/roles-and-contributions.md`.

## Decision

1. **Artisan ranks 18, between Student (15) and Researcher (30).** Rank measures power on the
   platform, not standing in the craft.
   - **Above Student.** The lowest role stays Student, so anonymous public reading, the sign-up
     default and the budget fallback are unchanged, and artisans hold every student capability by
     the ladder.
   - **Below Researcher.** Artisans cannot propose claims, read all evidence or make videos: they add
     knowledge only as reviewed testimony.
   - **Managed by staff.** Professors and admins admit and manage them under the existing rank rules.
   - **18, not 20.** The designer portal's ladder already uses 20 for its Field Contributor, and the
     portals are to merge, so 18 is a number free in both. The roles lane's first cut in the tree uses
     20 and moves to 18 in `core/roles.py`, `shared/roles.json` and `lib/permissions.ts`.
2. **One role-only capability, `CONTRIBUTE_TESTIMONY`.**
   - A rank capability is inherited upward, so a researcher's or professor's words could then be
     credited as an artisan's.
   - `ROLE_ONLY_CAPABILITIES`, read by `can()` before the rank rule, gives it to artisans alone, and
     the Master Admin does not hold it.
   - Review is the rank capability `REVIEW_TESTIMONY`, from Professor up, and all its holders use
     two-step verification.
3. **Nobody makes themselves an artisan.** The role is requested at sign-up or in an access request,
   and granted by the person who admits the account or changes its role.
4. **Profiles live in tables of their own**: `StudentProfile`, `ArtisanProfile`, and `ArtisanCraft`
   for one or more crafts.
   - The user serialiser that lists accounts to staff cannot reach them.
   - The age band, gender and derived style appear in no response about another account, and in no
     audit detail, log, trace or fixture.
   - Leaving a role deletes its profile, except while an artisan's words are still shown or waiting.
   - A conversation names one of the artisan's crafts, asked at the start when there are several, and
     every contribution keeps that craft. A conversation that ranges over two crafts is two
     conversations.
5. **The age band becomes a reading style**, a fixed paragraph appended to the system prompt of the
   section, compose, regenerate and lede calls.
   - Under 14, 14 to 17 and 18 to 22 each have one.
   - 23 and over, and every other role, keep today's prompts byte for byte.
   - It goes in the system prompt, not the user message, because the message holds untrusted data
     while the paragraph is an instruction chosen from a table by an enum.
   - Candidates, schemas and post-checks are the same for every style, and the paragraph tells the
     model to keep every fact, figure and citation. So the style changes the register; which facts
     the model picks among those offered varies as it does for every reader.
   - Sentence lengths are not checked mechanically, because dropping a cited sentence for its length
     would lose a fact to a style rule.
   - A Student who has not given a band is refused by the answer route rather than given a guessed
     style.
6. **Only composition and the lede carry the style in this version**, as the owner asked. Expert
   takes, term summaries, generated explainers, region stories and the other model-written texts stay
   standard. Each can take the same paragraph later through `composer/prompt.styled`.
7. **Stored pieces are kept per style for the kinds a composer writes** (`prose`, `process_ladder`).
   Otherwise a young reader would be served an adult section from earlier research, and an adult a
   young reader's. Every other kind is shared by all styles, so maps, reactions and molecules keep
   their reuse, and written-back claims serve every style.
8. **Gender has one reader**, `character_figure`, for the illustrated stories designed separately.
   It never reaches a model, a ranking or a builder.
9. **Students under 18 need a guardian's consent, which the admitting institution confirms.**
   - The Digital Personal Data Protection Act, 2023 (section 9) requires a parent's or guardian's
     verifiable consent before a child's personal data is processed, and forbids tracking or
     behavioural monitoring of children. The owner's bands include under 14 and 14 to 17, while
     sign-up asks for 18 or older.
   - Students reach KalaVigyan through their school or college, which admits them, so a professor or
     admin confirms that the institution holds that consent.
   - The confirmation is asked for every student, adult or not, so it reveals nobody's age, and Manage
     users lists each student without it.
   - A student who gives an under-18 band without it is held, on the server too, until it is
     confirmed. This guard fails closed.
   - Using the band as a reading level is a declared preference, not monitoring, and nothing is
     profiled from behaviour.
10. **Artisans are adults.** Testimony is shown under the artisan's credit, and a minor's would need a
    guardian's consent as well. The field voices feed sends no one under 18 either. The artisan's
    first entry asks "I am 18 or older".
11. **Conversations have their own switch, routes and agent.**
    - `ARTISAN_CONVERSATION_ENABLED` (default off) guards the conversation routes under
      `/api/artisan`. `VOICE_CALL_ENABLED` stays off and still guards all of `/api/voice`: putting
      conversations under `/api/voice` would have meant opening that router's guard for one role.
    - The voice backend's session row (`purpose` `ARTISAN`), binding, relay upload, seconds ledger,
      speech to text, speech and transcript cipher are reused.
    - The artisan agent is a second ElevenLabs agent with its own nonce context, so neither
      custom-LLM endpoint accepts the other's sessions.
    - Relay is the default, as for voice.
12. **The interviewer listens.**
    - Each turn is one short open question in the artisan's language, following what they said
      through process, materials, timing, tools, history and change. The gaps KalaVigyan already holds
      for the craft inform it, by name only, so it never leads.
    - It never states, corrects or teaches, and never asks for personal details.
    - A failed, refused or slow call falls back to a fixed guide question, so a conversation never
      stalls.
    - When the artisan asks something, the voice turn's `VERIFIED` path answers from stored claims
      word for word, cited, with no model call. That is "they can talk to the AI" without a second
      answering pipeline.
    - An artisan may then repeat what they heard, so the reviewer sees the turn before every quote and
      extraction is told never to draw a fact only repeated from KalaVigyan's answer.
13. **Two AI tasks of their own, `INTERVIEW` and `TESTIMONY`.** `EXTRACT` is a public-text task that a
    provider limited to public text may serve, and a conversation is personal data. Separate tasks
    also let the master admin route a fast model to the turns and a careful one to the extraction.
14. **Recordings are kept privately and never shown.**
    - They are the evidence a reviewer listens to, and they go with the conversation.
    - Relay keeps the artisan's own uploads only. A turn that lost anything to scrubbing keeps no
      recording, since spoken digits cannot be cut out of audio.
    - The agent path keeps text only until fetching a recorded conversation's audio is shown to work.
15. **Testimony becomes a claim only at approval, with sensitivity `ATTRIBUTE_REQUIRED`.**
    - Every shared claim reader already refuses anything but `OPEN`, so no composer, page fact,
      summary, quiz, piece or count can use testimony as a fact. This uses a guard that already exists
      rather than a new filter in a dozen readers, and only the testimony store reads these claims.
    - No chunk is written, so no passage of testimony reaches a composer.
    - The claim's level stays provisional for good. Corroboration links ordinary claims for display,
      and the fact reaches answers only through those.
    - Pending items are rows of their own, so nothing unreviewed exists as a claim.
16. **Testimony is reviewed before it is shown: a deliberate exception to "no review gates".**
    - That rule is about sourced facts reaching readers fast. Testimony is a person's own words, shown
      under their name or description, so a human reads it first, as the owner directed.
    - The reviewer looks for personal details, other people's names, and quotes that do not say what
      the claim says.
    - Reviewers may edit the claim and the English, but only trim the quote, which stays the artisan's
      exact words.
    - The bindings' domain rule records this exception when the lanes build it.
17. **One "In the artisan's words" surface, shared with field voices.**
    - The portals' quotes and KalaVigyan testimony share the craft page's Voices part and
      `artisan_voice` version 2, told apart by `origin` (`KALAVIGYAN` here), each quote keyed by
      `itemId`.
    - The speaker line for an artisan who chose not to be named is the field voices contract's own:
      "An artisan of <craft>, <district>, <state>".
    - In answers, the block is built from approved testimony by fixed rules with no model and is never
      stored as a piece, so a withdrawal reaches the next answer at once. Stored explainers drop
      withdrawn quotes when served, and show the current credit.
18. **Withdrawal erases.**
    - A withdrawn item keeps only a tombstone row; its claim versions, citation and text are deleted at
      once.
    - The source, transcript and recordings go when the conversation has nothing left waiting or
      shown.
    - Rejected items keep their text 30 days, then lose it.
    - Reading and withdrawing one's own contributions work whatever the switch or the account's
      current role.
19. **One migration**, `0028_roles_and_contributions`, after `0027_field_voices`.
    - It adds the enum values, six tables and three columns. It adds no quota rows and no spend
      cap: the owner's direction of 2026-11-18 is no caps for now on anyone, in money or tokens.
    - Its downgrade turns artisans into students, as `0009_admin_role` turned admins into
      professors.
    - The lead re-chains it beside the field voices migration.

## Owner to confirm

1. **Item 9, guardian consent.** The institution's confirmation as the route, asked for every
   student, and holding an under-18 student until it is given. The alternative, a parent's own
   consent through a verified channel, needs a verification flow and a guardian's contact details,
   which this design avoids. The rules made under the Act may also exempt an educational institution's
   own processing for its students; that is a legal reading for the owner.
2. **Item 10.** Artisans must be 18 or older.
3. **Allowances.** Settled by the owner on 2026-11-18: no caps for now on anyone. When caps return,
   the artisan's would be set in Settings like any role's.
4. **Recordings stay private.** Showing short audio clips with approved quotes would need its own
   consent wording.
5. **Artisans read in the standard style.** They could be offered a plainer one by choice.
6. **Item 12.** Answering the artisan's questions from stored claims during a conversation.

## Unverified

1. That ElevenLabs serves a recorded conversation's audio (`GET /v1/convai/conversations/{id}/audio`
   with `record_voice` true), in which format, and how soon after the call. Until that is shown,
   agent conversations keep text only.
2. That conversation details carry each message's `time_in_call_secs`, which agent locators use.
   Until then, an agent turn is located at the time its request arrived.
3. That a language preset may override the agent's `first_message`. The voice contract's unverified
   items 1 to 8 apply to the artisan agent as to the voice agent; relay needs none of them.
4. The interview guide, the fixed phrases and the recording notice in twelve languages have not
   been read by native speakers.
5. Scribe's accuracy in each language (Urdu's band is moderate). Reviewers check quotes against the
   recording.
6. How closely the models keep each style's sentence lengths; the first production answers will
   show it.

## Consequences

- **Lanes.**
  - roles, profiles and first entry, on the backend and the web;
  - the reading style, a small edit to `composer/prompt.py` and the piece store beside the
    answer-richness lane's work;
  - artisan conversations, in voice;
  - the testimony store, extraction and the review queue;
  - the display, built with the field voices lane, on the craft page and in answers.
- **Living documents.** When built, these are updated in the same change:
  - `docs/ARCHITECTURE.md`;
  - `docs/CORE_API.md` (`reader_profiles`, `reading_style`, `testimony_store`);
  - the project bindings (the role list and the domain-rule exception);
  - `docs/contracts/voice.md` (the session purpose);
  - `docs/contracts/craft-page.md`, with the field voices lane.
- **Debt to record when built.**
  - styles for the other model-written texts;
  - the expert panel's artisan seat reading testimony;
  - quotes translated into the reader's language;
  - an in-app note to the artisan when an item is decided;
  - an E2E artisan account for the production run;
  - native review of the phrase tables.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. When the owner settles the items under
Owner to confirm, a later record says so and is linked above. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
