---
name: engineering-practices
description: Durable house rules for writing, changing, reviewing or refactoring ANY code or project file - reuse before writing, where shared code lives, size and structure budgets, naming, interfaces that last, error handling, tests, scripts, configs, data files, docs, recording decisions and debt, and finishing one thing before starting the next. Use this skill before touching code of any kind (new modules, bug fixes, refactors, tests, scripts, configs, data tooling) and whenever asked to clean up, consolidate, de-duplicate, review or "fix" something, even if the request never mentions standards. Python package work also needs backend-practices; user-interface work also needs frontend-practices.
---

# Engineering practices

Rules for keeping a codebase readable, reusable and maintainable as it grows and as people and
tools come and go. They are written to outlive any single task: nothing in this file depends on
the present state of the project.

Everything that is specific to this repository (folder names, commands, budgets, living
documents) is in one file, `references/project-bindings.md`. Read it together with this skill.
When the project changes, update the bindings, not the rules.

| For | Read |
|---|---|
| This repository's layers, commands, budgets and owner rules | `references/project-bindings.md` |
| Backend Python | `backend-practices` |
| User-interface code | `frontend-practices`, and `kalavigyan-design` for every screen |
| Generated names of files and keys | `naming` |

## Why these rules

Codebases that grow quickly fail in the same few ways: the same helper written many times under
vague names; units too large to hold in one's head; modules that each assume something different
about the same thing; tests that only prove a module agrees with itself; decisions nobody wrote
down; standards that live in memory and are forgotten under pressure. Each rule below removes one
of these causes. When a rule and a deadline conflict, the rule wins, because tangled code is paid
for again on every later change.

## The rules, in priority order

1. **Understand before writing.** Read the specification you are implementing, the code you are
   about to change, and its callers.
2. **Reuse before writing.** Use what exists, extend what is close, write new code last.
3. **One home for every thing.** Each constant, name, formula, schema, threshold and helper is
   defined once and imported everywhere else.
4. **Small, readable units.** Code is read far more often than it is written; optimise for the
   next reader.
5. **Finish before moving on.** A change is done when it is integrated, tested, documented and
   the old path is gone.
6. **Leave a trail.** Record decisions, debt and exceptions where the next person will find them.

## Reuse before writing

Before adding a function, class, component, constant or script:

- Search by what it does, not only by the name you would give it: the key verb, the formula, a
  distinctive literal. Look in the shared layer and its catalogue first, then in sibling modules.
- If the same idea already exists twice, do not add a third. Consolidate the two into one shared
  implementation, switch both callers, then continue.
- Never copy a block and adapt it. Extract the common part and call it from both places.
- Never keep two definitions "equal by tests". One imports from the other, or both import from a
  shared home.

A private helper with a vague name (`_plain`, `_get`, `_val`, `_check`, `_fix`) is usually a
shared function reinvented. Name it for what it does and ask whether it belongs in the shared
layer.

## Where things live

Place code at the lowest level that every user of it can import from:

| Used by | Home |
|---|---|
| one module | private in that module |
| several modules of one package | that package's shared module, named for what it holds |
| more than one package | the shared layer |

Dependencies point one way: feature packages depend on the shared layer, never on each other and
never the reverse. If package A needs something inside package B, that thing is shared by
definition: move it down and import it from there in both. A sideways import means a shared
component is sitting in the wrong place.

The shared layer stays healthy only under discipline:

- **Promote on real use.** Something enters the shared layer when a second real caller exists,
  not because it might be useful one day. Speculative generality is debt.
- **Shared code knows no feature.** Its interface speaks in neutral terms; a parameter named
  after one feature is a sign it was moved, not generalised.
- **No dumping grounds.** No `utils`, `helpers`, `misc` or `common` module that collects
  unrelated things. A shared module is named for the one topic it covers.
- **A higher bar.** Shared code has tests, a documented contract and an entry in the catalogue.
  A shared component nobody can find gets written again.

## Small, readable units

The bindings file gives the size budgets for files, functions, parameter lists and nesting. They
are triggers for a split, not walls: when a unit exceeds one, divide it along its responsibilities
and name the parts.

- Name things for what they mean in the domain, using the project's registered vocabulary. Do not
  invent a synonym for an existing term.
- Functions are verbs, values are nouns, booleans read as questions.
- Prefer guard clauses and early returns to nesting.
- A flag argument that switches a function between two behaviours means there are two functions.
- Comments say why, or state a rule the code cannot express. Delete commented-out and unused
  code; history belongs to version control.
- A module opens with what it is for and which part of the specification it implements.

## Interfaces that last

Most long-term pain comes from interfaces, not implementations.

- Keep public interfaces narrow, typed and documented. Everything else is private and free to
  change.
- Change a shared interface together with every caller, in one change. If that is impossible,
  deprecate: keep the old form working, mark it with the date it will be removed, and remove it
  on that date. Two permanent ways to do one thing is the outcome to avoid.
- Stored data carries a schema version. A format change comes with a migration and never
  silently reinterprets old files.
