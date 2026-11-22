import { expect, test } from "@playwright/test";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { EmptyState } from "@/components/EmptyState";
import { Field, TextInput } from "@/components/FormControls";
import { Button, buttonLook } from "@/components/ui/button";
import { Chip, type ChipProps } from "@/components/ui/Chip";
import { Figure, type FigureProps } from "@/components/ui/Figure";
import { IconButton } from "@/components/ui/IconButton";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { Skeleton } from "@/components/ui/Skeleton";
import { nextTabIndex } from "@/components/ui/Tabs";
import { TOAST_DURATION, ToastCard } from "@/components/ui/Toast";
import { Toggle } from "@/components/ui/Toggle";
import { clampZoom, zoomBy, ZOOM_RESET } from "@/components/ui/useZoom";
import { figureKicker } from "@/lib/editorialText";

import { attribute } from "./explainerRender";
import { primitivesPage } from "./primitivesPage";

type FieldProps = Parameters<typeof Field>[0];

const html = (element: ReactElement) => renderToStaticMarkup(element);
const words = (markup: string) => markup.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const GAP_WORDS = /not built yet|coming soon|no data|not enough cited evidence|\b0 results|nothing here yet|beta|ai-generated/i;

test("every button look maps to one of the five, the old names included", () => {
  expect(buttonLook({ variant: "default" })["data-variant"]).toBe("primary");
  expect(buttonLook({ variant: "outline" })["data-variant"]).toBe("quiet");
  expect(buttonLook({ variant: "ghost" })["data-variant"]).toBe("quiet");
  expect(buttonLook({ variant: "provider" })["data-variant"]).toBe("quiet");
  expect(buttonLook({ variant: "destructive" })["data-variant"]).toBe("destroy");
  expect(buttonLook({ variant: "link" })["data-variant"]).toBe("text");
  expect(buttonLook({ size: "sm" })).toMatchObject({ "data-size": "sm" });
  expect(buttonLook({ size: "auth" })).not.toHaveProperty("data-size");
  const busy = html(createElement(Button, { variant: "primary", busy: true, busyLabel: "Sending" }, "Request access"));
  expect(busy).toContain('aria-busy="true"');
  expect(words(busy)).toBe("Request access Sending");
});

test("a busy button keeps its resting width, primary is the indigo fill and disabled sinks into the paper", async ({ page }) => {
  const row = [
    html(createElement(Button, { variant: "primary", id: "rest" }, "Request access")),
    html(createElement(Button, { variant: "primary", id: "busy", busy: true, busyLabel: "Sending" }, "Request access")),
    html(createElement(Button, { variant: "primary", id: "off", disabled: true }, "Request access")),
    html(createElement(Button, { variant: "danger", id: "danger" }, "Remove key")),
    html(createElement(Button, { variant: "destroy", id: "destroy" }, "Delete lesson")),
    html(createElement(IconButton, { label: "Close", icon: createElement("svg"), id: "icon" }))
  ].join("");
  await page.setContent(primitivesPage(`<div style="display:flex;gap:8px;align-items:start">${row}</div>`));
  const look = (id: string) => page.locator(`#${id}`).evaluate((node) => ({ width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height, background: getComputedStyle(node).backgroundColor, colour: getComputedStyle(node).color }));
  const [rest, busy, off, danger, destroy, icon] = await Promise.all(["rest", "busy", "off", "danger", "destroy", "icon"].map(look));
  expect(busy.width).toBe(rest.width);
  expect(rest).toMatchObject({ background: "rgb(36, 59, 156)", colour: "rgb(251, 251, 249)", height: 46 });
  expect(off).toMatchObject({ background: "rgb(232, 234, 228)", colour: "rgb(89, 83, 78)" });
  expect(danger.colour).toBe("rgb(158, 46, 39)");
  expect(destroy).toMatchObject({ background: "rgb(158, 46, 39)", colour: "rgb(251, 251, 249)" });
  expect(icon).toMatchObject({ width: 44, height: 44 });
  await page.setContent(primitivesPage(row, 'data-theme="dark"'));
  expect(await look("rest")).toMatchObject({ background: "rgb(169, 188, 243)", colour: "rgb(14, 18, 28)" });
});

