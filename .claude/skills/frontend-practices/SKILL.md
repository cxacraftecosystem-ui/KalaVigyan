---
name: frontend-practices
description: Durable practices for building and refactoring user-interface code (components, pages, hooks, state, styling, forms, data fetching, HTML and CSS pages, dashboards, annotation and review screens) so components are reusable, readable, accessible and consistent over years. Use whenever creating or changing any UI file (.tsx, .jsx, .ts, .js, .vue, .svelte, .css, .html), adding a screen, component, form, table, chart or dashboard, or connecting a UI to an API - even for a quick prototype or a single page. Read engineering-practices first; this skill adds the frontend specifics.
---

# Frontend practices

Read `engineering-practices` first; this skill applies its rules to user-interface code. Where
UI code lives in this repository, and the project rules a UI must respect, are in
`../engineering-practices/references/project-bindings.md`. Examples use React and TypeScript
terms; with another framework keep the principles and map the names. Anyone writing or reviewing
user-interface code here reads it, with `kalavigyan-design` for how a screen looks.

| For | Read |
|---|---|
| The house rules this applies | `engineering-practices` |
| Where UI code lives here, and the project's rules | `../engineering-practices/references/project-bindings.md` |
| Tokens, components, templates, copy and acceptance | `kalavigyan-design` |

## Structure

Organise UI code by how far a piece is reused:

```
components/ui/       generic building blocks with no domain knowledge: Button, Field, Table, Modal
components/shared/   domain components used by two or more features
features/<feature>/  one folder per screen or workflow: its pages, components, hooks, API calls
hooks/               hooks used by more than one feature
lib/                 API client, formatting, validation, constants
styles/              design tokens and global styles
types/               shared types, derived from the backend schemas
```

Promotion rule: a component starts inside the feature that needs it. When a second feature needs
it, move it to `components/shared/` (or `components/ui/` if it knows nothing about the domain)
and import it from there in both. Never copy a component into a second feature. Features do not
import from each other.

## Before creating a component

Look in the generic and shared folders first. If something close exists, extend it through props
or composition instead of writing a sibling. When you replace a component, delete the old one
and update every import in the same change.

## Components

- One component, one job, one file. Past the size budget, or when it needs "and" to describe,
  split it.
- Separate what is shown from where the data comes from. Presentational components receive data
  and callbacks and contain no fetching and no business rules; feature-level containers or hooks
  fetch, decide and pass down.
- Keep props few and typed. Prefer one `variant` with named values over several booleans, and
  composition over a long list of configuration props.
- Derive values while rendering instead of storing copies of them in state.
- Every view of remote data handles four states: loading, empty, error and success.

## Accessibility

Accessibility is part of building the component, not a later pass, and the target is the current
WCAG AA level: real buttons and links, a label for every input, full keyboard operation, visible
focus, sufficient contrast, text alternatives for images and charts, and no information carried
by colour alone. A generic component that is accessible makes every screen built from it
accessible; one that is not multiplies the problem.

## State

- Keep state as local as possible; lift it only to the nearest common parent that needs it.
- Server data belongs to a fetching and caching layer, not to a global store that mirrors it.
- Filters, pagination and selection live in the URL, so a screen can be reloaded and shared.
- A global store holds only what is truly global, such as the signed-in user or the theme.

## Data access

- One API client. Components and hooks call its functions; nothing else performs requests.
- Request and response types are derived from the backend schemas or validated against them, so
  the two sides cannot drift apart silently.
- Failures are handled in one place and tell the user what happened and what they can do.
- The server decides what a user may see. The client never receives a field it must not show
  and then hides it.

## Styling

- Colours, spacing, type sizes and radii are design tokens defined once. Components use tokens,
  never raw colour codes or pixel values.
- Themes (light, dark) are token sets, and the page sets an explicit background.
- Layouts work at phone width without horizontal scrolling.
- Inline styles are for values computed at run time only.

## Forms

- Validate with a schema shared with the API types and show each error beside its field.
- Disable submission while a request is pending, and show the outcome.
- Client-side validation helps the user; the server validates again.

## Text, numbers and language

User-visible strings live in one place per feature, ready to be translated, and sentences are
never assembled by concatenation. Numbers, units and dates go through shared formatters so the
same quantity looks the same on every screen.

## Security

Treat everything from the network or the user as untrusted: never inject it as raw markup, never
build URLs or queries by string concatenation, keep credentials out of client code and out of
storage that scripts can read, and add no third-party script without recording why.

## Performance

Measure before optimising. Memoise only a measured hot spot, virtualise long lists, split code
by route, and watch the size of what is shipped. Blanket memoisation makes components harder to
read and rarely helps.

## Dependencies

A UI library is a long commitment. Add one only when it clearly beats writing the piece, wrap it
behind your own component so it can be replaced, and record the decision.

## Tests

- Test components by what a user sees and does, not by their internals.
- Cover the four data states and the main interaction of each component.
- One end-to-end happy path per feature.

## Before you call it done

- Did I look for an existing component before creating this one?
- Is anything used by two features now in the shared or generic folder?
- Are data fetching and business rules outside the presentational components?
- Do all remote views handle loading, empty, error and success?
- Are colours and spacing taken from tokens?
- Is every control labelled and usable by keyboard?
- Do the types come from the backend schemas?
- Is untrusted content never rendered as raw markup?
- Do the tests exercise behaviour a user would notice?

## How this skill is kept true

| What | Kept true by |
|---|---|
| Type checks, lint and unit specs | Frontend checks (`.github/workflows/frontend-checks.yml`) |
| Retired classes, hex literals and physical utilities | the design guard, `frontend/e2e/design-guard-unit.spec.ts` |
| Accessibility and layout at the acceptance widths | the browser smoke and the capture and parity runs |

Re-read it when the web client changes framework, a check is automated, or the design system changes a rule.
