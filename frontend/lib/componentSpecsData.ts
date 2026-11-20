import { className, componentLabel, domId, drawingShape, heldOrUnitShape, heldTextShape, unitRef, type DrawingElement, type HeldNode, type HeldOrUnit } from "@/lib/componentSpecsPlates";
import { boolean, dictionary, integer, list, matching, nullable, number, object, oneOf, text } from "@/lib/shape";

export const LINE_TAGS = ["p", "h3", "li", "span", "dt", "dd", "figcaption", "td", "th"] as const;
export const CHART_FORMS = ["drawing", "dots", "rows", "figure", "series"] as const;
export const MAP_SETTINGS = ["drawing", "explorer"] as const;
export const SOURCE_LIST_SETTINGS = ["status", "listing"] as const;

const cssLength = matching(/^-?\d+(\.\d+)?(%|px)?$/, "a length");
const figureRef = matching(/^[a-z0-9]+:\d+$/, "a figure reference");

export type TextLine = { tag: (typeof LINE_TAGS)[number]; classes: string[]; unit: string | null; text: HeldNode[] | null };
export type FigureNumber = { unit: string; ref: string };
export type FigureHead = { number: FigureNumber | null; title: string; titleId: string | null; dek: string | null; dekId: string | null };
export type Placed = { classes: string[]; left: string | null; width: string | null; top: string | null; hidden: boolean; text: HeldNode[] | null };
export type ToggleOption = { value: string; label: string; pressed: boolean };
export type ToggleGroup = { classes: string[]; label: string; marker: "layers" | "zooms"; optionKey: "layer" | "z"; options: ToggleOption[] };

export const textLineShape = object<TextLine>({ tag: oneOf(LINE_TAGS), classes: list(className), unit: nullable(unitRef), text: nullable(heldTextShape) });
export const figureNumberShape = object<FigureNumber>({ unit: unitRef, ref: figureRef });
export const figureHeadShape = object<FigureHead>({ number: nullable(figureNumberShape), title: unitRef, titleId: nullable(domId), dek: nullable(unitRef), dekId: nullable(domId) });
const placedShape = object<Placed>({ classes: list(className, 1), left: nullable(cssLength), width: nullable(cssLength), top: nullable(cssLength), hidden: boolean, text: nullable(heldTextShape) });
const toggleGroupShape = object<ToggleGroup>({
  classes: list(className, 1),
  label: text,
  marker: oneOf(["layers", "zooms"] as const),
  optionKey: oneOf(["layer", "z"] as const),
  options: list(object<ToggleOption>({ value: text, label: text, pressed: boolean }), 2)
});

export type DotsChart = { classes: string[]; label: string; total: number; marked: number };
export type BarRow = { label: string; value: number; shown: string; emphasis: boolean };
export type RowsChart = { classes: string[]; head: FigureHead; rows: BarRow[]; source: string };
export type FigureChart = { classes: string[]; head: FigureHead; drawing: DrawingElement; source: TextLine };
export type SeriesTable = { summary: string; caption: string; head: string[]; rows: { head: string; cells: (string | null)[] }[] };
export type SeriesPlot = { classes: string[]; label: string; comp: string; series: number[][]; drawing: DrawingElement; labels: Placed[] };
export type SeriesChart = { classes: string[]; head: FigureHead; plot: SeriesPlot; events: string[]; table: SeriesTable; download: { href: string; fileName: string; label: string }; source: string };
export type ChartSpec = { form: (typeof CHART_FORMS)[number]; drawing: DrawingElement | null; dots: DotsChart | null; rows: RowsChart | null; figure: FigureChart | null; series: SeriesChart | null };

