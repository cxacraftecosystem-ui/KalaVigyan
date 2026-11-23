import { citationShape, CRAFT_PATH, INSTANT, sourceRefShape, storedLevelShape, UUID, type CraftLink, type StoredLevel } from "@/lib/answerShapes";
import {
  COVERAGE_CLASSES,
  CRAFT_GI_STATUSES,
  DEPTH_BASES,
  DIFFER_WEIGHTS,
  environmentStepShape,
  localNameShape,
  pageDepthShape,
  pageEventShape,
  pageGiShape,
  pageRelativeShape,
  pageTabsShape,
  PICTURE_ROLES,
  type EnvironmentStep,
  type LocalName,
  type PageDepth,
  type PageEvent,
  type PageGi,
  type PageRelative,
  type PageTabs,
  type PictureRole
} from "@/lib/craftPageContext";
import { explainerSentenceShape, mediaRefShape, termSpanShape, TERM_KEY, WIKIDATA_ID, type ExplainerSentence, type MediaRef, type TermSpan } from "@/lib/explainerBlockBase";
import { PARTIAL_DATE } from "@/lib/explainerInsight";
import { PLACE_ROLES } from "@/lib/districtCraftsContract";
import { fieldVoicesTotalsShape, pageFieldPhotoShape, pageVoiceShape, type FieldVoicesTotals, type PageFieldPhoto, type PageVoice } from "@/lib/fieldVoicesContract";
import { DISCIPLINES, type Discipline } from "@/lib/explainerContract";
import { pageProcessShape, type PageProcess } from "@/lib/craftPageProcess";
import { boolean, count, integer, list, matching, nullable, number, object, oneOf, positive, ruled, ShapeError, text, type Shape } from "@/lib/shape";
import type { Citation, SourceRef } from "@/lib/types";

export const CRAFT_PAGE_PATH = (slug: string) => `/crafts/${encodeURIComponent(slug)}/page`;
export const CRAFT_EDITION = /^v([1-9]\d{0,5})$/;
export const UNREAD_CHAPTERS = "chapters";

export function craftEdition(segment: string): number | null {
  const found = CRAFT_EDITION.exec(segment);
  return found ? Number(found[1]) : null;
}

export const PROVENANCES = ["CURATED", "SEED", "FROM_ANSWERS", "RESEARCHER"] as const;
export const SECTION_BASES = ["CURATED", "STORED_CLAIMS"] as const;
export const SUBJECT_KINDS = ["CRAFT", "STAGE", "MATERIAL", "TOOL", "PLACE", "COMMUNITY", "TERM", "CONCEPT"] as const;
export { COVERAGE_CLASSES, CRAFT_GI_STATUSES };
export const CRAFT_PAGE_SCHEMA_VERSION = 3;
export const GI_SHOWN = ["REGISTERED", "APPLIED"] as const;
export const NATIVE_NAME_SOURCES = ["DOSSIER", "WIKIDATA"] as const;
export const BORROWED_SCOPES = ["FAMILY", "KIN"] as const;
export const SOURCE_GROUPS = ["GOVERNMENT", "SCHOLARSHIP", "MUSEUM", "WEB_AND_PRESS", "FIELD", "FAMILY", "KIN", "LIBRARY", "COMPOUND_RECORDS"] as const;
export const BORROWED_GROUPS = ["FAMILY", "KIN"] as const;
export const PLACE_KINDS = ["VILLAGE", "TOWN", "DISTRICT", "STATE", "COUNTRY", "REGION", "RIVER"] as const;
export const GROUP_KINDS = ["COMMUNITY", "PERSON", "ORGANISATION"] as const;

export type Borrowed = { scope: (typeof BORROWED_SCOPES)[number]; slug: string; label: string };
export type Focal = { x: number; y: number; width: number; height: number };
export type PagePlate = { media: MediaRef; caption: string; standIn: string | null; focal: Focal | null; sentences: ExplainerSentence[] };
export type Provenance = (typeof PROVENANCES)[number];
export type SubjectKind = (typeof SUBJECT_KINDS)[number];
export type PlaceRole = (typeof PLACE_ROLES)[number];
export type PlaceKind = (typeof PLACE_KINDS)[number];
export type GroupKind = (typeof GROUP_KINDS)[number];

