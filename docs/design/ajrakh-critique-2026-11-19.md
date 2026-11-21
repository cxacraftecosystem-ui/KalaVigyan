# Kutch Ajrakh monograph: critic re-score, 2026-11-19

Release step 6 of `docs/NEXT.md`. One critic scored the live page against `.claude/skills/kalavigyan-craft-pages/references/page-checklist.md`, for design and chemistry together. **Design 7/10, chemistry 7.5/10.**

**Applied the same day (no words changed):** design fixes 1 (no primary buttons on the reading page), 2 (the phone stacks the three opening buttons), 3 (opaque sticky bars), 4 (the chemistry sub-rail no longer sticks under the rail), 5 (selected states in indigo), 9 (Fig. 10's repeated title hidden) and 10 (the second "Watch it being made" hidden). They are one override block, `style#kv-release-fixes`, in `frontend/public/monographs/kutch-ajrakh/index.html`. With them the page is 46,870 px at 1440, under the length limit.

**Left for the owner:**
- Design fixes 6 (SVG label sizes), 7 (Fig. 1 rests at dip 1; resting at dip 4 changes its generated status line and button label), 8 (a picture crop), 11 (folding the progress block), 12 (numbering) and 13 (the GI card frame).
- Every wording change below, which needs the owner's OK.

| For | Read |
|---|---|
| The rules the critic scored against | [page-checklist.md](../../.claude/skills/kalavigyan-craft-pages/references/page-checklist.md) |
| The design system the fixes follow | [kalavigyan-design](../../.claude/skills/kalavigyan-design/SKILL.md) |
| The release this critique was a step of | [NEXT.md](../NEXT.md) |

The critic's report follows as written.

Read on 19 Nov 2026 at https://kalavigyan.vercel.app/crafts/Kutch-Ajrakh, at 360, 834 and 1440 px, light and dark, plus a reduced-motion run at 1440 for the rest state. Full-page captures go blank past Chromium's 16,384 px limit, so the page was captured in 8,000 px slices (`seg-*.png`, `sheet-*.png`). Measurements are in `metrics.json`, `probe.json` and `probe2.json`; the page text is in `innerText.txt`. All files are in this folder.

## Scores

**Design: 7 / 10**
- Passes: no sideways scroll at any width (rule 12 of the design acceptance). The masthead photograph is in the first viewport at every width (rule 2). Credits sit under their figures (14). Charts and the wells are drawn to scale from zero (17). Toasts are fixed to the viewport (11). The media chapter is a gallery keyed to the section titles (8). The coda comes before the tools (16). Dark mode is coherent.
- Fails:
  - Rule 1: the h1 is the question and the masthead has no native name, although the dossier holds Sindhi اجرڪ (claim C152). The Hindi and Urdu panels carry the raw question as h3.
  - Rule 3: the chapter 6 GI card repeats the name and the GI date.
  - Rule 4: the first screen shows two counts (44 and 20 sources), sections numbered 1 to 7 beside a rail numbered 1 to 12, and rail labels that differ from the chapter titles.
  - Rule 5: the 44 includes 8 family, 2 kin-monograph and 14 compound-library sources.
  - Rule 6: the vat is told again by Fig. 10 and by the specimen band's "Dip it again". There are three vat players.
  - Rule 7: two SMarndi close-ups of the same indigo star field.
  - Rule 10: Fig. 1 rests at "Dip 1 of 4", and "How this answer was made" shows a pipeline progress list at rest.
  - Rule 12: the sticky bars are translucent (96 to 97 per cent ground), and two are stacked in chapter 3.
  - Rule 16: the page is 47,228 px at 1440.
- Design-system breaches:
  - Three indigo primary buttons on a reading page.
  - A 2 + 1 button wrap on the phone.
  - Pressed and selected states in ink-1 instead of indigo.
  - SVG labels at 5.7 to 11.8 px, below the 12 px floor.
  - "Watch it being made" appears twice.

**Chemistry: 7.5 / 10**
- Passes:
  - Every equation balances for atoms and charge (rule 21): the leuco oxidation, indican hydrolysis (implied), 2 indoxyl + O₂, the hydros vat with its sodium salt (C 16, H 14, N 2, Na 6, O 10, S 2), and 4 Fe²⁺ + O₂ + 4 H⁺.
  - The dithionite electron count is right. The alizarin six-member Al chelate (1-OH and 9-C=O) is right. Purpurin's extra 4-OH is right. Tyrian purple as 6,6′-dibromoindigo is right. Indigo needing no mordant is right.
  - The source's unbalanced "indoxyl + air" is shown, not drawn (22). Six disagreements are recorded with both readings.
- Fails:
  - Rule 19: "oxidises with the tannic acid" hands the oxidant's role to tannin in 7 places, the short answer first. Only Fig. 8 corrects it, so rule 22's "same quote renders the same way" also fails.
  - Rule 19: leucoindigo is called "colourless" in the vat, and cloth then comes out green.
  - Rule 21: Fig. 4 says each oxygen carries a hydrogen in the vat, which contradicts the page's own sodium-salt equation.
  - Rule 18: woad is counted as a third vat dye, though it gives the same indigo.
  - Rules 18 and 19: harde is drawn as C₇₆H₅₂O₄₆ tannic acid, but myrobalan's tannins are ellagitannins.
  - Rule 19: "Indian madder holds high amounts of alizarin" is contested and not recorded as Sources differ.
  - Rule 20: depth is unequal. Blue has five figures. Black has no structure of the iron–tannin complex. White's "lime discharges alum" has no mechanism.
  - Rules 15 and 18: the kin panel joins Bagh's "alizarin" from al root (*Morinda*) to Ajrakh's alizarin.

## Design fixes that change no words

1. **Primary buttons on a reading page.**
   - Where: all widths, both themes.
   - Wrong: `button.btn.primary[data-listen-open]` (Listen · 2 min), `#quiz-next.btn.primary.sm` and `#gen-reset.btn.primary.sm` (Watch it being made) are indigo fills.
   - Fix: remove the class `primary` from all three, so they render as quiet `btn`.
2. **Phone button row.**
   - Where: 360, both themes.
   - Wrong: `.kv-open-act` wraps Listen and Save on one line and Cite this answer on the next.
   - Fix: add `@media (max-width: 639px){ .kv-open-act{flex-direction:column;align-items:stretch} .kv-open-act>.btn{width:100%} }`.
3. **Translucent sticky bars.**
   - Where: all widths. Most visible in dark: "state.18,19" shows through the rail at 1440, and prose shows through the menubar at 360 (`crop-sticky-*.png`).
   - Wrong: `.kv-rail`, `.kv-menubar` and `.subrail` use `color-mix(in srgb, var(--ground) 96%/97%, transparent)`.
   - Fix: set `background: var(--ground)` on all three. The file already has this rule as an override; make it the default.
4. **Two sticky bars stacked.**
   - Where: chapter 3, all widths.
   - Wrong: `nav.subrail` sticks at `top:46px` under the 47 px `.kv-rail` or `.kv-menubar`, so the two bars overlap by 1 px.
   - Fix: `.subrail{position:static}`. The rail's scroll-spy already marks Chemistry.
5. **Selected states in ink instead of indigo.**
   - Where: both themes; the Dark toggle shows in dark mode, the Cite tabs at every width.
   - Wrong: `.kv-tool[aria-pressed="true"]` and `.kv-tabs button[aria-selected="true"]` use an `ink-1` fill, while APA, Rainfall and the other selections beside them are indigo.
   - Fix: `background:var(--indigo);color:var(--on-indigo);border-color:var(--indigo)`.
6. **SVG text below 12 px.**
   - Where (smallest size measured; widths are 834 and 1440 unless noted):

     | Figure | Smallest size |
     |---|---|
     | `#fig1` | labels 11.5 px, O₂ subscript 8.6 px |
     | `#rp-blue` | 8.9 px at 1440 |
     | `#rp-red`, `#rp-black`, `#rp-white` | 10.2 to 11.8 px |
     | `.rangefig` (Figs. 11, 12) | 9.3 px |
     | `.ws-fig` (wells) | 10.5 px |
     | `.tmp-fig` (Fig. 16) | 8.3 px at 834 |
     | `#pt-market` | 9.4 px |
     | one plain `figure` | 5.7 px at 834 (run `probe2.js` to name it) |

   - Fix: size SVG labels against the rendered scale, `font-size: calc(12px / var(--k))` with `--k` = rendered width ÷ viewBox width, set by the existing `data-fit` script. Drop a label that then crowds; never shrink it. Subscripts stay at 12 px or more.
7. **Fig. 1 rests unfinished.**
   - Where: all widths, under reduced motion too.
   - Wrong: `figure#fig1[data-dips="1"]` rests at "Dip 1 of 4".
   - Fix: start it at `data-dips="4"`, the deepest blue. The status line is generated from that value.
8. **Look-alike pictures (rule 7).**
   - Where: all widths. Worst at 834, where the second picture fills the column.
   - Wrong: the specimen band (SMarndi, stars on an indigo ground) and `figure.plate.kv-cloth-plate` (SMarndi, star and lattice on an indigo ground) show the same kind of cloth.
   - Fix: crop `kv-cloth-plate` to the red and white border band at its right edge and credit it "cropped", or put the madder-roots plate in that row.
9. **Fig. 10's title appears twice.**
   - Where: all widths.
   - Fix: hide `h2.kx-h`. The figure caption already carries "Inside one cotton fibre: the vat, then the air".
10. **One control per job.**
    - Wrong: "Watch it being made" appears in chapter 11 (`#gen-reset`) and again under "How this answer was made" in chapter 12.
    - Fix: remove the chapter 12 button.
11. **Progress state at rest, and page length.**
    - Wrong: the "How this answer was made" block in Sources shows a checklist ("Understood … Checking each quote", "The answer is ready") and a second, compact list of all 44 sources.
    - Fix: wrap the block, from `.kv-sub-h` "How this answer was made" to the end of "Sections, as they were written", in a closed `<details>`.
    - Effect: with fix 9, this brings 1440 under about 47,000 px.
12. **Two numbering systems in the first screen.**
    - Wrong: the list under `p.kicker` "The answer in seven sections" is numbered 1 to 7, while its items open chapters 3, 5, 2, 4, 6 and so on.
    - Fix: show each item's chapter number instead (3, 5, 2 …), or no numeral.
13. **Second masthead (rule 3).**
    - Wrong: in chapter 6 the framed GI card repeats "Kutch Ajrakh" and the emblem above Fig. 20, and Fig. 20 repeats the masthead's 22 Apr 2024.
    - Fix: drop the card's frame and its name line, and keep Fig. 20 as an ordinary figure.

## Wording changes, which need the owner's OK

1. **The flagged sentence: iron's oxidant (rules 19 and 22).**
   - Current text, in the short answer: "On that treated cloth, iron in the *kut* paste oxidises with the tannic acid into a deep, fast chocolate-black, while madder dye links to the alum mordant and develops red where the *pa* and *gach* pastes were printed."
   - The same wording is also in:
     - the Black card;
     - stage 5's Why;
     - Fig. 8 step 3;
     - "The same iron, two jobs";
     - the quiz.
   - Proposed short answer: "On that treated cloth, the iron in the *kut* paste, oxidised by the air, binds the tannic acid into a deep, fast chocolate-black, while madder dye links to the alum mordant and develops red where the *pa* and *gach* pastes were printed.1,3"
   - Proposed for the other places: "…as the iron in the paste, oxidised by the air, binds the tannic acid."
   - Then drop Fig. 8's "Read 'oxidises with the tannic acid' this way" note, or keep it as the one place where the quote is marked.
   - Why:
     - Air (O₂) oxidises Fe(II), from the ferrous acetate of fermented scrap iron, to Fe(III). The tannin's galloyl and catechol groups are the ligand: they hold Fe(III) as the black charge-transfer complex.
     - Tannins are reducing agents. They do not oxidise iron, and in iron-gall ink they reduce Fe(III).
     - Source 3 already says it: "oxidise when exposed to air and the harda and develop a black colour". The GI quote stays verbatim in its popover.
2. **Leucoindigo is not colourless in the vat.**
   - Current text: "There the dye is leucoindigo, soluble and colourless, and it soaks into the fibre." It recurs in:
     - Fig. 10's lede and legend ("Leucoindigo: soluble, colourless");
     - "Round and back" ("Leuco form soluble, colourless").
   - Proposed: "There the dye is leucoindigo, soluble and pale yellow, and it soaks into the fibre."
   - Why:
     - In the alkaline vat leucoindigo is a mono- or dianion, and its solution is yellow to yellow-green (Blackburn, Bechtold and John, *Coloration Technology* 125, 2009). Only the neutral "indigo white" solid is near colourless.
     - Yellow leuco plus newly formed blue is why the lifted cloth is green. The page's own drawing already paints the vat liquor olive. Keep source 8's "colourless" in its popover.
3. **Fig. 4's leucoindigo caption.**
   - Current text: "In the vat, soluble and colourless: each oxygen carries a hydrogen."
   - Proposed: "In the vat, soluble and pale yellow: the alkali takes the hydrogen from each oxygen and holds the dye as its sodium salt; drawn here as neutral leucoindigo. INFERRED"
   - Why: at the vat's pH (above 11) the 3,3′-diol is deprotonated. The page's own balanced hydros equation gives C₁₆H₁₀N₂Na₂O₂.
4. **Woad is not a third dye.**
   - Current text: "It is one of only three natural vat dyes, with woad and Tyrian purple.8"
   - Proposed: "With Tyrian purple it is one of the natural vat dyes; woad, named beside them, is another plant that gives the same indigo.8"
   - Why: *Isatis tinctoria* gives indigotin, C₁₆H₁₀N₂O₂, identical to *Indigofera*'s. Counting woad as a dye mixes a plant with a molecule (rule 18).
5. **Myrobalan's tannin is not C₇₆H₅₂O₄₆.**
   - Current text, in the Harde card: "C76H52O46 tannic acid PubChem CID 16129778". In Fig. 8: "Tannic acid C76H52O46 in the cotton · CID 16129778".
   - Proposed card line: "chebulagic and chebulinic acids, gallic acid; tannic acid, C₇₆H₅₂O₄₆, shown as the model gallotannin".
   - Why: commercial tannic acid is a gallotannin from galls and sumac. *Terminalia chebula* fruit tannins are chiefly the ellagitannins chebulagic acid (C₄₁H₃₀O₂₇) and chebulinic acid (C₄₁H₃₂O₂₇), with corilagin and gallic acid (Bag et al., *Asian Pacific Journal of Tropical Biomedicine* 3, 2013). Check the CIDs (chebulagic 442674, chebulinic 72284) before use. The GI's "Tannic acid" stays in its quote.
6. **Indian madder and alizarin.**
   - Current text: "Indian madder holds high amounts of alizarin, the main compound behind red in most natural dyes;32". The Madder card shows "C14H8O4 alizarin; also purpurin" for *Rubia cordifolia*.
   - Proposed: keep the sentence and add a Sources differ note: "Mouri and Laursen find purpurin and munjistin the main colourants of *Rubia cordifolia*, with little or no alizarin, unlike European madder." On the card, put purpurin first and give alizarin as the synthetic dye's compound.
   - Source: C. Mouri and R. Laursen, *Microchimica Acta* 179, 2012; D. Cardon, *Natural Dyes*, 2007.
   - Why: the page itself cites the Met (10) saying Indian and European madders differ chemically. Record the disagreement; never settle it.
7. **The lime resist needs a mechanism (rule 20).**
   - Current text: "Lime in the outline resist discharges alum…", and Fig. 5's title "…and lime takes the alum away".
   - Proposed: keep the GI verb and add one cited mechanism sentence once a source is found (a calico-printing text on alkaline resists for alumina mordants, such as Knecht and Fothergill, *Principles and Practice of Textile Printing*).
   - Candidate, to check: "Strongly alkaline lime turns the alum in the paste into aluminium hydroxide and aluminate that wash out with the resist instead of fixing on the fibre."
   - Also add an iron–tannin structure for Black: Fe(III) chelated by two galloyl groups, drawn like Fig. 7.
8. **Kin panel across senses (rules 15 and 18).**
   - Current text: "SHARES ALIZARIN — Alizarin is made from the root bark of aal, identified as Morinda tinctoria (Indian mulberry).48"
   - Proposed: link Bagh by alum (its alum sentence is already on the page), or drop the card.
   - Why: *Morinda* gives morindone-type anthraquinones, not madder's alizarin. The page's own sentence 10 says the two are chemically different.
9. **One true count (rules 4 and 5).**
   - Current text: "Drawn from 44 sources · 24 more for the kin crafts", beside "Monograph drawn from 20 sources".
   - Proposed: "Drawn from 20 sources · 24 more from the family, kin monographs and compound records · 24 for the kin crafts". Simpler still: keep only the masthead strip.
   - Why: 44 = 20 own + 8 family + 2 kin-monograph + 14 compound records. Two different 24s now sit side by side.
10. **Raw question in other languages (rule 1).**
    - Current text: "समझाइए कि Ajrakh कैसे काम करता है, सबसे पूर्ण, व्यापक, विस्तृत विवरण-पुस्तिका की…" and "سمجھائیے کہ Ajrakh کیسے کام کرتا ہے، سب سے مکمل، جامع اور تفصیلی رہنما کتاب کی ط…"
    - Proposed: "Ajrakh कैसे काम करता है?" and "Ajrakh کیسے کام کرتا ہے؟"
11. **Native name in the masthead (rule 1).**
    - Proposed: add Sindhi اجرڪ (`lang="sd-Arab" data-script="Arab" dir="rtl"`) and "ajrak", from claim C152, at equal standing with "Kutch Ajrakh", if it is marked reviewed.
12. **Fig. 10.**
    - Current text: "The model drew this explainer from the five cited sentences beneath it while the answer was written, because Model-built explainers was on in Ask. It runs in its own sealed frame, in the fonts that frame can use."
    - Proposed: remove Fig. 10 entirely. It retells Fig. 1 (rule 6), and all five of its sentences are already on the page. At least remove this paragraph, which is settings and pipeline wording.
13. **Indigo record.**
    - Current text: "PubChem's main indigo record, CID 10215, files another tautomer" (Fig. 4), against "…CID 5318432, the same molecule in its (2E), C=O form" (Data). Fig. 21 cites CID 10215.
    - Proposed data note: "PubChem's main record, CID 10215, draws a hydroxy tautomer; the models and cards use CID 5318432, the (2E) C=O form." Use CID 5318432 in Fig. 21 as well.
14. **Rail labels (rule 4).**
    - Wrong: "1 The cloth" opens "At a glance", and "11 Media" opens "Pictures, video and film".
    - Proposed: rail "1 At a glance", or retitle the chapters to match the rail.

## What would raise each score to 9 or above

- **Design:** design fixes 1 to 6, which are the system breaches. Fixes 7, 8, 11 and 13 for rest state, repetition and length. Wording changes 9, 10, 11 and 12 for the first minute, true counts and the signature told once.
- **Chemistry:** wording change 1 in all 7 places. Changes 2 and 3, so the signature figure is chemically consistent. Changes 4, 5 and 8 for ambiguous terms. Change 6 recorded as Sources differ. Change 7: a cited lime mechanism plus an iron–tannin structure, so Black and White reach Blue's and Red's depth.

## Applied on 2026-11-19, with the owner's OK

The page is structured content (decision 0105), so every change below is an edit to its content or
template, rebuilt by `app.scripts.build_monograph`.

- **Wording 1, iron's oxidant:** done in all 7 places (short answer, Black card, stage 5's Why,
  Fig. 8 step 3, "The same iron, two jobs", the kin passage and the quiz): the iron, oxidised by
  the air, binds the tannic acid. Fig. 8's "Read 'oxidises with the tannic acid' this way" note is
  dropped; the GI quote stays verbatim in its popover.
