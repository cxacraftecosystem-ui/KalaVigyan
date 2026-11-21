# The family flagships

The starting backlog: for each of the nine families of the atlas, the candidate flagship, the anchor
craft beside the family's own page, the facts KalaVigyan already holds for each state, the task to
claim and what is still missing. The facts were read from the production server on 2026-11-21: a
craft's with `get_facts` by field, and the family's own from its page at
`/categories/<slug>` on the site. `get_facts` now reads the family page too, named as subject
`{kind "category", slug}`. Read each again before you cite it, since a fact may have been held from
its page or joined by others since. Read only your family's section.

Each section gives:

| Part | What it gives |
|---|---|
| Pages | the family's page and the anchor craft, by slug |
| Why this one | what makes it the family's shared mechanism |
| Shared by | the sub-families and crafts that will borrow it, and those that will not |
| Task | the anchor's open-work task, from `list_open_work` on the same day; the family's own is its `FLAGSHIP` task (Open work and the flagships, below) |
| Carried by | the kind, the registered components it links to and the what-if beside it |
| Missing | what must be found or made before it is drawn |
| The states and their facts | a table, "Read from" naming the family's page or the craft whose `get_facts` gave the fact, and the fact's statement as held |

## Textiles: two mordants, one bath, then the vat

- **Pages**: `Textiles-Based-Craft-Category`; anchor `Machilipatnam-Kalamkari`.
- **Why this one**: mordant and resist dyeing is how the family's printed and dyed cloths take
  colours that last, and the family page and Kalamkari's state every step, from the tannin to the
  vat. It is the one family whose specimen colours exist already.
- **Shared by**: every printed or resist-dyed cloth of the family: block prints, kalamkari,
  bandhani, leheriya. Embroidery and carpets are made with dyed thread and take it as kin.
- **Task**: none on the anchor, whose reaction-player need the shared indigo players already meet;
  the nearest open one is `MISSING_COMPONENT:craft:Kutch-Bandhani:reaction-player` (HIGH), for
  Bandhani's own resist and bath.
- **Carried by**: `reaction_player`, a reaction drawn for each step; the vat state links to
  `shared/chemistry/indigo-vat-dip`; beside it a what-if, alum or iron, as a `VARIANT` of
  `kutch-ajrakh/chemistry/what-if-wash-water`. The filled storyboard in `storyboard.md` is this one.