export const chartShape = object<ChartSpec>({
  form: oneOf(CHART_FORMS),
  drawing: nullable(drawingShape),
  dots: nullable(object<DotsChart>({ classes: list(className, 1), label: text, total: integer, marked: integer })),
  rows: nullable(object<RowsChart>({ classes: list(className, 1), head: figureHeadShape, rows: list(object<BarRow>({ label: text, value: number, shown: text, emphasis: boolean }), 1), source: unitRef })),
  figure: nullable(object<FigureChart>({ classes: list(className, 1), head: figureHeadShape, drawing: drawingShape, source: textLineShape })),
  series: nullable(
    object<SeriesChart>({
      classes: list(className, 1),
      head: figureHeadShape,
      plot: object<SeriesPlot>({ classes: list(className, 1), label: text, comp: text, series: list(list(number, 1), 1), drawing: drawingShape, labels: list(placedShape) }),
      events: list(unitRef),
      table: object<SeriesTable>({
        summary: text,
        caption: text,
        head: list(unitRef, 1),
        rows: list(object<SeriesTable["rows"][number]>({ head: unitRef, cells: list(nullable(unitRef), 1) }), 1)
      }),
      download: object<SeriesChart["download"]>({ href: matching(/^data:text\/csv/, "a CSV data link"), fileName: text, label: text }),
      source: unitRef
    })
  )
});

export type StatTile = { figure: string; small: string | null; caption: string };
export type StatTilesSpec = { classes: string[]; tiles: StatTile[] };
export const statTilesShape = object<StatTilesSpec>({ classes: list(className), tiles: list(object<StatTile>({ figure: text, small: nullable(text), caption: unitRef }), 1) });

export type FactTableSpec = { id: string; numeral: number; chapterNo: string; title: string; titleId: string; rows: { term: string; value: string }[] };
export const factTableShape = object<FactTableSpec>({
  id: domId,
  numeral: integer,
  chapterNo: unitRef,
  title: unitRef,
  titleId: domId,
  rows: list(object<FactTableSpec["rows"][number]>({ term: unitRef, value: unitRef }), 1)
});

export type TimelineScale = { label: string; marks: { left: string; final: boolean }[]; spans: { left: string; text: string }[]; ticks: { left: string; side: "l" | "mid" | "r"; text: string }[] };
export type TimelineSpec = { variant: string; number: FigureNumber; title: string; scale: TimelineScale; steps: string[] };
export const timelineShape = object<TimelineSpec>({
  variant: className,
  number: figureNumberShape,
  title: unitRef,
  scale: object<TimelineScale>({
    label: text,
    marks: list(object<TimelineScale["marks"][number]>({ left: cssLength, final: boolean }), 2),
    spans: list(object<TimelineScale["spans"][number]>({ left: cssLength, text })),
    ticks: list(object<TimelineScale["ticks"][number]>({ left: cssLength, side: oneOf(["l", "mid", "r"] as const), text }))
  }),
  steps: list(unitRef, 1)
});

export type MapExplorer = {
  head: FigureHead;
  id: string;
  comp: string;
  controls: ToggleGroup[];
  mapLabel: string;
  drawing: DrawingElement;
  inset: { drawing: DrawingElement; caption: string };
  key: { id: string; unit: string };
  caption: string;
  side: TextLine[];
  rank: { caption: string; more: string };
};
export type MapLayerSpec = { setting: (typeof MAP_SETTINGS)[number]; drawing: DrawingElement | null; explorer: MapExplorer | null };
export const mapLayerShape = object<MapLayerSpec>({
  setting: oneOf(MAP_SETTINGS),
  drawing: nullable(drawingShape),
  explorer: nullable(
    object<MapExplorer>({
      head: figureHeadShape,
      id: domId,
      comp: text,
      controls: list(toggleGroupShape, 1),
      mapLabel: text,
      drawing: drawingShape,
      inset: object<MapExplorer["inset"]>({ drawing: drawingShape, caption: unitRef }),
      key: object<MapExplorer["key"]>({ id: domId, unit: unitRef }),
      caption: unitRef,
      side: list(textLineShape, 1),
      rank: object<MapExplorer["rank"]>({ caption: unitRef, more: text })
    })
  )
});

