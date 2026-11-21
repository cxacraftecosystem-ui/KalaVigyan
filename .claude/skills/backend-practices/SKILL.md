---
name: backend-practices
description: Durable practices for writing, fixing and refactoring backend Python code (packages, libraries, analysis and statistics, pipelines, data schemas, service clients, command lines) so it stays layered, reusable and readable over years. Use whenever writing, fixing, refactoring or reviewing any .py file - adding a module or function, touching DataFrame analysis, statistics, scoring, pipelines, configuration, data formats or a CLI - including small bug fixes and test changes. Read engineering-practices first; this skill adds the Python backend specifics.
---

# Backend practices (Python)

Read `engineering-practices` first; this skill applies its rules to backend Python code. The
names of this repository's layers, its shared layer, its catalogue and its commands are in
`../engineering-practices/references/project-bindings.md`. Anyone writing or reviewing a `.py`
file here reads it.

| For | Read |
|---|---|
| The house rules this applies | `engineering-practices` |
| This repository's layers, shared layer and commands | `../engineering-practices/references/project-bindings.md` |
| The shared code's catalogue | `docs/CORE_API.md` |

## Layers and the direction of imports

Arrange a backend as layers that depend in one direction only:

```
entry points (CLI, API)  ->  feature packages  ->  shared layer
```

- The shared layer knows nothing about any feature. It holds what is neutral or needed by more
  than one feature.
- Feature packages never import each other. What two features both need moves into the shared
  layer.
- Inside a feature the flow is data models and loading, then domain logic, then analysis, then
  orchestration, then entry point. A lower layer never imports a higher one. No import cycles.

When an import would point the wrong way, the code is telling you something is in the wrong
place. Move it; do not work around it with a late import.

## Use the shared layer

Before writing a helper, check the catalogue. The needs that are reinvented most often, and
therefore always belong to the shared layer: numeric primitives (sigmoid, logit, rounding rules,
rates with intervals); resampling and tests; agreement and scoring metrics; text normalisation;
file reading and atomic writing; hashing; seeded randomness; identifiers; converting values to
plain serialisable types; checks for missing values; required-column checks.

If what you need is absent and a second module needs it too, add it to the shared layer with
tests and a catalogue entry, then use it. A private copy "for now" is how duplication starts.

## Module design

- One responsibility per module, named for it. Public names first, private helpers below, and an
  explicit public surface (`__all__`).
- No module-level mutable state: no caches, registries or defaults that a call can change behind
  another caller's back. State lives in an object the caller holds and passes in.
- Functional core, imperative shell. Analysis, scoring and transformation functions take data
  and return data. Files, network and clocks are touched only at the edges (orchestration,
  clients, entry points). This is what keeps the core testable and reusable.
- Records that cross a boundary (files, module interfaces, service calls) are typed models, not
  loose dictionaries. A function returns one well-named result type, not a tuple of mixed things.
- Options are keyword-only. A boolean parameter that changes what a function does is two
  functions, or a named choice.
- Errors derive from a small shared hierarchy so callers can catch by category (invalid input, a
  refused guard, bad configuration, a failed external call). Library code raises; it does not
  print and it does not exit.
- Library code logs through the standard logging module. Only entry points write to the
  terminal.

## Functions

A function fits on a screen and does one thing. When it grows past the budget, extract its steps
into named functions so the body reads as an outline. A long function usually hides several
smaller ones, and often one that already exists in the shared layer.

## Tabular data

- Column names are constants defined once and imported. A name typed as a string in many files
  will be typed differently in one of them.
- A public function states the columns it needs and checks them on entry with the shared helper,
  failing with a message that lists what is missing.
- Do not modify a frame passed in; return a new one. Sort outputs so results are deterministic.
- Keep rows and columns that must not mix (labels and features, training and held-out rows)
  apart by construction, not by convention.

## Statistics and numerical code

- One implementation per estimator, in the shared layer, citing the source of its formula.
- Each estimator has a hand-calculated test and defined behaviour for degenerate input: it
  reports "not estimable" with the reason, never a plausible-looking number.
- Randomness always comes from the shared seeded generator with an explicit seed and stream.
- Resampling respects the unit of independence, and the function says what that unit is.
- Prefer clear vectorised code. Optimise only what a measurement shows to be slow, and keep the
  simple version as the test oracle.

## Data formats

- Every stored format has a schema, a version field and a validator that runs on load.
- Changing a format means writing a migration and bumping the version. Old files are migrated or
  rejected with a clear message, never read under new assumptions.
- Derived files are regenerated by a command, never patched by hand.

## External services

Model providers, databases and other services are reached through one adapter each, behind a
small interface the rest of the code depends on. Adapters translate failures into the shared
error categories, never leak credentials into logs, and can be replaced by a fake in tests. No
test touches the network.

## Configuration and constants

- Settings live in configuration files read through one loader; nothing reads a file relative to
  the current working directory.
- A threshold from a specification is a named constant defined once, with its source, and
  imported wherever it is used.

## Entry points

A CLI or API handler is thin: parse and validate input, call one orchestration function, turn
the result into output and a status code. No analysis logic lives in entry points or scripts.

## Types and style

Type hints on every public function; run the project's type and lint tools and fix what they
report instead of silencing it. A suppression needs a reason in the same line.

## Tests

- Mirror the package layout. Shared fixtures and builders live in one fixtures location.
- Add a contract test wherever two modules meet: produce the output of one and feed it to the
  other.
- No network, no dependence on test order, no reliance on files outside the test's own temporary
  directory unless the test is explicitly about a real dataset.
- Run a module's tests while working, and the whole suite and the hygiene check before finishing.

## Before you call it done

- Do imports point only downward, with no feature-to-feature import?
- Did I use the shared layer for every numeric, text, file, hashing and metric need?
- Is anything I wrote useful to a second module? Then is it in the shared layer and catalogue?
- Are functions short, single-purpose and free of flag arguments?
- Are column names and thresholds imported constants?
- Does every public function validate its inputs and fail with a clear message?
- Does any changed data format have a version bump and a migration?
- Is there a contract test for each interface I touched?
- Do the whole suite and the hygiene check pass?

## How this skill is kept true

| What | Kept true by |
|---|---|
| Layers and the direction of imports | `tools/hygiene/layers.py`, enforced by `tools/hygiene_check.py` |
| Lint and format | `ruff check` and `ruff format --check` in Backend checks (`.github/workflows/backend-checks.yml`) |
| File, function and parameter budgets, and no comments | `tools/hygiene_check.py` against its baseline |

Re-read it when the backend gains a layer, a tool or a rule from the owner.