- **Missing**: the colour of myrobalan-soaked cloth and of printed alum at Machilipatnam; the madder
  bath's temperature; a specimen token for beeswax; the iron and tannin reaction stated for the
  family (Ajrakh's player states it for Ajrakh only).

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Tannin first | `927272fb-c58c-5fc5-b35c-2c1baffc4430` | family page | Untreated cotton could not absorb madder, so the cloth was first dipped in a tannin solution and then mordanted so the dye could bond and remain insoluble. |
| 1. Tannin first | `9c16ca66-9f3f-5231-967a-5ea5aa091725` | `Machilipatnam-Kalamkari` | In step c, the white cloth is soaked evenly in myrobalan juice and dried in sunlight, the myrobalan acting as a mordant for block printing. |
| 1. Tannin first | `8d1cc58b-91ab-5b47-b99e-5218c76468b9` | `Machilipatnam-Kalamkari` | The tannin in myrobalan reacts with iron salt to produce black; with alum it improves fastness of the red dye; it helps cotton absorb iron and alum salts more evenly. |
| 2. Two mordants printed | `a12abe8c-bc7e-50f0-b815-e9724fd661e8` | `Machilipatnam-Kalamkari` | Two mordants, kasim and karam, are printed; the printing of iron mordant precedes that of alum. |
| 2. Two mordants printed | `278fbf07-3721-50c9-95e1-8eae1778e016` | `Machilipatnam-Kalamkari` | Karam, the red printing mordant, is babul gum solution mixed with an alum decoction, and its printed portions turn firm red when boiled with madder and alizarin. |
| 3. Loose mordant washed out | `2a26748e-4f03-5009-a9f5-7aac56adc219` | `Machilipatnam-Kalamkari` | The cloth is washed in flowing water to remove gum and unwanted mordant so colour does not develop in unwanted areas; after washing for one hour it is dried in the sun. |
| 4. One bath, two colours | `b25ce086-7bb1-5708-b119-f511e4058f99` | family page | With a red dye such as madder or chay root, an alum mordant gives red and an iron mordant gives black. |
| 4. One bath, two colours | `0fe8538d-c217-56ce-bbab-eee0dfa4fd26` | family page | A mordant fixes the dye molecule to the fibre and changes the hue, intensity and fastness of the result. |
| 4. One bath, two colours | `e5b26369-810a-5de7-bcbe-3414f9c10706` | `Machilipatnam-Kalamkari` | The mordant-printed fabric is submerged and boiled for an hour and a half with alizarin and jajaku leaves, swirled for even permeation. |
| 4. One bath, two colours | `31e2c359-79b2-57f1-aa7a-477032b9941e` | `Machilipatnam-Kalamkari` | During boiling red develops from alum plus alizarin while alizarin also helps fix the black. |
| 5. Resist where blue is not wanted | `d08e97d1-fb66-5840-893a-a747e4b71a3f` | `Machilipatnam-Kalamkari` | Indigo needs no mordant, so wax resist protected areas not to be blue before dipping in the vat. |
| 5. Resist where blue is not wanted | `ec41630b-5440-5a1a-9aa6-5c0b3134e005` | family page | After the reds, chintz is covered in beeswax except where blue is wanted, then dipped into indigo, the wax resisting the dye. |
| 6. The vat | `3aa18c50-239e-502d-9ceb-c19dab86996b` | family page | Indigo is insoluble in water, so it is reduced to a soluble colourless leuco form that enters the fibre and reoxidises to insoluble blue in air. |
| 6. The vat | `bcd937f4-463e-5f0a-81d1-07c0c95dc582` | family page | Traditional indigo vats reduce the dye by fermentation, carried out by naturally occurring microbes under alkaline, anaerobic conditions. |

## Metal: lost-wax casting

- **Pages**: `Metal-Craft-Category`; anchor `Bastar-Dhokra`.
- **Why this one**: the family page states lost-wax casting in general and for dhokra and
  Chola-style bronzes, and Bastar Dhokra states each step with its proportions, its furnace and its
  heat. Two accounts of Aranmula's mirror describe it as cast by lost wax too.
- **Shared by**: the cast crafts of brass and bell metal, bronze and metal crafts: the dhokras of
  Bastar, Adilabad and Bengal, Swamimalai bronze icons, Aranmula Kannadi. Hammered vessels, filigree
  and the inlay of bidri and koftgari are mechanisms of their own, for their own players.
- **Task**: `MISSING_COMPONENT:craft:Bastar-Dhokra:reaction-player` (HIGH); each cast craft's own
  reaction-player task closes with a `SUBJECT_LINK` or `VARIANT` keyed to it.
- **Carried by**: `reaction_player`, a reaction drawn for each step, each step saying why it has no
  equation (none is stated); beside it a what-if, brass alone or with bronze, on how freely the melt
  runs.
- **Missing**: specimen tokens for beeswax, the clay coat, the glowing mould and molten and cast
  bell metal; the melting range of dhokra's mixed metal (the 750 °C held for Aranmula is delta
  bronze, another alloy, and is never borrowed); what happens at the cast's surface as it cools.

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Clay core | `b6ecc15b-7df9-5345-910e-3567fcde20d1` | family page | A dhokra caster moulds a core of clay, rice husk and water, covers it with threads of beeswax mixed with resin, and coats the wax model with a fine layer of clay. |
| 1. Clay core | `719ce082-e2c6-554c-bcd2-2069430b0518` | `Bastar-Dhokra` | The core of a figure is shaped from black soil brought from the fields and kneaded with paddy husk, then left to dry in the sun. |
| 1. Clay core | `363142f6-a0b1-54ad-8273-ecff710ff523` | `Bastar-Dhokra` | Rice husk, called bhoosa, holds the soil together, makes the mould porous and keeps it from cracking during firing. |
| 2. Wax model | `b834a61e-7cfb-5df9-959e-c1a9ecdbf2ba` | `Bastar-Dhokra` | Raw beeswax is melted in a pot and filtered through coarse cotton cloth into a clay pot of water, where it sets and floats. |
| 2. Wax model | `e5f65f11-3e43-5f28-b278-77e75e6089d1` | `Bastar-Dhokra` | Wax strings are wrapped closely around the hard, green-coated model, and further designs are added in plain wax. |
| 3. Clay coat and channels | `c8a447a1-455a-5fa5-98ee-1d2616204aaf` | `Bastar-Dhokra` | Once the core is dry it is covered with clean, sticky riverside soil mixed with powdered dung or wood coal, in proportions of 85-90% soil to 10-15% dung or coal. |
| 3. Clay coat and channels | `d22cb755-2059-5839-b597-f70f60cd5040` | `Bastar-Dhokra` | A channel is made at the bottom of the decorated model for pouring the metal, and a pin made of wax is inserted in it. |
| 3. Clay coat and channels | `cfa22a02-e146-5020-997c-5f3b99e01ce0` | `Bastar-Dhokra` | A final layer of powdered termite-hill soil covers the model, with larger wax channels added to form an inverted funnel for pouring the metal. |
| 4. Fire: wax out, metal molten | `cbbb14cc-0a00-5f36-b426-6e16a6e980ac` | family page | In dhokra, dewaxing and casting are often done together: the model with its metal-filled clay bowl is fired in a pit furnace 0.3-0.6 metres deep, then turned over. |
| 4. Fire: wax out, metal molten | `0a31b75b-2546-5e26-9dfe-68e39cd13a3d` | `Bastar-Dhokra` | Blowing through the pipe raises the fire to about 1000-1200 degrees Celsius, the heat needed to melt the metal. |
| 4. Fire: wax out, metal molten | `03e7bd26-45bd-54ef-a3fa-aea9560ce658` | `Bastar-Dhokra` | Because dewaxing happens inside a closed mould, the wax is hard to reclaim, as it vaporises and burns or soaks into the mould's clay. |
| 4. Fire: wax out, metal molten | `8d62a631-8933-58d2-85f0-5098a089938e` | `Bastar-Dhokra` | In a second furnace, metal pieces in the proportion of 200 grams of bronze to 800 grams of brass are melted in a crucible. |
| 4. Fire: wax out, metal molten | `4dc046eb-3fa2-5ebc-8584-b3194827909c` | `Bastar-Dhokra` | The GI application explains that brass alone is too viscous to flow easily into the mould, while heavier, less viscous bronze helps the melt run through narrow channels. |
| 5. The pour | `ce27e50f-2373-58f5-9667-fa0ce474ef29` | `Bastar-Dhokra` | When the fired mould turns red it is held upside down, and molten metal from the crucible is poured into its funnel to replace the wax. |
| 5. The pour | `9e65aba7-c844-5752-97ad-af78d9106301` | family page | In cire perdue or lost-wax casting, a wax model is coated in clay, molten metal replaces the escaping wax, and the figure is then chased with hand tools. |
| 6. Cool and break | `28c1ea0f-4f42-5eaf-b177-683590ecc598` | `Bastar-Dhokra` | The cast is left to cool for 1-6 hours depending on its size, and water is sprinkled on it if it has not cooled. |
| 6. Cool and break | `cdcfbd45-cc3d-54c2-9c66-8f1a21a05655` | `Bastar-Dhokra` | The outer mould is broken gently with a wooden mallet, and the piece is cleaned with wire brushes and files. |

