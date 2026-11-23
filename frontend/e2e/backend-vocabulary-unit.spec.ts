import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { DEPTH_BASES, ENVIRONMENT_FACTORS, EVENT_KINDS, PICTURE_ROLES } from "@/lib/craftPageContext";
import {
  BORROWED_SCOPES,
  COVERAGE_CLASSES,
  CRAFT_GI_STATUSES,
  GI_SHOWN,
  GROUP_KINDS,
  NATIVE_NAME_SOURCES,
  PLACE_KINDS,
  PROVENANCES,
  SECTION_BASES,
  SOURCE_GROUPS,
  SUBJECT_KINDS
} from "@/lib/craftPageContract";
import { SPECIES_ROLES, TIMING_KINDS } from "@/lib/craftPageProcess";
import { PLACE_ROLES } from "@/lib/districtCraftsContract";
import { IMAGE_RELEVANCE, MEDIA_DISPLAYS } from "@/lib/explainerBlockBase";
import { BLOCK_KINDS, BUILT_BLOCK_KINDS, BUILT_FIGURE_KINDS, DEPTHS, DISCIPLINES, FINAL_SECTION_STATES, TERM_BASES, WORKING_SECTION_STATES } from "@/lib/explainerContract";
import { EXPERT_SEATS } from "@/lib/explainerExperts";
import { FIRING_ATMOSPHERES, INDIGO_FORMS, LOST_WAX_STEPS, SIGNATURE_KINDS, VAT_KINDS } from "@/lib/explainerSignature";
import { AMOUNT_KINDS, CONVERSION_BASES, CURRENCIES, GI_STATUSES, METRIC_UNITS, PRICE_SCALES, TREND_VARIABLES } from "@/lib/explainerInsight";
import { SEASONS } from "@/lib/explainerPlace";
import { ZOOM_LEVELS } from "@/lib/explainerPlay";
import { TRAIL_GROUPS, TRAIL_STAGES } from "@/lib/explainerStream";
import { NOTIFICATION_KINDS, SECTION_CHANGES } from "@/lib/learningContract";
import { CITATION_FORMATS, LESSON_FORMATS, SLIDE_KINDS } from "@/lib/lessonContract";
import { COLOUR_SIDES, FORMULA_BASES } from "@/lib/explainerMatter";
import { MEDIA_JOB_STATUSES, MEDIA_KINDS } from "@/lib/mediaContract";
import { UNIT_REF } from "@/lib/unitIds";
import { AGGREGATIONS, ENV_STATS, PLACE_BASES, PLACE_SCOPES, REGION_FACETS } from "@/lib/regionContract";
import { MATERIAL_KINDS, MATERIAL_ROLES, REACTION_KINDS, STAGE_TYPES } from "@/lib/scienceContract";
import { CLIENT_TOOL_NAMES, RELAY_AUDIO_TYPES, VOICE_MODES } from "@/lib/voiceContract";
import { INTERVIEW_TOPICS } from "@/lib/conversationContract";
import { AGE_BANDS, CREDIT_MODES, GENDERS } from "@/lib/profileContract";
import { CONTRIBUTION_STATUSES, LOCATOR_PRECISIONS, TESTIMONY_ENGLISH_SOURCES, TESTIMONY_REJECT_REASONS, TESTIMONY_SCREENS } from "@/lib/testimonyContract";

const BACKEND = join(__dirname, "..", "..", "backend", "app");
const sources = new Map<string, string>();

function backendTuple(file: string, name: string): string[] {
  const text = sources.get(file) ?? readFileSync(join(BACKEND, ...file.split("/")), "utf8");
  sources.set(file, text);
  const found = new RegExp(`^${name} = \\(([^)]*)\\)`, "m").exec(text);
  if (!found) throw new Error(`${name} is not a tuple in backend/app/${file}`);
  return [...found[1].matchAll(/"([^"]+)"/g)].map((value) => value[1]);
}

