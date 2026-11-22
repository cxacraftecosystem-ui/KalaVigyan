import { citationShape, UUID } from "@/lib/answerShapes";
import { CONTRIBUTED_RULE, contributedPlateShape, shelvedRightly, type ContributedPlate } from "@/lib/craftContributed";
import { DAY, MONTH } from "@/lib/craftOrigins";
import { pageRelativeShape, SAME_FAMILY_MAX, ENVIRONMENT_FACTORS, type PageRelative } from "@/lib/craftPageContext";
import { PLACE_ROLES } from "@/lib/districtCraftsContract";
import { explainerSentenceShape, mediaRefShape, WIKIDATA_ID, type ExplainerSentence, type MediaRef } from "@/lib/explainerBlockBase";
import {
  BLOCK_SHAPES,
  BUILT_BLOCK_KINDS,
  BUILT_FIGURE_KINDS,
  differReadingShape,
  type BlockByKind,
  type DifferReading,
  type TypedBlockKind
} from "@/lib/explainerContract";
import { datasetShape, type RegionDataset } from "@/lib/regionContract";
import { pageFieldPhotoShape, type PageFieldPhoto } from "@/lib/fieldVoicesContract";
import { integer, list, matching, nullable, number, object, oneOf, ruled, ShapeError, tagged, text, type Shape } from "@/lib/shape";
import type { Citation } from "@/lib/types";

export const CHAPTER_KEYS = ["glance", "made", "chem", "why", "history", "market", "whatif", "people", "kin", "sources"] as const;
export const FIGURE_KINDS = ["FIGURE", "TABLE"] as const;
export const BORROWED_SCOPES = ["FAMILY", "KIN"] as const;
export const ORIGIN_BASES = ["CURATED", "STORED", "READERS"] as const;
export const GENERATED_KINDS = ["MODEL", "AI_IMAGE", "AI_VIDEO"] as const;
export const AI_MEDIA_KINDS = ["IMAGE", "VIDEO"] as const;
export const SOURCE_GROUPS = ["GOVERNMENT", "SCHOLARSHIP", "MUSEUM", "WEB_AND_PRESS", "FIELD", "FAMILY", "KIN", "LIBRARY", "COMPOUND_RECORDS"] as const;
export const PART_KINDS = [
  "key_facts",
  "register_facts",
  "plate",
  "record",
  "sources_differ",
  "places",
  "communities",
  "field_photos",
  "relatives",
  "source_list",
  "open_questions",
  "searched",
  "start_research",
  "ai_media",
  "contributed"
] as const;
export const NOT_ON_THE_PAGE = ["quiz", "compare", "map_layer"] as const;
export const PAGE_BLOCK_KINDS = [...BUILT_BLOCK_KINDS.filter((kind) => !(NOT_ON_THE_PAGE as readonly string[]).includes(kind)), ...BUILT_FIGURE_KINDS, "artisan_voice"] as const;
export const KIN_ITEM_KINDS = ["concept_graph", "relatives"] as const;
export const QUESTION_SHOWN_MAX_CHARS = 160;
export const FIELD_PHOTOS_SHOWN = 12;
export const RESEARCH_QUESTIONS = 3;
export const TAB_CHAPTERS = { overview: "glance", process: "made", science: "chem", region: "why", sharedScience: "kin", sources: "sources", evidence: "sources" } as const;