- Wrap each external service or library that could be replaced (a model provider, a database, a
  rendering library) behind one small adapter. The rest of the code talks to the adapter.
- A new third-party dependency is a decision: justify it, pin it, record it. Prefer what the
  standard library or an existing dependency already does.

## Errors and guards

- Fail early and loudly, with a specific error that names the offending id or value. Never
  swallow an error or catch broadly to keep going.
- No silent fallbacks: no quiet default, imputation or skipped row when input is missing or
  malformed. Refuse, or return an explicit "not available" with the reason.
- A guard that protects integrity (access rules, freezes, blinding, leak checks) fails closed:
  when the information needed to decide is missing, the answer is no. Never weaken a guard to
  make a test or a demo pass.
- Validate at boundaries; trust the validated value inside.
- Secrets come from the environment and never appear in code, logs, reports or test fixtures.

## Tests

- A test states a rule from the specification and checks it against an expected value obtained
  independently: by hand, from the document, or from a reference implementation. Never produce
  the expected value by running the code under test.
- Fixing a defect starts with a test that fails because of it.
- Test the seams. A unit that passes its own tests but disagrees with its neighbour is the most
  common serious defect, so every interface between modules has a test that exercises both sides.
- Shared fixtures live in one place and are imported.
- Tests are deterministic, need no network, run fast, and check one concern each.

## Changing existing code

- Change code in place. No parallel `_v2` beside the old path: replace it and delete what you
  replaced.
- Rename with every caller in the same change.
- Fix the cause, not the symptom. When a test fails, read the specification to decide whether the
  code or the test holds the wrong rule, and fix that one.
- Leave the files you touch cleaner than you found them, within the scope of your task.
- Keep pure restructuring separate from behaviour changes where you can; a restructuring leaves
  every test passing unchanged.

## Scripts, configuration, data and documents

- Scripts are thin: parse arguments, call a tested function, report.
- Configuration values live in one file per concern, read by one loader. Code holds no magic
  numbers; a threshold is a named constant defined once, with its source.
- Generated files are regenerated, never edited by hand. Data files are validated on load.
- Paths resolve from a known root, never from the current working directory.
- Text files are UTF-8 without a byte-order mark, with LF line endings.
- A document that disagrees with the code is a defect. Update the living documents named in the
  bindings in the same change that makes them untrue.

## Decisions, debt and exceptions

- **Decisions.** When you choose between real alternatives (an interface, a convention, a
  dependency, a reading of an ambiguous requirement), write a short record in the decision log:
  the context, the choice, and what follows from it. Future readers need the reason more than
  the result.
- **Debt.** When you knowingly leave something below standard, add it to the debt register with
  what is wrong, why it was left, and what would clear it. An unrecorded shortcut is a trap.
- **Exceptions.** Rules can be broken when breaking them is clearly better. Do it openly: a
  comment at the spot naming the rule and the reason, and a debt entry if it is temporary.

## Automate what can be checked

A rule that a tool can check should be checked by a tool, on every run, forever; people and
agents are for judgement. The bindings name the project's check command. It works as a ratchet:
existing shortfalls are recorded in a baseline, the count may go down and never up. When the same
kind of mistake is made twice, add a check for it instead of a reminder.

## Working method

- Work in small steps and verify each one. Run the relevant tests after every meaningful change
  and the whole suite and the check command before calling anything done.
- Agree an interface before two pieces of code are written against it, and build the shared piece
  first. Code that must fit together is not written in parallel by authors who cannot see each
  other's work.
- Do not start the next task on top of failing tests, an unintegrated module or a known
  duplicate. Fix, consolidate, then move forward.
- Spend effort where it changes the outcome: thinking and checking, not volume.

## Keeping this skill alive

These files are part of the codebase. When a rule turns out to be wrong, missing or unclear,
change the skill in the same change that taught you, and note why in the decision log. If the
code and a rule disagree, one of them is wrong: fix it, do not work around it. Keep rules general
and put project facts in the bindings, so the skill stays true when the project moves.

## Before you call it done

- Did I search for an existing implementation before writing each new piece?
- Is every shared piece in the right home, feature-neutral, tested and in the catalogue?
- Does every definition have exactly one home?
- Are the units I touched within budget and named for what they do?
- Do errors fail loudly and guards fail closed?
- Does each new or changed rule have a test with an independently derived expected value?
- Is the old path deleted and every caller updated?
- Are decisions, debt and exceptions recorded?
- Do the whole test suite and the check command pass?
- Are the living documents still true?

## How this skill is kept true

| What | Kept true by |
|---|---|
| Size, nesting, parameter and comment budgets, and the import direction | `tools/hygiene_check.py` against `tools/hygiene_baseline.json`, in the Hygiene workflow |
| Tests with independently derived expected values | review of each change, and the test suites that run on every pull request |
| The project facts it leaves to the bindings | `references/project-bindings.md` and its own closing section |

Re-read it when a rule proves wrong, missing or unclear, as Keeping this skill alive says.