## Clay: firing, heat and air

- **Pages**: `Mud-Based-Craft-Category`; anchor `Nizamabad-Black-Pottery`, with
  `Krishnanagar-Terracotta`.
- **Why this one**: every pot and terracotta of the family is fired, and the family page and both
  curated crafts state what heat does at each stated temperature and how the air in the kiln makes
  the same clay red or black.
- **Shared by**: terracotta and pottery, and the fired clay and mud crafts, Jaipur's blue pottery
  among them, whose glaze adds a step of its own.
- **Task**: `MISSING_COMPONENT:craft:Nizamabad-Black-Pottery:reaction-player` (MEDIUM).
- **Carried by**: `reaction_player`, one scene of a pot in the kiln whose parts change at each
  step, each step's temperature from its facts; beside it a what-if, open to the air or smothered.
  Read along its temperature, the firing is the first case for a new general kind.
- **Missing**: specimen tokens for raw, leather-hard, red-fired and black-fired clay; iron's
  oxidation as a source writes it (the facts give hematite and the lower oxides, not a reaction);
  a second source for Nizamabad's firing temperature.

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Dried before the fire | `f00fb976-29ea-5525-bfb9-5d7fd313bb55` | `Nizamabad-Black-Pottery` | The ware is dried, ideally slowly and evenly in shade, before firing. |
| 2. Water leaves the clay mineral | `7687cf86-9ccf-5fcc-9cd0-85f76c30a8dc` | `Nizamabad-Black-Pottery` | Kaolinite begins to lose its hydroxyl water at 550–600 °C, forming disordered metakaolin; hydroxyl loss continues up to 900 °C. |
| 2. Water leaves the clay mineral | `ad03d709-7849-511e-98b2-dda5b12bfd24` | family page | Firing at a minimum of 550°C is needed for pottery of considerable hardness and durability, and irreversible changes in clay structure begin at 500° C. |
| 3. Quartz turns at 573 °C | `984c0242-7fc8-5ecd-b38a-67203e513576` | `Nizamabad-Black-Pottery` | At ambient pressure, alpha quartz changes abruptly to beta quartz at 573 °C. |
| 3. Quartz turns at 573 °C | `7a6778e6-06c6-5706-b6d9-879f633986c0` | `Nizamabad-Black-Pottery` | At 573 °C quartz changes reversibly and suddenly between its alpha and beta forms with an abrupt volume change, straining the surrounding body. |
| 4. Grains bond | `e11b81ee-0c66-5e9a-b51a-2886642c3e6e` | family page | In sintering, clay minerals decompose and grain edges bond by ion diffusion; kaolinite restructures at 585° C and smectite at 678° C. |
| 4. Grains bond | `bc57e48d-04bf-529d-83f4-02da47aa31ea` | family page | At 900° C clay minerals lose their structure and form new silicate minerals. |
| 5. Air decides the colour | `0c1f8353-55e9-5de9-b2da-b28c006c32f6` | family page | Oxidising firing burns off organic matter to give a light colour, while in reducing conditions carbon from the fuels is deposited on pots, leaving black or dark brown surfaces. |
| 5. Air decides the colour | `15f7e5c5-ddd4-5c72-872b-b15228f8afbd` | `Nizamabad-Black-Pottery` | In oxidising conditions iron forms red hematite (Fe2O3); in reducing conditions lower oxides such as magnetite or FeO form, grey to black. |
| 5. Air decides the colour | `8a9cc95d-a573-5bcc-92b1-a136054a1a91` | `Nizamabad-Black-Pottery` | Carbon burns out from the surfaces inward and needs oxygen and time; where either is lacking, carbon remains in the core. |
| 5. Air decides the colour | `366c1697-ea97-5158-a028-46711b74a7c5` | `Nizamabad-Black-Pottery` | Potters keep oxygen out of the kiln during firing, because oxygen would turn the pottery red instead of black. |
| 5. Air decides the colour | `49f1e3a3-108b-55bc-8f64-8efa70881ac8` | `Nizamabad-Black-Pottery` | The potter opens the fire to air, or smothers it with fuel, dung or sawdust to cut off oxygen. |

## Stone: carving by removal

- **Pages**: `Stone-Craft-Category`; anchor `Mahabalipuram-Stone-Sculpture`, with
  `Konark-Stone-Carving`; for inlay, `Agra-Marble-Inlay`.
- **Why this one**: every stone craft takes stone away to leave a form, and the family's facts tie
  the tool and the pace to the stone's hardness, from talc-rich soapstone to granite.
- **Shared by**: stone carving and the stone crafts. Stone inlay cuts and grinds the same way and
  adds the setting: it is the second candidate.
