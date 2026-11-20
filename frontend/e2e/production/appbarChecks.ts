import { expect, type Locator, type Page } from "@playwright/test";

import { ROLE_LABELS } from "@/lib/permissions";
import type { User } from "@/lib/types";

import { ACCOUNT_LABEL, APPBAR_NAV_MIN_WIDTH, MAIN_NAV_LABEL, MENU_LABEL, READING_BAR, labelProblems, navExpectation } from "./checks";
import { clickProblems } from "./clicks";

const BADGES = '[data-testid="unread-notes"], .kv-bar-count, .sr-only, [title]';
const SIGN_OUT = "Sign out";

export function wideBar(page: Page): boolean {
  return (page.viewportSize()?.width ?? 0) >= APPBAR_NAV_MIN_WIDTH;
}

function unexpectedRole(user: User): string {
  return `the E2E account is ${user.role}; it must be STUDENT or RESEARCHER, the roles without two-step`;
}

export function labelsOf(links: Locator): Promise<string[]> {
  return links.evaluateAll(
    (nodes, badges) =>
      nodes.map((node) => {
        const copy = node.cloneNode(true) as Element;
        copy.querySelectorAll(badges).forEach((badge) => badge.remove());
        return (copy.textContent ?? "").replace(/\s+/g, " ").trim();
      }),
    BADGES
  );
}

function mainNav(page: Page): Locator {
  return page.getByRole("navigation", { name: MAIN_NAV_LABEL, exact: true });
}

function menuButton(page: Page): Locator {
  return page.getByRole("button", { name: MENU_LABEL, exact: true });
}

async function currentProblems(nav: Locator, current: string | null): Promise<string[]> {
  if (current === null) return [];
  const marked = await labelsOf(nav.locator('a[aria-current="page"]'));
  return marked.length === 1 && marked[0] === current ? [] : [`the navigation bar marks [${marked.join(", ")}] as the current page; it should mark ${current}`];
}

async function barShape(page: Page, expected: readonly string[], current: string | null): Promise<string[]> {
  await page.evaluate(() => window.scrollTo(0, 0));
  if (!wideBar(page)) {
    await expect(menuButton(page)).toBeVisible();
    return (await mainNav(page).count()) > 0 ? ["the Main navigation shows below 768 px beside the Menu button that stands for it"] : [];
  }
  const nav = mainNav(page);
  await expect(nav).toBeVisible();
  const problems = [...labelProblems("the navigation bar", expected, await labelsOf(nav.locator("a"))), ...(await currentProblems(nav, current))];
  if ((await menuButton(page).count()) > 0) problems.push("the Menu button shows from 768 px beside the navigation it stands for");
  return problems;
}

export async function barProblems(page: Page, user: User, current: string | null): Promise<string[]> {
  const expected = navExpectation(user.role);
  if (!expected) return [unexpectedRole(user)];
  const problems = await barShape(page, expected.bar, current);
  const account = mainNav(page).getByRole("button", { name: ACCOUNT_LABEL, exact: true });
  if (wideBar(page) && (await account.count()) === 0) problems.push(`the navigation bar has no ${ACCOUNT_LABEL} button`);
  return problems;
}

async function sheetProblems(page: Page, expected: readonly string[]): Promise<string[]> {
  const refused = await clickProblems(page, menuButton(page), `the ${MENU_LABEL} button`);
  if (refused.length > 0) return refused;
  const panel = page.getByRole("dialog", { name: MENU_LABEL, exact: true });
  await expect(panel).toBeVisible();
  const problems = labelProblems("the menu", expected, await labelsOf(panel.locator("a")));
  await closePanel(page, panel);
  return problems;
}

async function closePanel(page: Page, panel: Locator): Promise<void> {
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : undefined));
}

export async function readingBarProblems(page: Page, current: string | null): Promise<string[]> {
  const problems = await barShape(page, READING_BAR, current);
  if (wideBar(page) || problems.length > 0) return problems;
  return sheetProblems(page, READING_BAR);
}

async function panelProblems(panel: Locator, where: string, user: User): Promise<string[]> {
  const problems: string[] = [];
  if (!(await panel.innerText()).includes(ROLE_LABELS[user.role])) problems.push(`${where} does not name the role ${ROLE_LABELS[user.role]}`);
  if ((await panel.getByRole("button", { name: SIGN_OUT, exact: true }).count()) === 0) problems.push(`${where} offers no ${SIGN_OUT}`);
  return problems;
}

export async function menuProblems(page: Page, user: User): Promise<string[]> {
  const expected = navExpectation(user.role);
  if (!expected) return [unexpectedRole(user)];
  const wide = wideBar(page);
  const label = wide ? ACCOUNT_LABEL : MENU_LABEL;
  const where = wide ? "the account menu" : "the menu";
  const refused = await clickProblems(page, page.getByRole("button", { name: label, exact: true }), `the ${label} button`);
  if (refused.length > 0) return refused;
  const panel = page.getByRole("dialog", { name: label, exact: true });
  await expect(panel).toBeVisible();
  const problems = [...labelProblems(where, wide ? expected.account : expected.menu, await labelsOf(panel.locator("a"))), ...(await panelProblems(panel, where, user))];
  if ((await page.locator('a[href^="/admin"]').count()) > 0) problems.push("an admin link is on the page for a role without admin areas");
  await closePanel(page, panel);
  return problems;
}
