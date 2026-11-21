# The storyboard of a flagship

A flagship is storyboarded on paper before anything is drawn: one header and one row per state.
The storyboard is what an agent hands back for review before drawing, what a reviewer reads first,
and what the drawing is checked against at the end. It cites facts by id; it never holds prose a
reader will see.

## The header

| Line | What it holds |
|---|---|
| Family | its label and the slug of its page (`Metal-Craft-Category`) |
| Mechanism | the one change every craft of the family shares, in a few words |
| Anchor | the curated craft whose facts stand beside the family's, by slug |
| Label | `shared/<field>/<name>`, after `list_components` found nothing that fits or nearly fits |
| Kind | the kind that carries it, and the registered components it links to instead of redrawing |
| Rests on | the state shown at first paint, normally the last |
| Beside it | the what-if, molecules or chain placed next to it, by label or as a later delivery |
| Borrowed by | the crafts that will place it, each marked `VARIANT` (own facts) or `SUBJECT_LINK` (none) |

## The rows

| Column | What it holds |
|---|---|
| State | its number and a name of a few words, the rail's label |
| Shows | what the drawing holds: the object, the materials on it and the one thing that changed |
| Facts | the ids of the facts that state it, family facts first |
| Sentences | the page sentences citing those facts, or the units you will write, each with its facts |
| Materials | each material drawn and its specimen or molecule token, or "no token" |
| Conditions | each temperature, time, proportion or depth exactly as a quote gives it, with its fact |
| Equation | the balanced equation a source states, or why the step has none |
| Missing | the facts, tokens or kind the state still needs |

A row whose Facts cell is empty is not a state yet. A row with anything under Missing is not drawn
until that is settled: research the facts, ask the team for the tokens or the kind.

## A storyboard, filled

Textiles, from the backlog: the facts are the ones `flagships.md` lists, read again with
`get_facts` on 2026-11-21.

| Line | Value |
|---|---|
| Family | Textiles, `Textiles-Based-Craft-Category` |
| Mechanism | two mordants, one dye bath, then a resist and the vat |
| Anchor | `Machilipatnam-Kalamkari` |
| Label | `shared/chemistry/two-mordants-one-bath` |
| Kind | `reaction_player`, a reaction drawn for each step; the vat links to `shared/chemistry/indigo-vat-dip` |
| Rests on | state 5 |
| Beside it | a `VARIANT` of `kutch-ajrakh/chemistry/what-if-wash-water` (alum or iron) and `shared/chemistry/alizarin-purpurin-3d` |
| Borrowed by | the curated block printers and kalamkari, each a `VARIANT` where its own mordants differ |

| State | Shows | Facts | Materials | Conditions | Equation | Missing |
|---|---|---|---|---|---|---|
| 1. Tannin first | a cotton square soaked in myrobalan | `927272fb-c58c-5fc5-b35c-2c1baffc4430`, `9c16ca66-9f3f-5231-967a-5ea5aa091725` | cotton `--dye-cloth`; soaked cotton `--dye-harda` | none stated | none: the sources give the step no reaction | a fact giving the soaked cloth's colour at Machilipatnam |
| 2. Two mordants printed | iron printed black on the tannin; alum printed where red will be | `a12abe8c-bc7e-50f0-b815-e9724fd661e8`, `8d1cc58b-91ab-5b47-b99e-5218c76468b9`, `278fbf07-3721-50c9-95e1-8eae1778e016` | black `--dye-kut`; the alum print as an outline only | none stated | none stated by the sources held | a fact giving the printed alum's colour before the bath |
| 3. Loose mordant washed out | running water over the square | `2a26748e-4f03-5009-a9f5-7aac56adc219` | as in state 2 | "one hour" | none: a washing | none |
| 4. One bath, two colours | the square in the madder bath, red where alum was, black where iron was | `b25ce086-7bb1-5708-b119-f511e4058f99`, `0fe8538d-c217-56ce-bbab-eee0dfa4fd26`, `e5b26369-810a-5de7-bcbe-3414f9c10706`, `31e2c359-79b2-57f1-aa7a-477032b9941e` | red `--dye-madder`; black `--dye-kut` | "an hour and a half" | none stated; the molecule links to `shared/chemistry/alizarin-purpurin-3d` | the bath's temperature, if a source gives it |
| 5. Resist, then the vat | wax over the reds, the square lifted from the vat | `d08e97d1-fb66-5840-893a-a747e4b71a3f`, `ec41630b-5440-5a1a-9aa6-5c0b3134e005`, `3aa18c50-239e-502d-9ceb-c19dab86996b` | wax: no token; blue `--dye-indigo` | none stated | the dip player's, linked | a specimen token for beeswax |

What this storyboard tells its agent before any drawing: two facts to research (the soaked cloth's
colour and the alum print's colour, or draw both as outlines), one token to ask for (beeswax), and
nothing to redraw that the library already holds (the vat, the alizarin molecule).
