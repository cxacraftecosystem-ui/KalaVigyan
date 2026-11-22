import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import {
  busiestPoint,
  parseMcpActivity,
  scopeChosen,
  scopeFromParams,
  scopeHref,
  scopeValue,
  totals,
  type McpActivity
} from "@/lib/mcpActivityContract";
import { activityStats, pointLabel, scopeOptions, scopedLastCall, seriesTitle } from "@/lib/mcpActivityView";
import { canAccessRoute, ROUTE_GUARDS } from "@/lib/permissions";
import { ShapeError } from "@/lib/shape";
import type { User } from "@/lib/types";

const SHARED = join(__dirname, "..", "..", "shared");
const SECOND = "8f3e2c1a-0000-4000-8000-000000000002";

const golden = (): McpActivity => JSON.parse(readFileSync(join(SHARED, "mcp.activity.golden.json"), "utf8")) as McpActivity;
const person = (role: User["role"]): User => ({ id: role, email: `${role}@example.org`, name: role, role, capabilities: [] }) as User;

test("the MCP activity parses exactly as the backend writes it", () => {
  expect(parseMcpActivity(golden())).toEqual(golden());
});

test("an MCP activity off its contract is refused", () => {
  expect(() => parseMcpActivity({ ...golden(), schemaVersion: 2 })).toThrow(ShapeError);
  expect(() => parseMcpActivity({ ...golden(), days: 14 })).toThrow(ShapeError);
  expect(() => parseMcpActivity({ ...golden(), arguments: {} })).toThrow(ShapeError);
  const answered = { ...golden().failures[0], outcome: "OK" };
  expect(() => parseMcpActivity({ ...golden(), failures: [answered] })).toThrow(ShapeError);
});

test("the figure's title names the busiest day and the stats add up the period", () => {
  const activity = golden();
  expect(busiestPoint(activity.series)?.start).toBe("2026-11-18");
  expect(seriesTitle(activity)).toBe("The busiest day was 18 Nov 2026, with 13 calls");
  expect(totals(activity.series)).toEqual({ ok: 32, toolErrors: 3, protocolErrors: 1 });
  const [calls, failed] = activityStats(activity);
  expect([calls.value, failed.value, failed.note]).toEqual(["36", "4", "3 tool errors, 1 protocol error"]);
  expect(scopedLastCall(activity)).toBe("2026-11-22T09:15:00Z");
  expect(scopedLastCall({ ...activity, connection: SECOND })).toBe("2026-11-20T14:02:00Z");
  expect(pointLabel(activity.series[2], "week")).toBe("Week of 18 Nov 2026");
});

test("a period with no calls draws no figure title", () => {
  const quiet = { ...golden(), series: golden().series.map((point) => ({ ...point, ok: 0, toolErrors: 0, protocolErrors: 0 })) };
  expect(seriesTitle(quiet)).toBeNull();
});

test("the screen's period and scope live in its address, one scope at a time", () => {
  const asked = scopeFromParams(new URLSearchParams(`days=180&client=Claude&connection=${SECOND}`));
  expect(asked).toEqual({ days: 180, client: null, connection: SECOND });
  expect(scopeFromParams(new URLSearchParams("days=14"))).toEqual({ days: 30, client: null, connection: null });
  expect(scopeHref({ days: 30, client: "Claude", connection: null })).toBe("/admin/mcp?client=Claude");
  expect(scopeHref({ days: 7, client: null, connection: null })).toBe("/admin/mcp?days=7");
  expect(scopeChosen(scopeValue(asked), 7)).toEqual({ days: 7, client: null, connection: SECOND });
  expect(scopeChosen("all", 30)).toEqual({ days: 30, client: null, connection: null });
});

test("the scope choice lists every client and every connection in its group", () => {
  const options = scopeOptions(golden());
  expect(options.map((option) => [option.label, option.group ?? null])).toEqual([
    ["Every client", null],
    ["Claude", "Clients"],
    ["ChatGPT", "Clients"],
    ["Claude for Ravi Shah", "Connections"],
    ["ChatGPT for Meera Iyer", "Connections"],
    ["Claude for Ravi Shah", "Connections"]
  ]);
  expect(options[1].hint).toBe("2 connections");
});

test("only a master admin opens the MCP activity, as the API's own guard requires", () => {
  const gates = Object.fromEntries(ROUTE_GUARDS.map((guard) => [guard.path, guard.gate]));
  expect(gates["/admin/mcp"]).toBe("require_master_admin");
  expect(canAccessRoute(person("MASTER_ADMIN"), "/admin/mcp")).toBe(true);
  expect(canAccessRoute(person("ADMIN"), "/admin/mcp")).toBe(false);
});
