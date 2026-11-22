# 0001. Adopt the practice skills and an automated hygiene check

The engineering, backend and frontend practice skills bind this repository, with the owner's rules
over them and every project fact in one bindings file. `tools/hygiene_check.py` holds their
measurable rules to an exact ratcheted baseline and a table of the allowed import layers.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The provider layer moved below services, so `providers -> services` is gone (amends item 5) | [decision 0139](0139-sources-and-providers-reach-outside-services-once.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked that the coding practices written as skills in `C:/dev/IIT/Research/.claude/skills/`
(`engineering-practices`, `backend-practices`, `frontend-practices`) bind this repository from
now on. The skills keep their rules general and put every project fact in one bindings file.
Some owner rules are stricter than the skills: no code comments at all, latest stable versions,
secret names only, nothing heavy run locally.

## Decision

1. The three skills are copied unchanged into `.claude/skills/`. Only
   `engineering-practices/references/project-bindings.md` is rewritten for KalaVigyan: layout,
   import direction, budgets (the same numbers as the Research bindings), commands, version
   control, living documents, and the plan's domain rules.
2. The owner's rules override the skills where they differ, and the bindings say so. Where a
   skill says to explain a choice or an exception in a comment, the explanation goes into
   `docs/decisions/` or `docs/TECH_DEBT.md` instead.
3. `tools/hygiene_check.py` (a thin script over the tested `tools/hygiene/` package) checks on
   every Backend checks run:
   - import direction in `backend/app`, from the table `LAYER_IMPORTS`;
   - UTF-8 without a byte-order mark and LF endings for every tracked or new text file;
   - no Python comments other than functional directives (the owner's rule, already enforced for
     the frontend by a grep step in Frontend checks);
   - ratcheted counts of Python files over 400 lines, functions over 40 lines and functions with
     more than 5 positional parameters, against `tools/hygiene_baseline.json`.
4. The ratchet is exact: a count above the baseline fails, and a count below it also fails until
   `--update-baseline` records it. `--update-baseline` refuses to raise a count. This keeps the
   baseline from going stale and letting a later change spend a margin someone else freed.
5. The layer table records the code as it is:
   - `core` may import `models`, because `core/deps.py` returns the `User` row from the
     current-user dependency;
   - `providers` may import `services`, because the router reads the model catalogue
     (`services/ai_providers.py`), app settings and managed keys.
   Both stay allowed; moving the catalogue under `providers/` is in the debt register.
6. `tools/**` triggers Backend checks on pull requests only. A push to `main` touching only
   `tools/` does not start Backend checks, because Deploy backend follows every successful
   push run and a tooling change should not redeploy the API. The check still runs on the next
   backend change and on manual dispatch.
7. The tools package reuses the backend environment (`backend/.venv`: ruff, pytest) and the
   backend ruff settings (`tools/pyproject.toml` extends `backend/pyproject.toml`), so there is
   no second toolchain to keep current.

## Consequences

- A new package under `backend/app` fails the check until it has a row in `LAYER_IMPORTS` and in
  the bindings; this is deliberate (a guard fails closed).
- Existing over-budget code (14 files, 55 functions over 40 lines, 9 wide functions on
  2026-11-16) is recorded, not fixed; every clean-up lowers the baseline.
- Nesting depth, the frontend size budget and the frontend import boundaries are not checked by a
  tool yet (debt register).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