test("a chosen chip, segment and switch take indigo, and say so to assistive technology", async ({ page }) => {
  const chip = html(createElement(Chip, { pressed: true, count: 7 } as ChipProps, "madder"));
  const segments = html(createElement(SegmentedChoice, { label: "Answer depth", value: "standard", onChange: () => undefined, options: [{ value: "short", label: "Short" }, { value: "standard", label: "Standard" }, { value: "expert", label: "Expert", disabled: true, reason: "Choose a craft first" }] }));
  const on = html(createElement(Toggle, { label: "Larger text", checked: true }));
  const busy = html(createElement(Toggle, { label: "Weekly digest", checked: true, busy: true, busyLabel: "Saving" }));
  expect(chip).toContain('aria-pressed="true"');
  expect(words(chip)).toBe("madder 7");
  expect(segments.match(/aria-pressed="true"/g)).toHaveLength(1);
  expect(segments).toContain('title="Choose a craft first"');
  expect(on).toContain('role="switch" aria-checked="true"');
  expect(busy).toContain('aria-busy="true"');
  expect(words(busy)).toContain("Saving");
  await page.setContent(primitivesPage(`${chip}${segments}${on}`));
  const fill = (selector: string) => page.locator(selector).evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(await fill(".kv-chip")).toBe("rgb(223, 230, 246)");
  expect(await fill('.kv-seg > [aria-pressed="true"]')).toBe("rgb(36, 59, 156)");
  expect(await fill('.kv-seg > [aria-pressed="false"]:not(:disabled)')).toBe("rgba(0, 0, 0, 0)");
  expect(await fill('.kv-seg > :disabled')).toBe("rgb(232, 234, 228)");
  expect(await fill('[role="switch"]')).toBe("rgb(36, 59, 156)");
});

test("focus is indigo at 3px, inset inside segments and tabs, and photo ink over a dark ring on a photograph", async ({ page }) => {
  const segments = html(createElement(SegmentedChoice, { label: "Theme", value: "dark", onChange: () => undefined, options: [{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }] }));
  const tabs = '<div class="kv-tabs" role="tablist"><button type="button" role="tab" aria-selected="true" id="tab">Profile</button></div>';
  const photo = html(createElement(Button, { variant: "quiet", onPhoto: true, id: "photo" }, "Sign in"));
  const plain = html(createElement(Button, { variant: "quiet", id: "plain" }, "Save"));
  await page.setContent(primitivesPage(`${plain}${segments}${tabs}<div style="background:black;padding:8px">${photo}</div>`));
  const ring = async (selector: string) => {
    await page.locator(selector).first().focus();
    return page.locator(selector).first().evaluate((node) => ({ visible: node.matches(":focus-visible"), offset: getComputedStyle(node).outlineOffset, colour: getComputedStyle(node).outlineColor, width: getComputedStyle(node).outlineWidth, halo: getComputedStyle(node).boxShadow }));
  };
  expect(await ring("#plain")).toMatchObject({ visible: true, offset: "3px", colour: "rgb(36, 59, 156)", width: "2px" });
  expect(await ring(".kv-seg > button")).toMatchObject({ visible: true, offset: "-4px", colour: "rgb(36, 59, 156)" });
  expect(await ring('.kv-seg > [aria-pressed="true"]')).toMatchObject({ offset: "-4px" });
  expect(await ring("#tab")).toMatchObject({ visible: true, offset: "-3px" });
  const onPhoto = await ring("#photo");
  expect(onPhoto).toMatchObject({ visible: true, offset: "2px", colour: "rgb(251, 250, 246)", width: "2px" });
  expect(onPhoto.halo).toContain("rgba(8, 10, 16, 0.8)");
});