- **Task**: `MISSING_COMPONENT:craft:Mahabalipuram-Stone-Sculpture:reaction-player` (MEDIUM); for
  inlay, `MISSING_COMPONENT:craft:Agra-Marble-Inlay:reaction-player` (MEDIUM).
- **Carried by**: `reaction_player` with physical steps, each naming the stone and its tool and
  saying why it has no equation; beside it a what-if, soft stone or granite.
- **Missing**: specimen tokens for the stones; the family's stones on a stated hardness scale (none
  is held); the minerals that make granite hard (talc in soapstone is held).

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. The stone sets the tool | `155b60df-ed58-546d-b1f2-d245845be43f` | family page | Sivonen writes that soft stones are easier to carve than granite and easy to carve by hand, while granite and blue metal need more force and different tools because they are much harder. |
| 1. The stone sets the tool | `07e5f9ae-c420-5e77-974a-d64cc72408c1` | family page | The same statement says marble is the hardest form of limestone and soapstone the softest and easiest to work. |
| 1. The stone sets the tool | `5054bc9f-f908-5bb6-aeaf-14ebe1c97216` | family page | Jha writes that a high amount of talk (talc) in its composition makes soapstone soft and craft-friendly. |
| 2. Rough cut to the block | `73505123-c9bd-5539-8d2c-54b9e893b9a1` | family page | In Mamallapuram, carving started with rough cutting the stone to size, then drawing the statue on the block and cutting off the extra stone around the image. |
| 3. Layer by layer | `b7435f29-072b-5c06-96b8-5d61e049fe42` | family page | In Mamallapuram, the whole statue was usually worked layer by layer, from the sketch to the rough shape and then to the final finishing touches. |
| 3. Layer by layer | `5bf5c0b6-b563-5f8b-bc6d-400e27b9e49d` | family page | The Varanasi statement says unwanted stone is chiselled out of harder stones, while in softer stones it is scraped out with a sharp flat-edged iron tool. |
| 3. Layer by layer | `d9bbc332-3e25-5d56-9818-a6b0b50562a1` | family page | A Mamallapuram carver controlled the outcome of the carving by manipulating the angle of the chisel and the force of the hammer blow. |
| 4. Detail and finish | `db60eee1-e2e3-564c-8f21-dc333bc06c87` | `Mahabalipuram-Stone-Sculpture` | D'source describes the detailing and minor carving with sharp-edged and pointed chisels after rough carving, before the finished product is polished with sandpaper. |
| 4. Detail and finish | `b6401a06-aab9-5c77-8ad7-95969a72ca65` | family page | Sandpaper gives carved stone its final finish in Dhakotha soapstone carving and in Karnataka icon carving, where it is followed by coconut oil. |
| Inlay, the second candidate | `6295f3d7-ae77-51a8-a039-85b11423df74` | family page | Pietra dura, Italian for hard stone, is a technique in which precious and semi-precious stones are cut, polished and inlaid, generally on hard stone such as marble. |
| Inlay, the second candidate | `e948191f-4b41-58e4-a9e0-6389f9f322df` | `Agra-Marble-Inlay` | Grooves are cut into the base stone with a chisel so that the shaped stones fit them perfectly. |
| Inlay, the second candidate | `5d8f2ca5-b289-5e2c-83ca-ca6237fc0cc1` | `Agra-Marble-Inlay` | The inlay stones are cut and shaped to the design on an emery wheel, and because each part is shaped individually the work is time consuming. |
| Inlay, the second candidate | `786eb00e-256f-5678-9df1-f334c6d36633` | `Agra-Marble-Inlay` | The GI application says the stones are inlaid into the grooves with glue, by traditional methods using charcoal or modern ones using araldite. |

## Wood: turning and lac

- **Pages**: `Wood-Craft-Category`; anchor `Sankheda-Furniture`, whose facts are on the family page.
  The family has no curated craft; Channapatna Toys and Dolls, curated in More crafts, holds the
  fullest facts on the same mechanism.
- **Why this one**: turning on the lathe and lacquering with lac are stated step by step on the
  family page and Channapatna's. Seasoning, the one step every wood craft shares, is its first
  state; seasoning alone is the first candidate for the whole family, but the facts held give its
  times and none of the moisture or shrinkage that explain it, so it waits.
- **Shared by**: turned and lacquered wood, the wooden artware and toys turned on a lathe, and
  Channapatna. Carving, inlay and marquetry share the seasoning state only.
- **Task**: `MISSING_COMPONENT:craft:Sankheda-Furniture:reaction-player` (MEDIUM); Channapatna's
  `MISSING_COMPONENT:craft:Channapatna-Toys-Dolls:reaction-player` (HIGH) closes with a `VARIANT`
  citing its own facts.
- **Carried by**: `reaction_player`; the lac step names the lac and its stated pigments and says why
  it has no equation.