- **Wordings 2 and 3, leucoindigo:** pale yellow in all 13 places, including the molecule cards, the
  round-and-back cycle, the keys, the sealed Fig. 10 and Fig. 4's new caption.
- **Wording 4, woad:** done.
- **Wording 5, myrobalan:** tannic acid is labelled the model tannin, and one new sentence says
  harde's own tannins are hydrolysable ones, chebulinic acid among them, citing Bag, Bhattacharyya
  and Chattopadhyay (2013), source 69. Chebulagic acid's CID was not added.
- **Wording 6, madder:** a cited "Sources differ" sentence, from sources already on the page (the
  GI records name purpurin beside alizarin; the Met finds India's red dyes chemically different
  from dyer's madder). Mouri and Laursen (2012) could not be read (sign-in) and is not cited; the
  Madder card is unchanged.
- **Wording 7, the lime mechanism:** waits for a source.
- **Wording 10, the question:** removed from the page entirely (owner): the masthead reads "Kutch
  Ajrakh", the Hindi and Urdu panels no longer open with the raw prompt, and Cite this page titles
  the page "Kutch Ajrakh".
- **Wordings 8, 9, 11, 12, 13 and 14:** left as they are (owner).
- **Design fixes 6, 7, 8, 11, 12 and 13:** done.
  - SVG labels never render below 12 px: the `data-fit` script raises any smaller label, and the
    unfitted well chart's axis is set to 12 px. Checked at 360, 834 and 1440.
  - Fig. 1 rests at dip 4, the deepest blue.
  - The cloth plate is cropped to its floral field, border and the red cloth beside it, with the
    caption and credit changed to match ("cropped").
  - "How this answer was made" is a closed disclosure.
  - The first screen's list shows each item's chapter number.
  - The GI card loses its frame and its repeated name line.

## How this document is kept true

It is a point-in-time critique of 19 November 2026 and is not regenerated. Its "Applied" section
records what changed with the owner's OK; what still waits is in [NEXT.md](../NEXT.md), Owner
decisions. Re-read it before changing the Kutch Ajrakh page's wording or design.