export type ChapterKey = (typeof CHAPTER_KEYS)[number];
export type PageBlockKind = (typeof PAGE_BLOCK_KINDS)[number] & TypedBlockKind;
export type PageBlock = BlockByKind[PageBlockKind];
export type Borrowed = { scope: (typeof BORROWED_SCOPES)[number]; slug: string; label: string };
export type FigureHead = { kind: (typeof FIGURE_KINDS)[number]; title: string; borrowed: Borrowed[] };
export type AskedQuestion = { text: string | null; askedIn: string };
export type ItemOrigin = {
  basis: (typeof ORIGIN_BASES)[number];
  generated: (typeof GENERATED_KINDS)[number] | null;
  model: string | null;
  generatedOn: string | null;
  fromQuestion: AskedQuestion | null;
};
export type Focal = { x: number; y: number; width: number; height: number };
export type PagePlate = { media: MediaRef; caption: string; standIn: string | null; focal: Focal | null; sentences: ExplainerSentence[] };
export type LabelledFact = { label: string; value: string; citations: Citation[] };
export type RegisterFact = { label: string; value: string };
export type EntryPlace = { key: string; name: string };
export type RecordEntry = {
  label: string;
  start: number | null;
  end: number | null;
  factor: (typeof ENVIRONMENT_FACTORS)[number] | null;
  place: EntryPlace | null;
  sentences: ExplainerSentence[];
  plate: PagePlate | null;
};
export type AreaName = { lgd: number | null; name: string };
export type ChapterPlace = {
  key: string;
  name: string;
  kind: string;
  roles: (typeof PLACE_ROLES)[number][];
  district: AreaName | null;
  state: AreaName | null;
  country: string;
  wikidataId: string | null;
  sentences: ExplainerSentence[];
};
export type ChapterCommunity = { key: string; kind: string; name: string; localNames: string[]; honours: string[]; place: string | null; placeKey: string | null; sentences: ExplainerSentence[] };
export type SourceGroupList = { group: (typeof SOURCE_GROUPS)[number]; title: string; sourceIds: string[] };
export type PictureCredit = { mediaId: string; credit: string };
export type OpenQuestion = { key: string | null; question: string; settledBy: string | null; sentences: ExplainerSentence[] };
export type PageAiMedia = {
  assetId: string;
  kind: (typeof AI_MEDIA_KINDS)[number];
  url: string;
  mime: string;
  width: number | null;
  height: number | null;
  durationSeconds: number | null;
  altText: string;
  sentences: ExplainerSentence[];
  stageId: string | null;
  origin: ItemOrigin;
};
export type PagePart =
  | { kind: "key_facts"; facts: LabelledFact[] }
  | { kind: "register_facts"; facts: RegisterFact[] }
  | { kind: "plate"; plate: PagePlate }
  | { kind: "record"; entries: RecordEntry[] }
  | { kind: "sources_differ"; reading: DifferReading }
  | { kind: "places"; places: ChapterPlace[] }
  | { kind: "communities"; communities: ChapterCommunity[] }
  | { kind: "field_photos"; photos: PageFieldPhoto[]; total: number }
  | { kind: "relatives"; crafts: PageRelative[]; family: { label: string; path: string } | null }
  | { kind: "source_list"; groups: SourceGroupList[]; datasets: RegionDataset[]; pictures: PictureCredit[] }
  | { kind: "open_questions"; questions: OpenQuestion[] }
  | { kind: "searched"; searched: { query: string; site: string }[] }
  | { kind: "start_research"; questions: string[] }
  | { kind: "ai_media"; media: PageAiMedia[] }
  | { kind: "contributed"; pictures: ContributedPlate[] };
export type PartKind = PagePart["kind"];
export type ChapterItem = { block: PageBlock | null; part: PagePart | null; figure: FigureHead | null; origin: ItemOrigin | null; pieceId: string | null };
export type Chapter = { key: ChapterKey; title: string; opener: PagePlate | null; items: ChapterItem[] };

const AI_GENERATED = { IMAGE: "AI_IMAGE", VIDEO: "AI_VIDEO" } as const;

const sentences = (min = 0) => list(explainerSentenceShape, min);
const facts = (min = 0) => ruled(sentences(min), "facts only; a hypothesis is an open question", (shown) => shown.every((sentence) => sentence.level !== "HYPOTHESIS"));
const fraction = ruled(number, "a fraction from 0 to 1", (value) => value >= 0 && value <= 1);

const focalShape: Shape<Focal> = ruled(object<Focal>({ x: fraction, y: fraction, width: fraction, height: fraction }), "a focal box inside its picture", (box) => box.width > 0 && box.height > 0 && box.x + box.width <= 1 && box.y + box.height <= 1);

