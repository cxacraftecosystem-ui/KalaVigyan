# 0092. The KalaVigyan design system: Alum & Indigo

KalaVigyan's design system is Alum & Indigo, version 1.1: one source of truth, rules that bind every
screen, its own type and motion, and a migration by job rather than by name. The `kalavigyan-design`
skill carries it, every build task meets its acceptance, and the generator, the boards and the mask
live in the repository.

Date: 2026-11-18. Status: accepted. Supersedes the frontend system of plan section 14.1 and the
colour, type and motion choices of decisions 0019, 0021 and 0048; their behaviour stands.

| For | Read |
|---|---|
| What amended it | [0114 Component kinds any craft can use, and one dataset record](0114-kinds-and-datasets.md): the design tokens, now that a depicted material is a record |
| What it supersedes in part | [0019 Craft page process timeline, region panel and map choropleths](0019-craft-page-and-region-panel.md): its colour, type and motion choices; its behaviour stands |
| What it supersedes in part | [0021 Media UI: Image and Video on the craft page's process stages](0021-media-ui.md): its colour, type and motion choices; its behaviour stands |
| What it supersedes in part | [0048 Place renderers: region story, map layer, seasons and supply](0048-place-renderers.md): its colour, type and motion choices; its behaviour stands |
| What it supersedes in part | the frontend system of [PLAN.md](../PLAN.md), section 14.1 |
| What built on it | [0094 The design primitives: one citation cluster, one motion owner, the editorial folder](0094-design-primitives.md): its components, SYSTEM.md section 3 |
| Every decision, by group | [README.md](README.md) |

## Context

The web client was scaffolded in the Design Prototype Workshop portal's look: the
`field-repo-frontend`, `gsap` and `motion` skills copied from the designer portal, purple as the
action colour with the field, gold, ministry, archive, errand, steward, mango and evidence ramps,
Inter and Plus Jakarta Sans, glass and gradient surfaces, the island nav, spring and staggered
entrances, and one GSAP headline timeline. That look serves a field-data portal. KalaVigyan is a
reading product: every sentence is cited, pictures and maps carry meaning, data needs colours
that never read as controls, and craft names appear in thirteen scripts.

Three directions were drawn as boards. Direction A, Alum & Indigo, went through a creative and an
engineering critique as version 1.0; version 1.1 applies both and records where a critique was
not followed and why. On 18 November 2026 the owner approved version 1.1 and asked that "the
design system of the entire must change accordingly" and that the new system be written "as a
skills file too".

## Decision

1. **The system is Alum & Indigo, version 1.1**: alum-white paper, kut iron-black ink, one
   interactive indigo. Grafted from the Specimen Cabinet direction: the specimen label on every
   craft, the collection wall where every craft has a plate, figure numbering and Cite this
   monograph. From Night Vat: the full-bleed photographic first screen and the vat moment as the
   one orchestrated animation.
2. **One source of truth.** `tokens.json` holds every token in light, dark, high-contrast light
   and high-contrast dark with its contrast class; `tokens.css` and `tailwind.config.ts` are
   written by the same generator, which refuses a token set that breaks a check (contrast by
   class, a 10 delta E floor between data colours and the reserved colours, ramp first steps
   against land and water, texture visibility, specimen frames). Values change in the generator,
   never in its outputs or in a component.
3. **The rules that bind every screen**: indigo is the only interactive colour; madder is
   emphasis, Sources differ and real hazards; terracotta is place; turmeric only highlights;
   data ramps, series and family hues never borrow those colours; the Rann is drawn as stippled
   salt flat; citations are one superscript cluster per sentence opening the verbatim quote, with
   margin notes from 1200px and a bottom sheet on a phone; one control per job; every button row
   is an ActionGroup; concise copy and no gap admissions; motion only to explain, with every end
   state as the default style under either reduced-motion switch; native-script names only where
   a reviewed source states them for this craft; pictures as plates, credited, at the standard
   Commons widths; every page complete at rest.
4. **Type**: Newsreader for headlines and reading, IBM Plex Sans for the interface, IBM Plex Mono
   for codes, a Noto face per Indian and Arabic script selected by `data-script`, all self-hosted.
   Plus Jakarta Sans and Inter leave the client.
5. **Motion**: framer-motion owns declarative motion and CSS keyframes come from the motion
   tokens. GSAP leaves the codebase; its last use, `components/guide/useGsapHeadline.ts`, goes
   with the landing rebuild. Spring overshoot remains only on a switch thumb.
6. **Migration by job, not by name.** The generated config aliases today's neutral, type, radius
   and status keys to the new tokens so nothing silently stops compiling. Amended on 18 November
   2026, after the first build: the retired ramps are aliased too, in
   `frontend/tailwind.migration.ts`, against SYSTEM.md section 6, because about 700 retired-class
   uses sit in files other lanes were editing, and an unaliased `bg-purple-700` compiles to
   nothing, which would have left primary buttons without a fill. The aliases guess by lightness
   (purple text and mid fills to indigo, light washes to sunk, `bg-purple-200` to the turmeric
   highlighter, `text-white` to on-indigo, map fills to the map and ramp tokens with a dark order
   of their own), so a file is still migrated by job when it is touched; the skill's section 11
   lists where the guess is wrong. The guard spec (`frontend/e2e/design-guard-unit.spec.ts`), per
   file against a ratcheted baseline, blocks any rise in retired and stock palette classes, hex
   and colour literals outside the token files and a brand allow-list, uses of every alias,
   physical left and right utilities and properties, media queries off the breakpoint list, and
   `var()` arbitrary values outside the chart, map, cloth and crafts folders. Each alias is
   deleted when its count reaches zero, then `tailwind.migration.ts` goes. Agents migrate the
   files their task owns; shared changes reach other lanes through tokens and the shared
   primitives.
7. **The skill.** `.claude/skills/kalavigyan-design/SKILL.md` is loaded before any frontend or
   design work. Its `references/` holds the full specification (`SYSTEM.md`), `tokens.json`,
   `tokens.css` and the generated `tailwind.config.ts`. The `field-repo-frontend` and `gsap`
   skills are deleted; `motion` becomes a pointer to the skill's Motion section. The project
   bindings, `docs/ARCHITECTURE.md` and plan section 14 now name the new skill.
8. **Acceptance for every build task**: board-versus-implementation screenshots at 360, 390, 834,
   1194, 1440 and 1920 in light and dark, with high contrast and Larger text at 360 (SYSTEM.md
   section 8). No sideways scroll, nothing below 12px except citation numerals, reduced-motion
   end states, the picture rules, the design guard and the generator's `--check` passing, and
   every unit spec that passed still passing (a spec that pinned the old look is updated to the
   system).
9. **The generator, the boards and the mask live in the repository.** The approved generator was
   moved to `tools/design/` and split to the repository's budgets; its inputs are
   `tools/design/system.json` and its outputs were checked byte for byte against the approved
   ones before any change. `python tools/design_tokens.py` writes the skill's references and
   `frontend/app/tokens.css`, `--check` (run by `tools/tests/test_design_tokens.py`) fails on a
   hand edit. Three changes followed in the generator, not in its outputs: the font stacks name
   the `next/font` fallback faces and the Noto Sans script faces; the photo-button, scrim and
   plate-edge colours became static tokens; and `prefers-contrast: more` with the app on Dark
   now applies high-contrast dark (it applied high-contrast light under a dark colour scheme).
   The boards and their pictures are in `docs/design/`, with the authored landing mask at
   `docs/design/img/hero-dyed-mask.png`. The 80 MB of approval screenshots stay out; they are
   re-captured from the boards.

## Consequences

- Every screen changes. Until a file is migrated, the aliases keep it compiling in the new
  tokens, so a half-migrated page reads in the new palette rather than breaking.
- The boards, the generator and the authored landing mask are in the repository (point 9); the
  skill names their paths.
- What version 1.1 did not take from the critiques, and why (a floor of 10 rather than 15,
  margin notes that are not buttons, categorical family hues, the documented specimen
  exception, no right rail on a tablet, English kept visible on the names view, Western digits in
  Urdu answers, and the rest), is section 9 of `references/SYSTEM.md`. Reopening one of those
  needs the owner.

## How this record is kept true

Item 6's amendment of 18 November 2026 records what followed the first build. Beyond that it is not
edited except to mark it superseded: a later choice is a new record that names this one, and the
table above links the two both ways. The parts later records changed stay here as they were decided;
the later record is the one that holds. It records the choice as taken on 2026-11-18; what the code
does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
