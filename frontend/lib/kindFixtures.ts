import chart from "@/lib/kindFixtures/chart.json";
import choiceToggle from "@/lib/kindFixtures/choice_toggle.json";
import choiceToggleCopper from "@/lib/kindFixtures/choice_toggle_copper.json";
import diagram from "@/lib/kindFixtures/diagram.json";
import dipPlayer from "@/lib/kindFixtures/dip_player.json";
import drawing from "@/lib/kindFixtures/drawing.json";
import equationCard from "@/lib/kindFixtures/equation_card.json";
import experimentLab from "@/lib/kindFixtures/experiment_lab.json";
import factTable from "@/lib/kindFixtures/fact_table.json";
import labelCard from "@/lib/kindFixtures/label_card.json";
import mapLayer from "@/lib/kindFixtures/map_layer.json";
import mapSequence from "@/lib/kindFixtures/map_sequence.json";
import mapSequenceDhokra from "@/lib/kindFixtures/map_sequence_dhokra.json";
import materialCards from "@/lib/kindFixtures/material_cards.json";
import molecule3d from "@/lib/kindFixtures/molecule_3d.json";
import reactionPlayer from "@/lib/kindFixtures/reaction_player.json";
import sourceDisagreements from "@/lib/kindFixtures/source_disagreements.json";
import stagePlayer from "@/lib/kindFixtures/stage_player.json";
import statTiles from "@/lib/kindFixtures/stat_tiles.json";
import structureDiagram from "@/lib/kindFixtures/structure_diagram.json";
import swatchCards from "@/lib/kindFixtures/swatch_cards.json";
import swatchPair from "@/lib/kindFixtures/swatch_pair.json";
import timeline from "@/lib/kindFixtures/timeline.json";
import voice from "@/lib/kindFixtures/voice.json";
import { dictionary, integer, list, matching, nullable, object, oneOf, parseShape, ShapeError, text, type Shape } from "@/lib/shape";
import { UNIT_REF } from "@/lib/unitIds";

export type FixtureUnit = { text: string; claims: string[] };
export type FixtureQuote = { source: string; locator: string; quote: string };
export type FixtureFact = { text: string; quotes: FixtureQuote[] };
export type FixtureSource = { title: string; publisher: string | null; year: number | null; url: string | null; reliability: string | null };
export type KindFixture = {
  schemaVersion: 1;
  kind: string;
  craft: string;
  craftName: string;
  label: string;
  title: string;
  description: string;
  field: string;
  within: string | null;
  spec: Record<string, unknown>;
  units: Record<string, FixtureUnit>;
  facts: Record<string, FixtureFact>;
  sources: Record<string, FixtureSource>;
};

const ANY_KEY = /^[\w-]+$/;
const record: Shape<Record<string, unknown>> = {
  expected: "an object",
  parse(value, path) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ShapeError(path, "an object");
    return value as Record<string, unknown>;
  }
};

const fixtureShape: Shape<KindFixture> = object<KindFixture>({
  schemaVersion: oneOf([1] as const),
  kind: text,
  craft: text,
  craftName: text,
  label: matching(/^[a-z0-9]+(-[a-z0-9]+)*(\/[a-z0-9]+(-[a-z0-9]+)*){2,}$/, "a component label"),
  title: text,
  description: text,
  field: text,
  within: nullable(text),
  spec: record,
  units: dictionary(UNIT_REF, object<FixtureUnit>({ text, claims: list(text) })),
  facts: dictionary(ANY_KEY, object<FixtureFact>({ text, quotes: list(object<FixtureQuote>({ source: text, locator: text, quote: text }), 1) })),
  sources: dictionary(ANY_KEY, object<FixtureSource>({ title: text, publisher: nullable(text), year: nullable(integer), url: nullable(text), reliability: nullable(text) }))
});

const RAW: readonly unknown[] = [
  drawing,
  chart,
  factTable,
  timeline,
  mapLayer,
  statTiles,
  mapSequence,
  mapSequenceDhokra,
  sourceDisagreements,
  labelCard,
  swatchCards,
  swatchPair,
  voice,
  stagePlayer,
  dipPlayer,
  reactionPlayer,
  diagram,
  equationCard,
  structureDiagram,
  molecule3d,
  materialCards,
  experimentLab,
  choiceToggle,
  choiceToggleCopper
];

export const KIND_FIXTURES: readonly KindFixture[] = RAW.map((fixture) => parseShape(fixtureShape, fixture));
