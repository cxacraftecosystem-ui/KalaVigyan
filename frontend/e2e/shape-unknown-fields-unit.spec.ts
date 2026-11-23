import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { craftPageShape } from "@/lib/craftPageContract";
import { BUILD_UNKNOWN_FIELDS, list, nullable, number, object, oneOf, parseShape, ShapeError, tagged, text, unknownFieldsIn, type Shape } from "@/lib/shape";

import { UNKNOWN_FIELD, UNKNOWN_VALUE, withUnknownFields } from "./unknownFields";

type Source = { title: string; year: number | null };
type Cited = { id: string; source: Source; tags: { name: string }[] };

const sourceShape = object<Source>({ title: text, year: nullable(number) });
const citedShape = object<Cited>({ id: text, source: sourceShape, tags: list(object<{ name: string }>({ name: text })) });
const CITED: Cited = { id: "c1", source: { title: "Block printing of Akola", year: 2019 }, tags: [{ name: "dye" }, { name: "mordant" }] };
const LATER: unknown = {
  id: "c1",
  issue: "3",
  source: { title: "Block printing of Akola", year: 2019, containerTitle: "Journal of textile history" },
  tags: [{ name: "dye", weight: 1 }, { name: "mordant" }]
};

function golden(name: string): unknown {
  return JSON.parse(readFileSync(join(__dirname, "..", "..", "shared", name), "utf8"));
}

test("the unit specs parse as strictly as every build but production's", () => {
  expect(BUILD_UNKNOWN_FIELDS).toBe("refuse");
  expect(unknownFieldsIn("production")).toBe("ignore");
  expect(unknownFieldsIn("development")).toBe("refuse");
  expect(unknownFieldsIn("test")).toBe("refuse");
  expect(unknownFieldsIn(undefined)).toBe("refuse");
});

test("a strict parse names the first field it does not know", () => {
  expect(() => parseShape(citedShape, LATER)).toThrow(new ShapeError(".issue", "no such field"));
  expect(() => parseShape(citedShape, LATER, "refuse")).toThrow(ShapeError);
});

test("a production parse drops the fields it does not know at every depth and keeps every known field", () => {
  expect(parseShape(citedShape, LATER, "ignore")).toEqual(CITED);
});

test("a production parse still refuses a known field of the wrong kind, a missing field and a value outside its vocabulary", () => {
  expect(() => parseShape(citedShape, { ...CITED, extra: 1, id: 7 }, "ignore")).toThrow(new ShapeError("id", "text"));
  expect(() => parseShape(citedShape, { id: "c1", tags: [] }, "ignore")).toThrow(new ShapeError("source", "an object"));
  expect(() => parseShape(oneOf(["A", "B"] as const), "C", "ignore")).toThrow(ShapeError);
  const kinds = tagged<{ kind: string }>("kind", { plate: object<{ kind: string }>({ kind: text }) });
  expect(() => parseShape(kinds, { kind: "film", extra: 1 }, "ignore")).toThrow(new ShapeError("kind", "one of plate"));
});

test("a parse inside a parse keeps the outer policy, and the policy returns when the parse ends or throws", () => {
  const inner: Shape<Source> = { expected: "a source", parse: (value) => parseShape(sourceShape, value) };
  const outer = object<{ source: Source }>({ source: inner });
  const later = { source: { title: "Block printing of Akola", year: null, containerTitle: "Journal of textile history" } };
  expect(parseShape(outer, later, "ignore")).toEqual({ source: { title: "Block printing of Akola", year: null } });
  expect(() => parseShape(outer, later)).toThrow(/containerTitle: expected no such field/);
  expect(() => parseShape(citedShape, { ...CITED, id: 7 }, "ignore")).toThrow(ShapeError);
  expect(() => parseShape(citedShape, LATER)).toThrow(/issue: expected no such field/);
});

test("both craft page goldens with a field added to every object parse in production as the goldens themselves", () => {
  for (const name of ["craft.page.golden.json", "craft.page.register.golden.json"]) {
    const later = withUnknownFields(golden(name));
    expect(JSON.stringify(later)).toContain(`"${UNKNOWN_FIELD}":"${UNKNOWN_VALUE}"`);
    expect(() => parseShape(craftPageShape, later)).toThrow(new ShapeError(`.${UNKNOWN_FIELD}`, "no such field"));
    expect(parseShape(craftPageShape, later, "ignore")).toEqual(parseShape(craftPageShape, golden(name)));
  }
});
