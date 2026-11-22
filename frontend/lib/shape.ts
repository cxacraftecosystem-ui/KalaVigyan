export class ShapeError extends Error {
  constructor(readonly path: string, readonly expected: string) {
    super(`${path || "value"}: expected ${expected}`);
    this.name = "ShapeError";
  }
}

export type Shape<T> = {
  readonly expected: string;
  parse(value: unknown, path: string): T;
};

type Fields<T> = { [K in keyof Required<T>]: Shape<T[K]> };

function shape<T>(expected: string, check: (value: unknown) => value is T): Shape<T> {
  return {
    expected,
    parse(value, path) {
      if (!check(value)) throw new ShapeError(path, expected);
      return value;
    }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const text = shape("text", (value): value is string => typeof value === "string");
export const number = shape("a number", (value): value is number => typeof value === "number" && Number.isFinite(value));
export const integer = shape("an integer", (value): value is number => Number.isInteger(value));
export const boolean = shape("true or false", (value): value is boolean => typeof value === "boolean");

export function ruled<T>(inner: Shape<T>, expected: string, rule: (value: T) => boolean): Shape<T> {
  return {
    expected: inner.expected,
    parse(value, path) {
      const parsed = inner.parse(value, path);
      if (!rule(parsed)) throw new ShapeError(path, expected);
      return parsed;
    }
  };
}

function wholeFrom(least: number): Shape<number> {
  const expected = `a whole number from ${least}`;
  return {
    expected,
    parse(value, path) {
      const whole = integer.parse(value, path);
      if (whole < least) throw new ShapeError(path, expected);
      return whole;
    }
  };
}

export const count = wholeFrom(0);
export const positive = wholeFrom(1);

export function oneOf<const T extends readonly (string | number)[]>(values: T): Shape<T[number]> {
  return shape(`one of ${values.join(", ")}`, (value): value is T[number] => values.includes(value as T[number]));
}

export function matching(pattern: RegExp, expected: string): Shape<string> {
  return shape(expected, (value): value is string => typeof value === "string" && pattern.test(value));
}

export function nullable<T>(inner: Shape<T>): Shape<T | null> {
  return {
    expected: `${inner.expected} or null`,
    parse: (value, path) => (value === null ? null : inner.parse(value, path))
  };
}

export function optional<T>(inner: Shape<T>): Shape<T | undefined> {
  return {
    expected: `${inner.expected} when present`,
    parse: (value, path) => (value === undefined ? undefined : inner.parse(value, path))
  };
}

export function list<T>(item: Shape<T>, min = 0): Shape<T[]> {
  return {
    expected: `a list of ${item.expected}`,
    parse(value, path) {
      if (!Array.isArray(value) || value.length < min) throw new ShapeError(path, `at least ${min} of ${item.expected}`);
      return value.map((entry, index) => item.parse(entry, `${path}[${index}]`));
    }
  };
}

export function dictionary<T>(key: RegExp, item: Shape<T>): Shape<Record<string, T>> {
  return {
    expected: `a map of ${item.expected}`,
    parse(value, path) {
      if (!isRecord(value)) throw new ShapeError(path, "an object");
      const out: Record<string, T> = {};
      for (const [name, entry] of Object.entries(value)) {
        if (!key.test(name)) throw new ShapeError(`${path}.${name}`, `a key matching ${key}`);
        out[name] = item.parse(entry, `${path}.${name}`);
      }
      return out;
    }
  };
}

export function object<T extends object>(fields: Fields<T>): Shape<T> {
  const known = Object.keys(fields);
  return {
    expected: `an object with ${known.join(", ")}`,
    parse(value, path) {
      if (!isRecord(value)) throw new ShapeError(path, "an object");
      const unknown = Object.keys(value).filter((name) => !known.includes(name));
      if (unknown.length) throw new ShapeError(`${path}.${unknown[0]}`, "no such field");
      const out: Record<string, unknown> = {};
      for (const name of known) {
        const field = (fields as Record<string, Shape<unknown>>)[name];
        const parsed = field.parse(value[name], path ? `${path}.${name}` : name);
        if (parsed !== undefined) out[name] = parsed;
      }
      return out as T;
    }
  };
}

export function tagged<T>(tag: string, variants: Record<string, Shape<T>>): Shape<T> {
  return {
    expected: `one of the ${tag} variants ${Object.keys(variants).join(", ")}`,
    parse(value, path) {
      const name = isRecord(value) ? value[tag] : undefined;
      const variant = typeof name === "string" ? variants[name] : undefined;
      if (!variant) throw new ShapeError(path ? `${path}.${tag}` : tag, `one of ${Object.keys(variants).join(", ")}`);
      return variant.parse(value, path);
    }
  };
}

export function parseShape<T>(target: Shape<T>, value: unknown): T {
  return target.parse(value, "");
}