export type PageCraft = CraftLink & {
  id: string;
  displayName: string;
  localName: string | null;
  localNames: LocalName[];
  categoryName: string | null;
  subCategoryName: string | null;
  familyLabel: string | null;
  kindLabel: string | null;
  giStatus: (typeof CRAFT_GI_STATUSES)[number] | null;
  stateOfPractice: string[];
  stateOfOrigin: string[];
};
export type SearchedFor = { query: string; site: string };
export type CurationHeader = { version: number; curatedAt: string; coverage: (typeof COVERAGE_CLASSES)[number]; searched: SearchedFor[] };
export type SubjectRef = { id: string | null; name: string; kind: SubjectKind };
export type PageClaim = {
  id: string;
  text: string;
  level: StoredLevel;
  discipline: Discipline;
  subject: SubjectRef;
  provenance: Provenance;
  sourcesDiffer: boolean;
  citations: Citation[];
};
export type PageSentence = { id: string; text: string; level: StoredLevel; claimIds: string[]; terms: TermSpan[] };
export type KeyFact = { label: string; value: string; claimIds: string[] };
export type OverviewSection = { discipline: Discipline; title: string; basis: (typeof SECTION_BASES)[number]; sentences: PageSentence[] };
export type PageOverview = { lede: PageSentence[]; keyFacts: KeyFact[]; sections: OverviewSection[] };
export type DifferRow = { key: string; about: string; weight: number; claimIds: string[] };
export type PageArea = { lgd: number | null; name: string };
export type PagePlace = {
  key: string;
  name: string;
  kind: PlaceKind;
  role: PlaceRole;
  district: PageArea | null;
  state: PageArea | null;
  country: string;
  wikidataId: string | null;
  claimIds: string[];
};
export type PageCommunity = { key: string; kind: GroupKind; name: string; localNames: string[]; honours: string[]; place: string | null; placeKey: string | null; claimIds: string[] };
export type PageTerm = { key: string | null; label: string; names: string[]; meaning: string | null; language: string | null; script: string | null; claimIds: string[] };
export type PagePicture = { media: MediaRef; caption: string; role: PictureRole; stageId: string | null; claimIds: string[] };
export type PageQuestion = { key: string | null; question: string; settledBy: string | null; claimIds: string[] };
export type Kicker = { family: string | null; kind: string | null };
export type NativeName = { text: string; lang: string; script: string | null; sourceId: string; sourceKind: (typeof NATIVE_NAME_SOURCES)[number]; reviewed: boolean };
export type MastheadGi = { status: (typeof GI_SHOWN)[number]; on: string | null; citations: Citation[] };
export type Reliability = { a: number; b: number; c: number; d: number };
export type MastheadProvenance = { basis: (typeof DEPTH_BASES)[number]; sources: number; reliability: Reliability; curatedOn: string | null; updatedOn: string | null };
export type Masthead = {
  kicker: Kicker;
  name: string;
  nativeName: NativeName | null;
  gi: MastheadGi | null;
  place: string | null;
  provenance: MastheadProvenance;
  picture: PagePlate | null;
  palette: string;
};
export type CiteThis = { url: string; version: number | null; curatedOn: string | null; text: string; bibtex: string };
export type PageSource = SourceRef & { group: (typeof SOURCE_GROUPS)[number]; from: Borrowed | null; supports: number };
export type EvidenceEntry = { claimId: string; foldedIds: string[] };
export type EvidenceSubject = { subject: SubjectRef; entries: EvidenceEntry[] };
export type EvidenceGroup = { discipline: Discipline; title: string; subjects: EvidenceSubject[] };
export type PageEvidence = { groups: EvidenceGroup[]; hypotheses: EvidenceEntry[] };
export type CraftPage = {
  schemaVersion: typeof CRAFT_PAGE_SCHEMA_VERSION;
  craft: PageCraft;
  curated: boolean;
  curation: CurationHeader | null;
  depth: PageDepth;
  suggestedQuestions: string[];
  masthead: Masthead;
  lede: ExplainerSentence[];
  cite: CiteThis | null;
  tabs: PageTabs;
  overview: PageOverview;
  giCard: PageGi;
  events: PageEvent[];
  environment: EnvironmentStep[];
  sourcesDiffer: DifferRow[];
  places: PagePlace[];
  communities: PageCommunity[];
  process: PageProcess;
  glossary: PageTerm[];
  pictures: PagePicture[];
  openQuestions: PageQuestion[];
  sameFamily: PageRelative[];
  voices: PageVoice[];
  fieldPhotos: PageFieldPhoto[];
  fieldVoicesTotal: FieldVoicesTotals;
  evidence: PageEvidence;
  claims: PageClaim[];
  sources: PageSource[];
};