const PAIRS: [string, string, readonly string[]][] = [
  ["models/enums.py", "STAGE_TYPES", STAGE_TYPES],
  ["models/enums.py", "MATERIAL_KINDS", MATERIAL_KINDS],
  ["models/enums.py", "MATERIAL_ROLES", MATERIAL_ROLES],
  ["models/enums.py", "REACTION_KINDS", REACTION_KINDS],
  ["models/enums.py", "ENV_STATS", ENV_STATS],
  ["models/enums.py", "MEDIA_KINDS", MEDIA_KINDS],
  ["schemas/region.py", "REGION_FACETS", REGION_FACETS],
  ["schemas/region.py", "AGGREGATIONS", AGGREGATIONS],
  ["schemas/region.py", "PLACE_SCOPES", PLACE_SCOPES],
  ["schemas/region.py", "PLACE_BASES", PLACE_BASES],
  ["schemas/voice.py", "VOICE_MODES", VOICE_MODES],
  ["schemas/voice.py", "RELAY_AUDIO_TYPES", RELAY_AUDIO_TYPES],
  ["schemas/voice.py", "CLIENT_TOOL_NAMES", CLIENT_TOOL_NAMES],
  ["schemas/media.py", "MEDIA_JOB_STATUSES", MEDIA_JOB_STATUSES],
  ["models/enums.py", "EXPLAINER_DEPTHS", DEPTHS],
  ["models/enums.py", "DISCIPLINES", DISCIPLINES],
  ["models/block_kinds.py", "BLOCK_KINDS", BLOCK_KINDS],
  ["research/explainer.py", "BUILT_BLOCK_KINDS", BUILT_BLOCK_KINDS],
  ["research/explainer.py", "BUILT_FIGURE_KINDS", BUILT_FIGURE_KINDS],
  ["research/explainer.py", "WORKING_SECTION_STATES", WORKING_SECTION_STATES],
  ["research/explainer.py", "FINAL_SECTION_STATES", FINAL_SECTION_STATES],
  ["research/trail.py", "TRAIL_STAGES", TRAIL_STAGES],
  ["research/trail.py", "TRAIL_GROUPS", TRAIL_GROUPS],
  ["research/blocks_signature.py", "SIGNATURE_KINDS", SIGNATURE_KINDS],
  ["research/blocks_signature.py", "VAT_KINDS", VAT_KINDS],
  ["research/blocks_signature.py", "INDIGO_FORMS", INDIGO_FORMS],
  ["research/blocks_signature.py", "LOST_WAX_STEPS", LOST_WAX_STEPS],
  ["research/blocks_signature.py", "FIRING_ATMOSPHERES", FIRING_ATMOSPHERES],
  ["models/enums.py", "MEDIA_DISPLAYS", MEDIA_DISPLAYS],
  ["models/enums.py", "IMAGE_RELEVANCE", IMAGE_RELEVANCE],
  ["models/enums.py", "TERM_BASES", TERM_BASES],
  ["research/blocks_people.py", "EXPERT_SEATS", EXPERT_SEATS],
  ["research/calendar_words.py", "SEASONS", SEASONS],
  ["research/blocks_journey.py", "ZOOM_LEVELS", ZOOM_LEVELS],
  ["models/enums.py", "NOTIFICATION_KINDS", NOTIFICATION_KINDS],
  ["models/enums.py", "PLACE_ROLES", PLACE_ROLES],
  ["research/measures.py", "METRIC_UNITS", METRIC_UNITS],
  ["research/measures.py", "CONVERSION_BASES", CONVERSION_BASES],
  ["research/blocks_insight.py", "GI_STATUSES", GI_STATUSES],
  ["research/blocks_insight.py", "CURRENCIES", CURRENCIES],
  ["research/blocks_insight.py", "PRICE_SCALES", PRICE_SCALES],
  ["research/stated_amounts.py", "AMOUNT_KINDS", AMOUNT_KINDS],
  ["research/blocks_climate.py", "TREND_VARIABLES", TREND_VARIABLES],
  ["research/explainer_versions.py", "SECTION_CHANGES", SECTION_CHANGES],
  ["research/lessons.py", "SLIDE_KINDS", SLIDE_KINDS],
  ["research/lessons.py", "LESSON_FORMATS", LESSON_FORMATS],
  ["research/citation_export.py", "CITATION_FORMATS", CITATION_FORMATS],
  ["research/craft_page.py", "PROVENANCES", PROVENANCES],
  ["research/craft_page.py", "SECTION_BASES", SECTION_BASES],
  ["research/craft_page.py", "SUBJECT_KINDS", SUBJECT_KINDS],
  ["research/craft_page_process.py", "TIMING_KINDS", TIMING_KINDS],
  ["research/craft_page_context.py", "DEPTH_BASES", DEPTH_BASES],
  ["research/craft_page_context.py", "EVENT_KINDS", EVENT_KINDS],
  ["research/craft_page_context.py", "PICTURE_ROLES", PICTURE_ROLES],
  ["research/craft_chapters.py", "BORROWED_SCOPES", BORROWED_SCOPES],
  ["research/craft_parts.py", "SOURCE_GROUPS", SOURCE_GROUPS],
  ["research/craft_masthead.py", "GI_SHOWN", GI_SHOWN],
  ["research/craft_masthead.py", "NATIVE_NAME_SOURCES", NATIVE_NAME_SOURCES],
  ["research/blocks_matter.py", "FORMULA_BASES", FORMULA_BASES],
  ["research/colours.py", "COLOUR_SIDES", COLOUR_SIDES],
  ["models/enums.py", "ENVIRONMENT_FACTORS", ENVIRONMENT_FACTORS],
  ["research/reactions.py", "SPECIES_ROLES", SPECIES_ROLES],
  ["models/enums.py", "GI_STATUSES", CRAFT_GI_STATUSES],
  ["models/enums.py", "COVERAGE_CLASSES", COVERAGE_CLASSES],
  ["curation/vocabulary.py", "PLACE_KINDS", PLACE_KINDS],
  ["curation/vocabulary.py", "GROUP_KINDS", GROUP_KINDS],
  ["models/people_vocabulary.py", "AGE_BANDS", AGE_BANDS],
  ["models/people_vocabulary.py", "GENDERS", GENDERS],
  ["models/people_vocabulary.py", "CREDIT_MODES", CREDIT_MODES],
  ["models/people_vocabulary.py", "INTERVIEW_TOPICS", INTERVIEW_TOPICS],
  ["models/people_vocabulary.py", "CONTRIBUTION_STATUSES", CONTRIBUTION_STATUSES],
  ["models/people_vocabulary.py", "TESTIMONY_ENGLISH_SOURCES", TESTIMONY_ENGLISH_SOURCES],
  ["models/people_vocabulary.py", "TESTIMONY_REJECT_REASONS", TESTIMONY_REJECT_REASONS],
  ["models/people_vocabulary.py", "TESTIMONY_SCREENS", TESTIMONY_SCREENS],
  ["models/people_vocabulary.py", "LOCATOR_PRECISIONS", LOCATOR_PRECISIONS]
];

for (const [file, name, client] of PAIRS) {
  test(`${name} matches backend/app/${file} value for value, in order`, () => {
    expect([...client]).toEqual(backendTuple(file, name));
  });
}

test("a name the backend file does not define fails instead of matching nothing", () => {
  expect(() => backendTuple("models/enums.py", "NOT_A_TUPLE")).toThrow("NOT_A_TUPLE is not a tuple");
});

test("the client reads a spec's unit refs by the backend's one unit id pattern", () => {
  const source = readFileSync(join(__dirname, "..", "..", "backend", "app", "research", "unit_ids.py"), "utf8");
  const pattern = /^UNIT_REF_PATTERN = r"([^"]+)"$/m.exec(source)?.[1];
  expect(UNIT_REF.source).toBe(pattern);
  expect(["u0001", "u5001", "u9001", "u10001", "chemistry-ab12"].map((unit) => UNIT_REF.test(unit))).toEqual([true, true, true, false, false]);
});
