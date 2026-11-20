import type { DocumentShape, EssayShape, HubShape, RecordShape } from "./pageShapes";

export const START_PREFIX = "Start the research on ";
export const RECORD_QUESTIONS = 3;
export const ESSAY_ACTIONS = [/^Saved?$/, /^Cite this answer$/] as const;
export const NO_FAMILY_SCIENCE_NOTE = "the hub draws no family science chapters: its family monograph is not served";

const LISTED_MAX = 6;

function listed(items: readonly string[]): string {
  return items.length > LISTED_MAX ? `${items.slice(0, LISTED_MAX).join(", ")} and ${items.length - LISTED_MAX} more` : items.join(", ");
}

function repeatedLabels(labels: readonly string[]): string[] {
  return [...new Set(labels.filter((label, at) => label && labels.indexOf(label) !== at))];
}

export function documentProblems(shape: DocumentShape | null): string[] {
  if (!shape) return ["the page draws no document"];
  const problems: string[] = [];
  if (!shape.heading) problems.push("the document draws no h1");
  if (shape.chapters.length === 0) problems.push("the document draws no chapter");
  const unlabelled = shape.chapters.filter((label) => !label).length;
  if (unlabelled > 0) problems.push(`${unlabelled} of the ${shape.chapters.length} chapters carry no label`);
  const twice = repeatedLabels(shape.chapters);
  if (twice.length > 0) problems.push(`the document draws a chapter twice: ${listed(twice)}`);
  if (shape.railTargets.length === 0) problems.push("the chapter rail lists no chapter");
  if (shape.missingTargets.length > 0) problems.push(`the chapter rail links to chapters the page does not draw: ${listed(shape.missingTargets)}`);
  if (shape.citedSentences === 0) problems.push("the document draws no cited sentence");
  return problems;
}

export function recordProblems(shape: RecordShape | null): string[] {
  if (!shape) return ["the page draws no craft record"];
  const problems: string[] = [];
  if (!shape.heading) problems.push("the craft record draws no h1");
  if (!shape.plate) problems.push("the craft record draws no typographic plate");
  if (shape.facts === 0) problems.push("the craft record shows none of what the craft list records");
  if (shape.start !== `${START_PREFIX}${shape.heading}`) problems.push(`the research invitation reads "${shape.start}"; it should read "${START_PREFIX}${shape.heading}"`);
  if (shape.questions !== RECORD_QUESTIONS) problems.push(`the research invitation offers ${shape.questions} questions; it should offer ${RECORD_QUESTIONS}`);
  if (shape.rail > 0) problems.push("a craft without a monograph draws a chapter rail");
  if (shape.citeThis) problems.push("a craft without a monograph offers Cite this");
  return problems;
}

export function hubProblems(shape: HubShape | null, family: string): { problems: string[]; notes: string[] } {
  if (!shape) return { problems: ["the page draws no category hub"], notes: [] };
  const problems: string[] = [];
  if (shape.heading !== family) problems.push(`the hub is headed "${shape.heading}"; it should be headed ${family}`);
  if (!shape.plate) problems.push("the hub draws no plate ground behind its heading");
  if (shape.shelves === 0) problems.push("the hub draws no shelf of its sub-families");
  if (shape.plates === 0) problems.push("the hub's shelves hold no craft");
  return { problems, notes: shape.chapters === 0 ? [NO_FAMILY_SCIENCE_NOTE] : [`${shape.chapters} family science chapters`] };
}

export function essayProblems(shape: EssayShape | null): string[] {
  if (!shape) return ["the page draws no answer essay"];
  const problems: string[] = [];
  if (!shape.question) problems.push("the answer draws no question as its h1");
  if (shape.lede === 0) problems.push("the answer draws no lede");
  else if (shape.ledeCited < shape.lede) problems.push(`${shape.lede - shape.ledeCited} of the ${shape.lede} lede sentences carry no citation`);
  const missing = ESSAY_ACTIONS.filter((action) => !shape.actions.some((label) => action.test(label)));
  if (missing.length > 0 || shape.actions.length !== ESSAY_ACTIONS.length) problems.push(`the answer's actions are [${shape.actions.join(", ")}]; they should be Save and Cite this answer`);
  return problems;
}