export const pagePlateShape: Shape<PagePlate> = ruled(
  object<PagePlate>({ media: mediaRefShape, caption: text, standIn: nullable(text), focal: nullable(focalShape), sentences: facts() }),
  "a plate drawn inline",
  (plate) => plate.media.display === "INLINE"
);

const askedShape: Shape<AskedQuestion> = object<AskedQuestion>({
  text: nullable(ruled(text, `a question of at most ${QUESTION_SHOWN_MAX_CHARS} characters`, (shown) => shown.length >= 1 && shown.length <= QUESTION_SHOWN_MAX_CHARS)),
  askedIn: matching(MONTH, "a month, YYYY-MM")
});

export const itemOriginShape: Shape<ItemOrigin> = ruled(
  object<ItemOrigin>({
    basis: oneOf(ORIGIN_BASES),
    generated: nullable(oneOf(GENERATED_KINDS)),
    model: nullable(text),
    generatedOn: nullable(matching(DAY, "a day, YYYY-MM-DD")),
    fromQuestion: nullable(askedShape)
  }),
  "a generated item with its model and day, and a question only on a reader's piece",
  (origin) =>
    (origin.generated === null) === (origin.model === null) && (origin.generated === null) === (origin.generatedOn === null) && (origin.fromQuestion === null || origin.basis === "READERS")
);

const aiMediaShape: Shape<PageAiMedia> = ruled(
  object<PageAiMedia>({
    assetId: UUID,
    kind: oneOf(AI_MEDIA_KINDS),
    url: matching(/^\/api\/crafts\/media\/[0-9a-f-]{36}$/, "the asset's page address"),
    mime: text,
    width: nullable(integer),
    height: nullable(integer),
    durationSeconds: nullable(number),
    altText: text,
    sentences: facts(1),
    stageId: nullable(UUID),
    origin: itemOriginShape
  }),
  "AI media labelled as made, a video with its length",
  (item) => item.origin.generated === AI_GENERATED[item.kind] && (item.kind === "IMAGE" || item.durationSeconds !== null)
);

const recordEntryShape: Shape<RecordEntry> = ruled(
  object<RecordEntry>({
    label: text,
    start: nullable(integer),
    end: nullable(integer),
    factor: nullable(oneOf(ENVIRONMENT_FACTORS)),
    place: nullable(object<EntryPlace>({ key: text, name: text })),
    sentences: facts(1),
    plate: nullable(pagePlateShape)
  }),
  "a span running forward, its start and end together",
  (entry) => (entry.start === null) === (entry.end === null) && (entry.start === null || entry.end === null || entry.start <= entry.end)
);

const areaShape: Shape<AreaName> = object<AreaName>({ lgd: nullable(integer), name: text });