export type SourcesDiffer = { summary: HeldNode[]; body: HeldOrUnit };
export type SequenceCard = { visual: string | null; when: string; title: string; lines: TextLine[]; differs: SourcesDiffer | null };
export type SequenceItem = { card: SequenceCard | null; component: string | null };
export type MapSequenceSpec = { head: FigureHead; first: SequenceItem[]; source: TextLine; more: SequenceItem[] };
const sequenceItemShape = object<SequenceItem>({
  card: nullable(
    object<SequenceCard>({
      visual: nullable(componentLabel),
      when: unitRef,
      title: unitRef,
      lines: list(textLineShape, 1),
      differs: nullable(object<SourcesDiffer>({ summary: heldTextShape, body: heldOrUnitShape }))
    })
  ),
  component: nullable(componentLabel)
});
export const mapSequenceShape = object<MapSequenceSpec>({ head: figureHeadShape, first: list(sequenceItemShape, 1), source: textLineShape, more: list(sequenceItemShape) });

export type TimelineEvent = { view: string; routes: string[]; pins: string[]; when: string; title: string };
export type EventCard = { when: string; title: string; lines: TextLine[] };
export type TimelineAxis = {
  label: string;
  breaks: string[];
  ticks: { left: string; text: string }[];
  spans: { left: string; width: string }[];
  events: { row: number; left: string; short: string }[];
};
export type TimelineMapSpec = {
  head: FigureHead;
  id: string;
  comp: string;
  rest: number;
  events: TimelineEvent[];
  play: string;
  status: string;
  supply: { labelId: string; label: string; description: string };
  views: Record<string, number[]>;
  drawing: DrawingElement;
  legend: { swatch: string[]; label: string }[];
  caption: string;
  cards: EventCard[];
  supplyNote: TextLine[];
  axis: TimelineAxis;
  items: EventCard[];
};
const eventCardShape = object<EventCard>({ when: unitRef, title: unitRef, lines: list(textLineShape, 1) });
export const timelineMapShape = object<TimelineMapSpec>({
  head: figureHeadShape,
  id: domId,
  comp: text,
  rest: integer,
  events: list(object<TimelineEvent>({ view: text, routes: list(text), pins: list(text), when: text, title: text }), 1),
  play: text,
  status: unitRef,
  supply: object<TimelineMapSpec["supply"]>({ labelId: domId, label: text, description: text }),
  views: dictionary(/^[a-z]+$/, list(number, 4)),
  drawing: drawingShape,
  legend: list(object<TimelineMapSpec["legend"][number]>({ swatch: list(className, 1), label: text }), 1),
  caption: unitRef,
  cards: list(eventCardShape, 1),
  supplyNote: list(textLineShape, 1),
  axis: object<TimelineAxis>({
    label: text,
    breaks: list(cssLength),
    ticks: list(object<TimelineAxis["ticks"][number]>({ left: cssLength, text }), 1),
    spans: list(object<TimelineAxis["spans"][number]>({ left: cssLength, width: cssLength })),
    events: list(object<TimelineAxis["events"][number]>({ row: integer, left: cssLength, short: text }), 1)
  }),
  items: list(eventCardShape, 1)
});

export function componentsHeldBy(spec: unknown, labels: ReadonlySet<string>): string[] {
  if (typeof spec === "string") return labels.has(spec) ? [spec] : [];
  if (Array.isArray(spec)) return spec.flatMap((item) => componentsHeldBy(item, labels));
  if (typeof spec === "object" && spec !== null) return Object.values(spec).flatMap((item) => componentsHeldBy(item, labels));
  return [];
}

