export function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(new Date(value));
}

const CALENDAR_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

export function formatCalendarDay(day: string): string {
  const parts = CALENDAR_DAY.exec(day);
  if (!parts) throw new RangeError(`not a calendar day: ${day}`);
  const date = new Date(Date.UTC(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3])));
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(date);
}

export function formatDateTime(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function bytes(value: number | string | undefined | null) {
  if (value === undefined || value === null) return "-";
  const size = Number(value);
  if (!Number.isFinite(size)) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function formatClock(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

export function spokenClock(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  const parts = [minutes > 0 ? countNoun(minutes, "minute") : null, rest > 0 || minutes === 0 ? countNoun(rest, "second") : null];
  return parts.filter(Boolean).join(" ");
}

export function byCount(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

export function countNoun(count: number, one: string, many = `${one}s`): string {
  return `${count} ${byCount(count, one, many)}`;
}

export function numberRuns(numbers: readonly number[]): string[] {
  const runs: string[] = [];
  let start = 0;
  numbers.forEach((value, index) => {
    if (numbers[index + 1] === value + 1) return;
    runs.push(index === start ? String(numbers[start]) : `${numbers[start]}–${value}`);
    start = index + 1;
  });
  return runs;
}

export function upperFirst(text: string): string {
  const trimmed = text.trim();
  return trimmed ? `${trimmed[0].toLocaleUpperCase("en-GB")}${trimmed.slice(1)}` : trimmed;
}

export function lowerFirst(text: string): string {
  return text ? `${text[0].toLocaleLowerCase("en-GB")}${text.slice(1)}` : text;
}

export function listText(names: readonly string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export function blankToNull(value: FormDataEntryValue | null) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  return trimmed.length ? trimmed : null;
}

export function numberOrNull(value: FormDataEntryValue | null) {
  const raw = blankToNull(value);
  if (raw === null || raw === undefined || typeof raw !== "string") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export const TITLE_CASE_SMALL_WORDS: ReadonlySet<string> = new Set([
  "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "or",
  "over", "per", "the", "to", "up", "via", "vs", "with"
]);

export const TITLE_CASE_FIELDS: ReadonlySet<string> = new Set([
  "name", "craftName", "artisanName", "productName", "toolkitName", "englishName", "title",
  "place", "placeName", "village", "district", "state"
]);

const APOSTROPHES = "'’";

const LATIN_RANGE = "A-Za-zÀ-ɏ";

const WORD_RE = new RegExp(`[0-9${LATIN_RANGE}${APOSTROPHES}]+`, "gu");
const LATIN_RE = new RegExp(`[${LATIN_RANGE}]`, "u");
const UPPER_RE = /\p{Lu}|\p{Lt}/u;
const LOWER_RE = /\p{Ll}/u;
const DIGIT_RE = /[0-9]/;

const MAX_ACRONYM_LENGTH = 4;

function capitaliseWord(word: string): string {
  if (word.length > 2 && APOSTROPHES.includes(word[1])) {
    return word[0].toUpperCase() + word[1] + word[2].toUpperCase() + word.slice(3);
  }
  return word[0].toUpperCase() + word.slice(1);
}

function caseWord(word: string, isFirst: boolean, isLast: boolean, shouting: boolean): string {
  if (!LATIN_RE.test(word)) return word;
  if (DIGIT_RE.test(word)) return word;
  if (!shouting && UPPER_RE.test(word.slice(1))) return word;
  const lowered = word.toLowerCase();
  if (TITLE_CASE_SMALL_WORDS.has(lowered) && !isFirst && !isLast) return lowered;
  return capitaliseWord(lowered);
}

function isShouting(text: string): boolean {
  if (LOWER_RE.test(text)) return false;
  if (!UPPER_RE.test(text)) return false;
  const words = text.match(WORD_RE) ?? [];
  if (words.length > 1) return true;
  return words.length === 1 && words[0].length > MAX_ACRONYM_LENGTH;
}

export function titleCase(value: string): string {
  const text = value.trim();
  if (!text || !LATIN_RE.test(text)) return text;

  const matches = [...text.matchAll(WORD_RE)];
  if (!matches.length) return text;

  const shouting = isShouting(text);

  let out = "";
  let cursor = 0;
  const lastIndex = matches.length - 1;
  matches.forEach((match, index) => {
    const start = match.index ?? 0;
    out += text.slice(cursor, start);
    out += caseWord(match[0], index === 0, index === lastIndex, shouting);
    cursor = start + match[0].length;
  });
  return out + text.slice(cursor);
}

export function titleCasePreview(value: string | null | undefined): string | null {
  if (!value) return null;
  const normalised = titleCase(value);
  return normalised && normalised !== value ? normalised : null;
}