const CLAIM_IDS = list(UUID, 1);

const DAY = matching(/^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/, "a day, YYYY-MM-DD");

const fraction = ruled(number, "a fraction from 0 to 1", (value) => value >= 0 && value <= 1);

const focalShape: Shape<Focal> = ruled(
  object<Focal>({ x: fraction, y: fraction, width: fraction, height: fraction }),
  "a focal box inside its picture",
  (box) => box.width > 0 && box.height > 0 && box.x + box.width <= 1 && box.y + box.height <= 1
);

const facts = ruled(list(explainerSentenceShape), "facts only; a hypothesis is an open question", (shown) => shown.every((sentence) => sentence.level !== "HYPOTHESIS"));

export const pagePlateShape: Shape<PagePlate> = ruled(
  object<PagePlate>({ media: mediaRefShape, caption: text, standIn: nullable(text), focal: nullable(focalShape), sentences: facts }),
  "a plate drawn inline",
  (plate) => plate.media.display === "INLINE"
);

const mastheadShape: Shape<Masthead> = object<Masthead>({
  kicker: object<Kicker>({ family: nullable(text), kind: nullable(text) }),
  name: text,
  nativeName: nullable(
    object<NativeName>({ text, lang: text, script: nullable(matching(/^[A-Z][a-z]{3}$/, "an ISO 15924 script")), sourceId: text, sourceKind: oneOf(NATIVE_NAME_SOURCES), reviewed: boolean })
  ),
  gi: nullable(
    ruled(object<MastheadGi>({ status: oneOf(GI_SHOWN), on: nullable(PARTIAL_DATE), citations: list(citationShape) }), "a GI date only with the claims that state it", (gi) => gi.on === null || gi.citations.length > 0)
  ),
  place: nullable(text),
  provenance: ruled(
    object<MastheadProvenance>({
      basis: oneOf(DEPTH_BASES),
      sources: count,
      reliability: object<Reliability>({ a: count, b: count, c: count, d: count }),
      curatedOn: nullable(DAY),
      updatedOn: nullable(DAY)
    }),
    "a curation day exactly on a curated masthead",
    (provenance) => (provenance.basis === "CURATED") === (provenance.curatedOn !== null)
  ),
  picture: nullable(pagePlateShape),
  palette: text
});

const citeShape: Shape<CiteThis> = ruled(
  object<CiteThis>({ url: matching(/^\/crafts\/[a-z0-9-]+(\/v[1-9]\d*)?$/, "a lower-case craft address"), version: nullable(positive), curatedOn: nullable(DAY), text, bibtex: text }),
  "a versioned address with its version and day, or a plain one with neither",
  (cite) => (cite.version === null) === (cite.curatedOn === null) && (cite.version === null) === !/\/v\d+$/.test(cite.url)
);

const pageSourceShape: Shape<PageSource> = {
  expected: "a listed source with its group",
  parse(value, path) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ShapeError(path, "an object");
    const { group, from, supports, ...source } = value as Record<string, unknown>;
    const at = (name: string) => (path ? `${path}.${name}` : name);
    const listed: PageSource = {
      ...sourceRefShape.parse(source, path),
      group: oneOf(SOURCE_GROUPS).parse(group, at("group")),
      from: nullable(object<Borrowed>({ scope: oneOf(BORROWED_SCOPES), slug: text, label: text })).parse(from, at("from")),
      supports: count.parse(supports, at("supports"))
    };
    if ((BORROWED_GROUPS as readonly string[]).includes(listed.group) !== (listed.from !== null)) throw new ShapeError(at("from"), "the monograph a borrowed source comes from, only when borrowed");
    return listed;
  }
};

const sentenceShape: Shape<PageSentence> = object<PageSentence>({ id: text, text, level: storedLevelShape, claimIds: CLAIM_IDS, terms: list(termSpanShape) });
const areaShape: Shape<PageArea> = object<PageArea>({ lgd: nullable(integer), name: text });
const subjectShape: Shape<SubjectRef> = object<SubjectRef>({ id: nullable(UUID), name: text, kind: oneOf(SUBJECT_KINDS) });
const entryShape: Shape<EvidenceEntry> = object<EvidenceEntry>({ claimId: UUID, foldedIds: list(UUID) });