test("a field with an error says so in words with an icon, marks the input invalid and points to the message", () => {
  const markup = html(createElement(Field, { label: "Email", error: "Enter an email address with a domain.", hint: "Your institution email.", required: true } as FieldProps, createElement(TextInput, { defaultValue: "ananya@" })));
  const describedBy = attribute(markup.replace("<input", '<input data-testid="email"'), "email", "aria-describedby")[0].split(" ");
  expect(markup).toContain('aria-invalid="true"');
  expect(describedBy).toHaveLength(2);
  for (const id of describedBy) expect(markup).toContain(`id="${id}"`);
  expect(words(markup)).toContain("Email (required)");
  expect(markup).toContain("lucide-circle-alert");
  expect(html(createElement(Field, { label: "Name" } as FieldProps, createElement(TextInput, {})))).not.toContain("aria-invalid");
});

test("toasts carry an icon and words; errors stay and interrupt, warnings stay longer than news", () => {
  expect(TOAST_DURATION).toEqual({ info: 5000, success: 5000, warning: 8000, error: 0 });
  const error = html(createElement(ToastCard, { toast: { id: "e", tone: "error", title: "The answer could not be saved", duration: 0 }, onDismiss: () => undefined }));
  const info = html(createElement(ToastCard, { toast: { id: "i", tone: "info", title: "Citation copied", duration: 5000 }, onDismiss: () => undefined }));
  expect(error).toContain('role="alert"');
  expect(error).toContain("<svg");
  expect(info).not.toContain('role="alert"');
  expect(info).toContain('aria-label="Dismiss: Citation copied"');
});

test("an empty place says what it is for and offers one way forward, and never admits a gap", () => {
  const markup = html(createElement(EmptyState, { title: "Your saved list", body: "Save a craft or an answer and it waits here for you.", actions: createElement(Button, { variant: "quiet" }, "Browse the atlas") }));
  expect(markup).toContain("<h2");
  expect(markup.match(/<button/g)).toHaveLength(1);
  expect(markup).not.toMatch(GAP_WORDS);
  expect(markup).not.toContain("<svg");
});

test("a skeleton is shaped like what is coming, busy for assistive technology and never just Loading", () => {
  for (const shape of ["masthead", "lede", "plateGrid", "chart"] as const) {
    const markup = html(createElement(Skeleton, { shape, label: "Opening the monograph" }));
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('data-skeleton="' + shape + '"');
    expect(words(markup)).toBe("Opening the monograph");
    expect(markup.match(/kv-sk /g)?.length ?? 0).toBeGreaterThan(2);
  }
});

test("figures and tables are numbered separately through a page, kicker first and the table behind All N values", () => {
  expect(figureKicker("figure", 3)).toBe("Fig. 3");
  expect(figureKicker("table", 1)).toBe("Table 1");
  const props: Omit<FigureProps, "children"> = { number: 5, title: "Rain over Kachchh has risen", source: "CHIRPS 3.0", table: createElement("table"), valueCount: 45 };
  const markup = html(createElement(Figure, props as FigureProps, createElement("svg")));
  expect(words(markup).startsWith("Fig. 5 Rain over Kachchh has risen")).toBe(true);
  expect(words(markup)).toContain("All 45 values");
});

test("tabs move with the arrow keys and wrap, and zoom stays between one and four times", () => {
  expect(nextTabIndex("ArrowRight", 2, 3)).toBe(0);
  expect(nextTabIndex("ArrowLeft", 0, 3)).toBe(2);
  expect(nextTabIndex("End", 0, 3)).toBe(2);
  expect(nextTabIndex("a", 0, 3)).toBeNull();
  expect(clampZoom(9)).toBe(4);
  expect(zoomBy(ZOOM_RESET, 0.5)).toEqual(ZOOM_RESET);
  expect(zoomBy({ scale: 2, x: 10, y: 4 }, 1.5)).toEqual({ scale: 3, x: 10, y: 4 });
});