- **Missing**: specimen tokens for wood, lac and its colours; a stated softening temperature of
  lac; the moisture content of seasoned wood.

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Seasoned billet | `6f8ef9d6-2b9a-5cea-ad62-e371d3ee2eb6` | family page | Kiln-seasoning does the work of natural drying in very roughly one-twelfth of the time needed to air-season the same timber, but is expensive on a small scale. |
| 1. Seasoned billet | `81c9cdfb-2596-56ec-b935-eeb56e487e31` | family page | At Channapatna, hale logs for lac-turnery are cut into billets and seasoned away from heat and sunlight for ten days to a month, depending on the moisture content of the wood. |
| 2. Turned on the lathe | `73e3eeab-bfa7-54bd-8006-100034806a72` | family page | The Punjab turner's lathe (adda) held the wood between spikes on two iron bars and was spun by a bow whose thong looped once round a peg. |
| 2. Turned on the lathe | `a1d89010-6517-529a-8041-540bafbfe770` | family page | On the lathe, cutting tools scrape thin continuous chips from the revolving wood, and the shaped piece is sanded smooth while still turning. |
| 2. Turned on the lathe | `a5eaac63-1b72-5a13-937a-6a91f584f40f` | family page | Gujarat's craft portal says Sankheda furniture is made by turning teak pieces on a lathe, applying powdered tin in a solvent, lacquering and leaf-polishing them, then assembling the furniture. |
| 3. The lac stick | `d6f8a0af-89cd-5ed1-9241-3d9d42e9c624` | family page | Lac is a resinous substance secreted by the lac insect, a member of the scale-insect super-family Coccidae. |
| 3. The lac stick | `2fbf8f6d-97da-55c6-9ac2-cf55c5afe6f0` | `Channapatna-Toys-Dolls` | For coloured lac sticks, lac chips are heated over a coal fire, colourant is added as they melt, and the evenly coloured paste is cooled and cut into sticks. |
| 4. Friction melts the lac | `a377d2ad-b29b-5543-9ef4-8caeba8d55eb` | family page | In lac-turnery a stick of coloured lac (batti) is pressed against the revolving wood, and the heat of friction melts the lac onto the surface. |
| 4. Friction melts the lac | `7fee6004-37be-50ae-9cac-54807ee91807` | `Channapatna-Toys-Dolls` | The turned wooden items are lacquered in a dry state by means of frictional heat, and the painted lac gives them a bright, colourful appearance. |
| 5. Leaf burnish | `1568c8f6-8a9a-5398-a8ba-cde38a73d830` | family page | Channapatna turners buff lacquered pieces with leaves of the screw pine, talegiri (Pandanus odoratissimus), which lends the finish translucency and gloss. |
| Seasoning, the first candidate | `08e800a8-e42a-5efd-9924-f1da446e81f3` | family page | Trotter called unseasoned wood the chief stumbling-block to adopting India's lesser-known timbers and said the importance of proper seasoning cannot be over-emphasized. |
| Seasoning, the first candidate | `bf6939eb-3e3f-5d16-9e31-1260862d40e9` | family page | Teak shrinks less than other timbers and its natural oil slows the absorption of moisture, so it responds slowly to changing weather. |
| Seasoning, the first candidate | `cb57e3f6-827d-58a7-a1be-0ca30ac65685` | family page | The Udayagiri craftsman was unable to make his boxes during the hot months, because the wood cracked under the knife. |

## Leather: tanning

- **Pages**: `Leather-Craft-Category`; anchor `Kolhapuri-Chappal`. The family has no curated craft;
  Kolhapuri's bag tanning is stated on the family page, and its own page holds no process facts.
- **Why this one**: leather is tanned hide, and the family page states how tannin binds collagen,
  at what acidity, and what that changes: the temperature at which the hide shrinks.
- **Shared by**: the footwear and leather goods sub-families.
- **Task**: `MISSING_COMPONENT:craft:Kolhapuri-Chappal:reaction-player` (MEDIUM).
- **Carried by**: `reaction_player`; beside it a what-if, vegetable or chrome tanning.
- **Missing**: specimen tokens for raw hide and tanned leather; Kolhapuri's own bag-tanning steps
  as facts of its page; the shrinkage temperature of vegetable-tanned buffalo hide (the 70 °C held
  is goatskin with pala tannin).

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. The hide and its collagen | `a240e9b6-5aea-5374-a343-b4f5d4e40729` | family page | Of a mammal hide's three layers, the corium, the thick central layer, is used to make leather once the other two are removed. |
| 1. The hide and its collagen | `fda07b59-6896-5ea8-badc-9495a04c3adc` | family page | Leather is made of collagen protein polymer, a skin-derived fibrillar type I collagen material. |
| 2. Prepared for tanning | `bb10778f-9257-5885-b98c-84f0b981ba54` | family page | At the tannery hides are soaked, limed in lime and water to loosen the hair, then washed, delimed, bated and pickled. |
| 3. Tannin enters | `13bc3616-50db-5c1e-87b3-74b9ff3ec235` | family page | Vegetable tanning soaks hides in increasingly strong tan liquors for weeks or months, producing a firm, water-resistant leather. |
| 3. Tannin enters | `ba23d94c-b5c1-582c-a1b6-115fe8d6c832` | family page | Kolhapuri bag tanning uses babul bark (Acacia arabica) and myrobalan nuts (hirda, Terminalia chebula). |
| 4. Tannin binds collagen | `4465cb61-d2fd-5e8a-a7c0-ae65380c29c5` | family page | Tanning takes its name from tannin, the agent that displaces water from between the hide's protein fibres and cements these fibres together. |
| 4. Tannin binds collagen | `65b57b2b-2cdb-56df-8181-938fb52275c9` | family page | The weakly anionic phenolic groups of vegetable tannins form ionic bonds with collagen's amino groups and hydrogen bonds with its carboxyl groups. |
| 4. Tannin binds collagen | `45bc75db-1cb2-5474-a7df-1e1b043b9cda` | family page | Vegetable tanning is carried out at pH 3 to 4, where weakly anionic polyphenols are attracted to the cationic amino groups of collagen. |
| 5. Shrinks only when hotter | `b184c5f6-38e0-5987-9b10-2094351d759b` | family page | Raw hides or skins shrink very easily at about 55 °C, while chrome-tanned leather shows shrinkage temperatures higher than 100 °C. |
| 5. Shrinks only when hotter | `7fd9700d-1d34-52b0-b977-575ce8709c2e` | family page | Britannica's eleventh edition described chrome-tanned leather as much stronger than any other and able to stand boiling water, whereas vegetable-tanned leather was completely destroyed at 70° C. |
| Chrome, the what-if | `42881c1f-5d9d-5fac-82df-23075047868d` | family page | Chrome tanning soaks the delimed, dehaired hide in a Cr(III) salt solution, preferably basic chromium sulphate, Cr4(SO4)5(OH)2, less toxic than hexavalent chromium. |
| Chrome, the what-if | `648bc8e4-3aa9-583d-827a-4b7ad2f92fac` | family page | Cationic chromium binds to the carboxylic groups of collagen's amino acids, and amino nitrogen forms ligands with chromium, together forming a metal complex. |