const overviewShape: Shape<PageOverview> = object<PageOverview>({
  lede: list(sentenceShape),
  keyFacts: list(object<KeyFact>({ label: text, value: text, claimIds: CLAIM_IDS })),
  sections: list(object<OverviewSection>({ discipline: oneOf(DISCIPLINES), title: text, basis: oneOf(SECTION_BASES), sentences: list(sentenceShape, 1) }))
});

const placeShape: Shape<PagePlace> = object<PagePlace>({
  key: text,
  name: text,
  kind: oneOf(PLACE_KINDS),
  role: oneOf(PLACE_ROLES),
  district: nullable(areaShape),
  state: nullable(areaShape),
  country: text,
  wikidataId: nullable(WIKIDATA_ID),
  claimIds: CLAIM_IDS
});

const communityShape: Shape<PageCommunity> = object<PageCommunity>({
  key: text,
  kind: oneOf(GROUP_KINDS),
  name: text,
  localNames: list(text),
  honours: list(text),
  place: nullable(text),
  placeKey: nullable(text),
  claimIds: CLAIM_IDS
});

const claimShape: Shape<PageClaim> = object<PageClaim>({
  id: UUID,
  text,
  level: storedLevelShape,
  discipline: oneOf(DISCIPLINES),
  subject: subjectShape,
  provenance: oneOf(PROVENANCES),
  sourcesDiffer: boolean,
  citations: list(citationShape, 1)
});

const pageFieldsShape: Shape<CraftPage> = object<CraftPage>({
  schemaVersion: oneOf([CRAFT_PAGE_SCHEMA_VERSION] as const),
  craft: object<PageCraft>({
    slug: text,
    name: text,
    path: CRAFT_PATH,
    id: UUID,
    displayName: text,
    localName: nullable(text),
    localNames: list(localNameShape),
    categoryName: nullable(text),
    subCategoryName: nullable(text),
    familyLabel: nullable(text),
    kindLabel: nullable(text),
    giStatus: nullable(oneOf(CRAFT_GI_STATUSES)),
    stateOfPractice: list(text),
    stateOfOrigin: list(text)
  }),
  curated: boolean,
  masthead: mastheadShape,
  lede: list(explainerSentenceShape),
  cite: nullable(citeShape),
  curation: nullable(
    object<CurationHeader>({
      version: positive,
      curatedAt: INSTANT,
      coverage: oneOf(COVERAGE_CLASSES),
      searched: list(object<SearchedFor>({ query: text, site: text }))
    })
  ),
  tabs: pageTabsShape,
  depth: pageDepthShape,
  suggestedQuestions: list(text, 1),
  overview: overviewShape,
  giCard: pageGiShape,
  events: list(pageEventShape),
  environment: list(environmentStepShape),
  sourcesDiffer: list(object<DifferRow>({ key: text, about: text, weight: oneOf(DIFFER_WEIGHTS), claimIds: list(UUID, 2) })),
  places: list(placeShape),
  communities: list(communityShape),
  process: pageProcessShape,
  glossary: list(
    object<PageTerm>({ key: nullable(TERM_KEY), label: text, names: list(text), meaning: nullable(text), language: nullable(text), script: nullable(text), claimIds: list(UUID) })
  ),
  pictures: list(object<PagePicture>({ media: mediaRefShape, caption: text, role: oneOf(PICTURE_ROLES), stageId: nullable(UUID), claimIds: list(UUID) })),
  openQuestions: list(object<PageQuestion>({ key: nullable(text), question: text, settledBy: nullable(text), claimIds: CLAIM_IDS })),
  sameFamily: list(pageRelativeShape),
  voices: list(pageVoiceShape),
  fieldPhotos: list(pageFieldPhotoShape),
  fieldVoicesTotal: fieldVoicesTotalsShape,
  evidence: object<PageEvidence>({
    groups: list(object<EvidenceGroup>({ discipline: oneOf(DISCIPLINES), title: text, subjects: list(object<EvidenceSubject>({ subject: subjectShape, entries: list(entryShape, 1) }), 1) })),
    hypotheses: list(entryShape)
  }),
  claims: list(claimShape),
  sources: list(pageSourceShape)
});

export const craftPageShape: Shape<CraftPage> = {
  expected: pageFieldsShape.expected,
  parse(value, path) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ShapeError(path, "an object");
    const page: Record<string, unknown> = { ...value };
    delete page[UNREAD_CHAPTERS];
    return pageFieldsShape.parse(page, path);
  }
};