const PART_SHAPES: { readonly [K in PartKind]: Shape<Extract<PagePart, { kind: K }>> } = {
  key_facts: object({ kind: oneOf(["key_facts"] as const), facts: list(object<LabelledFact>({ label: text, value: text, citations: list(citationShape, 1) }), 1) }),
  register_facts: object({ kind: oneOf(["register_facts"] as const), facts: list(object<RegisterFact>({ label: text, value: text }), 1) }),
  plate: object({ kind: oneOf(["plate"] as const), plate: pagePlateShape }),
  record: object({ kind: oneOf(["record"] as const), entries: list(recordEntryShape, 1) }),
  sources_differ: object({ kind: oneOf(["sources_differ"] as const), reading: differReadingShape }),
  places: object({
    kind: oneOf(["places"] as const),
    places: list(
      object<ChapterPlace>({
        key: text,
        name: text,
        kind: text,
        roles: list(oneOf(PLACE_ROLES), 1),
        district: nullable(areaShape),
        state: nullable(areaShape),
        country: text,
        wikidataId: nullable(WIKIDATA_ID),
        sentences: sentences(1)
      }),
      1
    )
  }),
  communities: object({
    kind: oneOf(["communities"] as const),
    communities: list(
      object<ChapterCommunity>({ key: text, kind: text, name: text, localNames: list(text), honours: list(text), place: nullable(text), placeKey: nullable(text), sentences: sentences(1) }),
      1
    )
  }),
  field_photos: ruled(
    object({ kind: oneOf(["field_photos"] as const), photos: list(pageFieldPhotoShape, 1), total: integer }),
    `at most ${FIELD_PHOTOS_SHOWN} photographs, no more than counted`,
    (part) => part.photos.length <= FIELD_PHOTOS_SHOWN && part.photos.length <= part.total
  ),
  relatives: ruled(
    object({ kind: oneOf(["relatives"] as const), crafts: list(pageRelativeShape), family: nullable(object({ label: text, path: matching(/^\/categories\/[A-Za-z0-9-]+$/, "a family page path") })) }),
    `kin crafts (at most ${SAME_FAMILY_MAX}) or the family page`,
    (part) => part.crafts.length <= SAME_FAMILY_MAX && (part.crafts.length > 0 || part.family !== null)
  ),
  source_list: ruled(
    object({
      kind: oneOf(["source_list"] as const),
      groups: list(object<SourceGroupList>({ group: oneOf(SOURCE_GROUPS), title: text, sourceIds: list(text, 1) }), 1),
      datasets: list(datasetShape),
      pictures: list(object<PictureCredit>({ mediaId: UUID, credit: text }))
    }),
    "each source once, in one group each",
    (part) => unique(part.groups.flatMap((group) => group.sourceIds)) && unique(part.groups.map((group) => group.group))
  ),
  open_questions: object({ kind: oneOf(["open_questions"] as const), questions: list(object<OpenQuestion>({ key: nullable(text), question: text, settledBy: nullable(text), sentences: sentences(1) }), 1) }),
  searched: object({ kind: oneOf(["searched"] as const), searched: list(object({ query: text, site: text }), 1) }),
  start_research: ruled(object({ kind: oneOf(["start_research"] as const), questions: list(text) }), `${RESEARCH_QUESTIONS} questions`, (part) => part.questions.length === RESEARCH_QUESTIONS),
  ai_media: ruled(object({ kind: oneOf(["ai_media"] as const), media: list(aiMediaShape, 1) }), "each AI asset drawn once", (part) => unique(part.media.map((item) => item.assetId))),
  contributed: ruled(object({ kind: oneOf(["contributed"] as const), pictures: list(contributedPlateShape, 1) }), CONTRIBUTED_RULE, (part) => shelvedRightly(part.pictures))
};

export const pagePartShape: Shape<PagePart> = tagged<PagePart>("kind", PART_SHAPES as Record<string, Shape<PagePart>>);
export const pageBlockShape: Shape<PageBlock> = tagged<PageBlock>(
  "kind",
  Object.fromEntries(PAGE_BLOCK_KINDS.map((kind) => [kind, BLOCK_SHAPES[kind as PageBlockKind]])) as Record<string, Shape<PageBlock>>
);

const figureShape: Shape<FigureHead> = object<FigureHead>({
  kind: oneOf(FIGURE_KINDS),
  title: text,
  borrowed: list(object<Borrowed>({ scope: oneOf(BORROWED_SCOPES), slug: text, label: text }))
});

export const chapterItemShape: Shape<ChapterItem> = ruled(
  object<ChapterItem>({ block: nullable(pageBlockShape), part: nullable(pagePartShape), figure: nullable(figureShape), origin: nullable(itemOriginShape), pieceId: nullable(UUID) }),
  "an answer block or a page part, never both",
  (item) => (item.block === null) !== (item.part === null)
);

export const chapterShape: Shape<Chapter> = object<Chapter>({ key: oneOf(CHAPTER_KEYS), title: text, opener: nullable(pagePlateShape), items: list(chapterItemShape, 1) });

function unique(values: readonly string[]): boolean {
  return new Set(values).size === values.length;
}

export function checkChapters(chapters: readonly Chapter[]): void {
  const keys = chapters.map((chapter) => chapter.key);
  if (!unique(keys)) throw new ShapeError("chapters", "each chapter once");
  if (keys.join() !== CHAPTER_KEYS.filter((key) => keys.includes(key)).join()) throw new ShapeError("chapters", "the monograph's order");
}