## Natural fibre and grass: along the fibre

- **Pages**: `Natural-Fibre-Grass-Work`; anchor `Bareilly-Cane-Bamboo-Craft`, with
  `Uttarakhand-Ringal-Craft`.
- **Why this one**: cane, bamboo, ringal, reed and grass are worked along their length: cut when
  their starch is low, protected, split along the fibre, softened with water and bent with heat.
  The family page and both curated crafts state each step.
- **Shared by**: cane and bamboo, grass work, and leaf, reed and rattan. Coir and jute free their
  fibre by retting, the second candidate.
- **Task**: `MISSING_COMPONENT:craft:Bareilly-Cane-Bamboo-Craft:reaction-player` (MEDIUM).
- **Carried by**: `reaction_player`, physical steps naming the culm and what acts on it; the starch
  and boron steps name their compounds.
- **Missing**: specimen tokens for green and dried culm, cane and grass; why water and heat let a
  culm bend (no fact states it); the temperature a cane is heated to.

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Cut when starch is low | `e0dc751d-3300-54de-b1bc-29dabef95ad0` | family page | Bamboo is best harvested in the dry season, avoiding rains and flowering, when its starch content is lowest and starch-feeding borers and fungi attack less. |
| 1. Cut when starch is low | `532581ac-8c01-5c78-9321-f74bc6d9022a` | family page | Soaking freshly felled culms in water for a few weeks leaches out their starch and gives some protection from borers, though not from fungi. |
| 2. Protected | `02f920d3-7526-533c-b9df-c4b3c5b60941` | family page | In heat treatment bamboo is rubbed with castor oil and heated over a gentle fire, and smoking lowers its moisture and leaves a protective layer of tar. |
| 2. Protected | `c99f6416-1543-5378-9787-3f5b2c30f3a3` | family page | A bamboo preservative is made as a 5% aqueous solution of boric acid and borax in the ratio 1: 1.5, and boron salts are effective against termites and fungi. |
| 3. Split along the fibre | `d0eabd9a-0205-53ed-865b-70f8a86f4395` | family page | Bamboo fibres run longitudinally through the internode, which makes splitting easier, but run transversely at the node. |
| 3. Split along the fibre | `e5913f0e-87ef-5539-970f-69ba27168e2a` | `Bareilly-Cane-Bamboo-Craft` | Slicing runs lengthwise along the densely packed fibres and is a fairly smooth operation, needing only the requisite amount of moisture in the culm. |
| 4. Softened with water | `2bba60b1-94a0-536c-bffd-0ea11eb228a0` | `Bareilly-Cane-Bamboo-Craft` | Thin cane is soaked in water until it takes up moisture, and the bamboo is immersed in water for 2 hours to absorb moisture. |
| 4. Softened with water | `2517cbb5-4a67-59bf-89eb-924a759df027` | `Uttarakhand-Ringal-Craft` | For winnows, a long ringal pole is split into wide thin splits; slightly tender splits are used directly, and dried splits are soaked in water to regain moisture. |
| 5. Bent with heat | `dbf22725-80ac-5f2f-9ff7-231d9176ccae` | `Bareilly-Cane-Bamboo-Craft` | The bamboo stick is heated with a kerosene lamp and bent to the desired shape; heated bamboo is easy to bend. |
| 5. Bent with heat | `ea9cfc86-03c6-5ec7-b481-9d62684b11cb` | `Bareilly-Cane-Bamboo-Craft` | The cane is heated on a slow fire, generally with a kerosene lamp, for flexibility before it is bent into shape. |
| Retting, the second candidate | `b236ecaa-2d71-501e-857f-5f0a79305ee6` | family page | As retting progresses, the polyphenols and pectins that hold coir fibres together in the husk are biologically degraded, freeing the individual fibres. |
| Retting, the second candidate | `0e35d49f-b290-5e58-8f42-7bbbd4d73279` | family page | The lignocellulose of coir fibre normally resists microbial attack, so retting does not disintegrate the fibre itself. |

## Paper: fibre to sheet

- **Pages**: `Paper-Craft-Category`; anchor `Arunachal-Pradesh-Monpa-Handmade-Paper`. The family has
  no curated craft; its page holds the facts, for Kashmiri, Monpa, Jaipur, Kagazipura and Kalpi
  paper.
- **Why this one**: handmade paper and papier-mache both start from fibres freed, beaten to pulp and
  laid as a sheet or in layers, and the family page states each step for several centres.