export function pythonJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(pythonJson).join(", ")}]`;
  if (typeof value === "object" && value !== null) return `{${Object.entries(value).map(([key, item]) => `${pythonJson(key)}: ${pythonJson(item)}`).join(", ")}}`;
  if (typeof value === "string") return JSON.stringify(value).replace(/[\u007f-￿]/g, (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return JSON.stringify(value);
}

export type ConceptRow = { name: string; place: string; family: string; sentences: number; sentence: TextLine };
export type ConceptGroup = { id: string; title: string; text: string; together: string; first: ConceptRow[]; more: ConceptRow[] };
export type ConceptAtlasSpec = { title: string; description: string; groups: ConceptGroup[] };
const conceptRowShape = object<ConceptRow>({ name: text, place: text, family: text, sentences: integer, sentence: textLineShape });
export const conceptAtlasShape = object<ConceptAtlasSpec>({
  title: unitRef,
  description: unitRef,
  groups: list(object<ConceptGroup>({ id: domId, title: unitRef, text: unitRef, together: unitRef, first: list(conceptRowShape, 1), more: list(conceptRowShape) }), 1)
});

export type RelatedCraft = { tile: number; swatch: HeldNode[]; top: string; name: string; place: string; sources: number; monograph: boolean; gi: boolean; shares: HeldNode[]; sentence: string };
export type RelatedCraftsSpec = { title: string; kicker: string; description: string; weave: string; crafts: RelatedCraft[] };
export const relatedCraftsShape = object<RelatedCraftsSpec>({
  title: unitRef,
  kicker: text,
  description: unitRef,
  weave: domId,
  crafts: list(
    object<RelatedCraft>({ tile: integer, swatch: heldTextShape, top: text, name: text, place: text, sources: integer, monograph: boolean, gi: boolean, shares: heldTextShape, sentence: unitRef }),
    1
  )
});

export type ListedSource = { key: string; number: number; title: string; meta: string; grade: "A" | "B" | "C" | "D"; gradeLabel: string; sentences: number; margin: string | null; url: string; linkLabel: string };
export type SourceListing = { id: string; title: string; description: string; openLabel: string; closeLabel: string; sources: ListedSource[] };
export type SourceListSpec = { setting: (typeof SOURCE_LIST_SETTINGS)[number]; statusId: string | null; listing: SourceListing | null };
export const sourceListShape = object<SourceListSpec>({
  setting: oneOf(SOURCE_LIST_SETTINGS),
  statusId: nullable(domId),
  listing: nullable(
    object<SourceListing>({
      id: domId,
      title: unitRef,
      description: unitRef,
      openLabel: text,
      closeLabel: text,
      sources: list(
        object<ListedSource>({
          key: matching(/^g\d+$/, "a source key"),
          number: integer,
          title: text,
          meta: text,
          grade: oneOf(["A", "B", "C", "D"] as const),
          gradeLabel: text,
          sentences: integer,
          margin: nullable(text),
          url: matching(/^https:\/\/\S+$/, "an https link"),
          linkLabel: text
        }),
        1
      )
    })
  )
});

export type Reading = { who: string; unit: string };
export type RangeFigure = { number: FigureNumber; title: string; dek: string; chart: string; source: string };
export type Disagreement = { summary: HeldNode[]; readings: Reading[]; figure: RangeFigure | null };
export type SourceDisagreementsSpec = { id: string; titleId: string; title: string; intro: string; items: Disagreement[] };
export const sourceDisagreementsShape = object<SourceDisagreementsSpec>({
  id: domId,
  titleId: domId,
  title: text,
  intro: unitRef,
  items: list(
    object<Disagreement>({
      summary: heldTextShape,
      readings: list(object<Reading>({ who: text, unit: unitRef }), 2),
      figure: nullable(object<RangeFigure>({ number: figureNumberShape, title: unitRef, dek: unitRef, chart: componentLabel, source: unitRef }))
    }),
    1
  )
});

export type CiteStyle = { value: string; label: string; text: string };
export type CitePanel = {
  key: string;
  tabId: string;
  panelId: string;
  label: string;
  box: string[];
  aid: string;
  cites: string[];
  boxId: string | null;
  styleKey: "style" | "cite-style";
  styles: CiteStyle[];
  textId: string;
  text: string;
  link: string;
  copyLabel: string;
};
export type CitationToolSpec = { title: string; titleId: string; tabsLabel: string; panels: CitePanel[] };
export const citationToolShape = object<CitationToolSpec>({
  title: unitRef,
  titleId: domId,
  tabsLabel: text,
  panels: list(
    object<CitePanel>({
      key: text,
      tabId: domId,
      panelId: domId,
      label: text,
      box: list(className, 1),
      aid: text,
      cites: list(className, 1),
      boxId: nullable(domId),
      styleKey: oneOf(["style", "cite-style"] as const),
      styles: list(object<CiteStyle>({ value: text, label: text, text }), 1),
      textId: domId,
      text: unitRef,
      link: unitRef,
      copyLabel: text
    }),
    1
  )
});
