# 0094. The design primitives: one citation cluster, one motion owner, the editorial folder

The primitives of Alum & Indigo are built before the page lanes move to them: one citation cluster
that owns its sources, one owner for motion, component classes in CSS and the editorial folder.
Commons pictures are plain `<img srcset sizes>`, and `/design` shows the system.

Date: 2026-11-18. Status: accepted. Builds on decision 0092 (Alum & Indigo).

| For | Read |
|---|---|
| What it builds on | [0092 The KalaVigyan design system: Alum & Indigo](0092-design-system.md): its components, SYSTEM.md section 3 |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0092 adopted the design system and its tokens. Its components (SYSTEM.md section 3) had
to be built before the page lanes could move to it, while other lanes were still editing the
answer, craft and contribution screens. The citation chip opened a modal source dialog per source;
the system asks for one cluster of numerals per sentence that opens every quote behind it, as a
popover, a margin note or a phone sheet. Motion lived in three places (framer variants, a GSAP
headline, the popover's own reduced-motion reader).

## Decision

1. **Where the primitives live.** Generic controls stay in `frontend/components/ui` (Button,
   IconButton, TextLink, Chip, SegmentedChoice, Toggle, Tabs, Sheet, Skeleton, Lightbox, Figure,
   the restyled Toast, SearchableSelect and AnchoredPopover). The reading primitives that know
   about citations, crafts and pictures live in a new `frontend/components/editorial` (Cite and
   its SourcePanel, EvidenceMark, MarginNotes and Spread, SpecimenLabel, NameStack, Masthead,
   Plate, TypographicPlate, FactGrid, ChapterRail), so every page lane composes the same pieces.
   The names follow SYSTEM.md section 3; the paths there (`craft/…`, `crafts/…`) are where page
   components will sit, not the primitives.
2. **The cluster owns its sources.** `answer/CitationChip.tsx` and `CitationChips` in
   `answer/CitationContext.tsx` render `editorial/CitationCluster` (`Cite`). The cluster
   de-duplicates by source through `lib/citations.citationsBySource`, sorts by number, and opens
   its own surface: a modal `Sheet` below 640px, the `AnchoredPopover` from 640px, docked beside
   the sentence in the margin from 1200px when the page has a `Spread` with a margin rail
   (`lib/citationCluster.citationSurface`). Clusters no longer call `CitationLookup.onOpen`.
3. **Its name and description.** The accessible name is "Sources 1 and 2" (or "Source 3"); the
   short titles are its description through `aria-describedby` on a hidden element, because
   `aria-description` is not yet supported by every screen reader nor known to the lint rules.
   `aria-controls` is set only while the surface exists. A word joiner glues the cluster to the
   word before it; the button's `data-testid` stays `citation-chip` so the production checks keep
   finding one per sentence, and `data-numbers` carries its label.
4. **One owner for motion.** `app/motion.css` holds the named keyframes (press, dip, oxidise, the
   panel entrances, the skeleton pulse), the vat's registered properties and phases, and the
   reduced-motion switch for both settings, moved from `globals.css`. `components/motion` holds
   the hooks: `useMotionAllowed` (false on the server and the first client render, then both
   switches), `useNamedMotion` and `useVatMoment`, which reads the duration tokens from the page
   and steps rest, in the vat, lifted and in the air (`lib/motion.vatSchedule`). The thread
   motion is not built: SYSTEM.md section 9 retires it. GSAP and `useGsapHeadline` are removed,
   so headlines are whole at first paint.
5. **Component classes in CSS.** Primitives that need pseudo-elements, state selectors or the
   control-size tokens Tailwind has no key for are `kv-*` classes in `app/primitives.css` and
   `app/editorial.css`, imported by `globals.css`. The legacy `field-button`, `field-input` and
   `field-link` rules share those selectors, so the old classes and the new components draw the
   same thing from one place.
6. **Commons pictures are plain `<img srcset sizes>`** at the standard widths through
   `lib/commonsPicture`, as SYSTEM.md 2.15 requires. The `@next/next/no-img-element` rule is off
   for `components/editorial`, `components/ui/Lightbox.tsx` and `app/design` in
   `eslint.config.mjs` for this reason.
7. **The mark.** `BrandMark` is the eight-pointed star in one colour; `BrandLockup` adds the
   wordmark as outlines in `components/brandOutlines.ts`, written by `tools/brand/wordmark.py`
   from the self-hosted Newsreader (600, opsz 24) and Noto Serif Devanagari (500, x1.08) with
   the master board's spacing, so an English page loads no Devanagari font. `app/icon.svg`,
   `app/favicon.ico` and `app/apple-icon.png` are the star.
8. **`/design`** renders every primitive in every state from the real components, public and
   `noindex`, and is a signed-out route so it never probes a session.

## Consequences

- Page lanes build monographs, the atlas, answers and the landing from these primitives and delete
  the components they replace (`craft/MediaFigure`, `craft/CraftTabs`, `answer/EvidenceBadge`,
  `answer/SourceDialog` for clusters); the leftovers are in `docs/TECH_DEBT.md`.
- Unit specs that counted one chip per source now read one cluster per sentence and its numbers.
- `e2e/primitivesPage.ts` loads the four CSS files into a page, so specs check the real styles
  (busy width, fills, the sheet's shape, the reduced-motion switch) without a build.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