- **Shared by**: handmade paper and papier-mache; sanjhi stencils are cut from the sheet it makes.
- **Task**: `MISSING_COMPONENT:craft:Arunachal-Pradesh-Monpa-Handmade-Paper:reaction-player`
  (MEDIUM).
- **Carried by**: `reaction_player`, a reaction drawn for each step; the step that frees the fibres
  names its alkali.
- **Missing**: specimen tokens for pulp and sheet; what holds a sheet together as it dries (no fact
  states it); Monpa's own steps as facts of its page.

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. Fibres freed | `04b2042e-7cb8-5c1d-8602-71151acac909` | family page | Kashmiri papermakers retted recycled materials in an alkaline lye of crude soda ash, sajjī, and lime, which disintegrated woven articles and separated the fibres. |
| 1. Fibres freed | `cf9723f9-b37b-5f24-8b4e-f5a76017b450` | family page | Monpa papermakers boil cut bark for 3 to 4 hours in ash water; the boiling is meant to remove organic substances, and it softens the bark. |
| 2. Beaten to pulp | `9162fca0-1070-5399-bb39-b75b8e647d6f` | family page | The boiled bark is beaten to pulp with a wooden hammer on a flat stone, a step called Thungu that compresses the pulp and strengthens the paper. |
| 3. The sheet formed | `8042aba6-a2d6-533a-b2bd-2d00ef2ab2c8` | family page | Jaipur papermakers dip framed wire sieves into the tank of pulped cotton, shake them gently so the fibres interlock, drain the water and sun-dry the sheet. |
| 3. The sheet formed | `83c9435a-58c5-557c-bb42-68c3ffc8cccc` | family page | A wooden frame overlaid with a bamboo or cane mesh is dipped horizontally into the vat, called the hauz, and lifted to gather the pulp. |
| 3. The sheet formed | `aeded621-328e-52b8-b762-1b8b71325d42` | family page | Kashmiri sheets were made by dipping the mould twice, so each sheet had two layers of pulp, what is today called a double-dip. |
| 4. Dried | `f3709b99-e5f6-5fe6-a62c-699ee32b0d52` | family page | Kalpi's GI application describes rags beaten to pulp by a machine with water and chemicals, the pulp drained by hand onto a metallic sheet, and pressed sheets hung on a line to dry. |
| 5. Sized and burnished | `812cb2b5-18e1-5505-bc41-9050aa5d680e` | family page | Each dry sheet was rubbed with burnt potter's clay, then sized with rice flour paste applied with a mitt of very hard, thick wool felt. |
| 5. Sized and burnished | `ac4a3298-a802-5d5e-b582-723a64e30431` | family page | Hard burnishing tightened the grain of Kashmiri paper and considerably thinned each sheet without taking away its weight. |
| 5. Sized and burnished | `783feae0-f0b8-5f67-b338-772a634ac181` | family page | Examined specimens of Kashmiri paper range from 0.06 mm to 0.15 mm in thickness, with 8 to 11 laid lines per centimetre. |
| What the fibre is | `f970a7a4-4855-5fe9-8756-4091c0f0dbb3` | family page | Plant cell walls are mainly cellulose, hemicellulose, lignin, pectin and glycoproteins, and non-cellulosic glycans shape their density, crystallinity and tensile strength. |
| What the fibre is | `5d929173-765a-5256-9c7f-7c660280ba85` | family page | Glycome profiling found xylan, arabinogalactans and rhamnogalacturonan-I on Monpa paper, and their presence is correlated with its high tensile strength. |

## More crafts: ground, pigment and binder

- **Pages**: `Miscellaneous`; anchor `Orissa-Pattachitra`, with `Madhubani-Paintings`.
- **Why this one**: no one mechanism runs through all of this family's sub-families. Folk painting
  is its largest, and every painting there is a ground, pigments and a binder, stated on the family
  page and on Pattachitra's.
- **Shared by**: folk painting. Jewellery, glass and beads, lac, toys and instruments take
  flagships of their own later, glass first: it is the second candidate, anchored on
  `Firozabad-Glass`.
- **Task**: `MISSING_COMPONENT:craft:Orissa-Pattachitra:reaction-player` (HIGH); for glass,
  `MISSING_COMPONENT:craft:Firozabad-Glass:reaction-player` (MEDIUM).
- **Carried by**: `reaction_player`; the pigment step names cinnabar and orpiment as the family's
  facts identify them, with their PubChem records and hazards from `lookup`.
- **Missing**: specimen tokens for the mineral pigments, the chalk ground and the lacquer; what a
  gum binder does as the paint dries (no fact states it); glass's melting reactions as a source
  writes them (the facts give the fluxes, the carbon dioxide and the silicates, not an equation).

### The states and their facts

| State | Fact | Read from | It states |
|---|---|---|---|
| 1. The ground | `f395c728-6b5f-5dc8-9aa8-b758aafc068a` | `Orissa-Pattachitra` | The canvas is made by pasting layers of old, used cotton cloth, such as saris or dhotis, together with tamarind glue. |
| 1. The ground | `0d7746b3-01f0-590a-a0f1-c475ce138bab` | `Orissa-Pattachitra` | Tripathy describes khadi pathara chalk ground fine and mixed 1:2 with water, then made sticky with 400 gm of tamarind glue per kg of chalk powder. |
| 1. The ground | `bf44fb5f-7de4-56ff-b074-9a218e315ce0` | `Orissa-Pattachitra` | The GI application says that when the first coat is a bit dry it is rubbed with round soft stones called barada or jhuna barada, the first phase of rubbing with jhuna barada. |
| 2. Pigments from minerals | `8542c006-62d2-5b78-abba-549b828fa841` | `Orissa-Pattachitra` | Crude cinnabar is levigated in a mortar with sugar water or lime juice and the yellowish water drained off, fifteen times or more for the purest, then mixed with gum, formed into tablets and dried. |
| 2. Pigments from minerals | `0430065e-2578-513e-8f6f-27c28e077ae3` | `Orissa-Pattachitra` | Black is oil wick lamp black, collected from inside an earthen pot put over the oil lamp, where the black from the wick sticks. |
| 2. Pigments from minerals | `bc7ab964-9fc9-5d08-b340-45b6c2a8354c` | family page | Hinglu, a red mineral from a Rajasthan mine, was identified by Raman spectroscopy as the naturally occurring mineral cinnabar (HgS). |
| 2. Pigments from minerals | `2ebb2b37-5c74-56f1-a5da-ce6ef802950d` | family page | Harital, a yellow mineral from a Rajasthan mine, was confirmed by Raman spectroscopy to be orpiment (As2S3). |
| 3. The binder | `0fed20dd-4259-55d2-987d-35a98f59673b` | `Orissa-Pattachitra` | Gum is used in all the colours to make them sticky and permanent, and lacquering is treated as a further binding medium applied after finishing. |
| 3. The binder | `2c2db602-b5cb-52a4-b84d-36e0378c64a4` | family page | In the Jaipur miniature workshop studied, most pigments came from local pansari shops and were prepared by ghutai, grinding the pigment and mixing it with gum Arabic. |
| 3. The binder | `f4cfb73c-87ab-5253-bbfa-c7df6767af2a` | family page | Sohrai artists dilute their soil pigments with water and use no binders. |
| 4. Colour laid in order | `b983d8c7-d0b4-5fb3-83ef-30805fb2deaa` | `Orissa-Pattachitra` | After sketching, the background is coloured first; red backgrounds are the most common in Orissa pattachitra, and traditionally cinnabar was the usual background colour. |
| 5. Sealed over the fire | `3a6c9021-d269-59f3-a5a8-60a993dbe001` | `Orissa-Pattachitra` | The finished painting is held over a charcoal fire and lacquer beaten onto it with a wooden stick and evened with a cloth bundle, kanamunda or dasi, making it water resistant and durable with a shining finish. |
| Glass, the second candidate | `d61886f2-7676-5416-a896-f99c0676a517` | family page | Silica is the glass former and silica sand, the largest constituent of the batch, has a high melting point of 1710°C. |
| Glass, the second candidate | `3dd57204-5b1e-5622-9000-4ecb024d67a0` | family page | In melting, the fluxes melt first and soda ash forms low-melting alkali silicates with sand, which react with the high-melting constituents while carbonates give off carbon dioxide. |
| Glass, the second candidate | `5d3ee0aa-2406-5250-a7ca-adcd17ddcdb0` | `Firozabad-Glass` | The GI journal gives Firozabad soda lime silica glass as 33% soda ash, 66% silica sand and 1% chemicals, produced at around 1450 degrees Celsius. |
| Glass, the second candidate | `305d78bd-5562-500b-b25e-4ecf0560baea` | `Firozabad-Glass` | Annealing heats and cools glass products in a controlled way to remove strains, so that they are not brittle. |

## Open work and the flagships

Each of the nine family pages holds one `FLAGSHIP` task until it draws its flagship, keyed
`FLAGSHIP:category:<slug>`: Metal's is `FLAGSHIP:category:Metal-Craft-Category`. The server holds
this backlog in code, in `research/open_work_flagship_backlog.py`, and a test keeps the two equal:
each family's mechanism and anchor, the facts of its states as the task's fact ids (the first and
second candidates' rows left out), and its Missing line as what is still to find or make. The task
is `HIGH`, since every craft of the family borrows the flagship, and its prompt is `deliver_page`.

- **Open** while the family page draws no registered `reaction_player`, `dip_player`,
  `stage_player` or `experiment_lab`: none rests on the page's facts or on the facts its published
  sections cite, none is keyed to those facts' concepts, and none is named in its layout. A
  waiting or approved proposal that names the key closes it too.
- **Claim** it with `reserve_tasks`, then deliver the player finished in a bundle for the family's
  category page: its spec and units citing the facts above, keyed to the anchor craft, with the
  task as `task_key`. `preview_page` first, then `propose_page`. The proposal is refused, with its
  reason, when it is of another kind, carries no spec or is not keyed to the anchor.
- **Each craft's own task** stays: the `MISSING_COMPONENT` task for the `reaction-player` need,
  named above for each anchor. A delivered reaction player keyed to the anchor completes the
  anchor's task, and each craft that then places it, by a `SUBJECT_LINK` or a `VARIANT` keyed to
  it, completes its own.

## How this backlog is kept true

| What | Kept true by |
|---|---|
| Each family's mechanism, anchor, facts and Missing line equal the server's backlog | `backend/tests/mcp/test_interactives_skill.py`, against `research/open_work_flagship_backlog.FLAGSHIPS` |
| Nine families, each anchored on one of its own crafts | the same test, against the category register |
| Every task it names is a craft's reaction-player task, and the family task's key is the server's | the same test, against `research/open_work.parse_task_key` |
| Each fact is named once | the same test |
| The served copies | the same test, byte for byte against the server's and the site's |

Re-read it when a family's flagship is built, its facts are read again from the server, or a
fact it names is held from its page.
