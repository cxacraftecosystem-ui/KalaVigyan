from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hygiene.baseline import (
    BUDGET_COUNTS,
    RATCHETED_COUNTS,
    REGISTER_COUNT,
    BaselineError,
    RatchetStep,
    compare,
    read_baseline,
    write_baseline,
)
from hygiene.budgets import BudgetFindings, Overrun, measure_budgets
from hygiene.comments import CommentViolation, comment_language, comment_violations
from hygiene.fonts import FontViolation, font_violations
from hygiene.layers import BACKEND_APP, ImportViolation, import_violations
from hygiene.register import REGISTER_RISE, register_entries
from hygiene.text_files import EncodingViolation, encoding_violations

__all__ = ["BASELINE_FILE", "HygieneReport", "project_files", "render", "run_check"]

BASELINE_FILE = PurePosixPath("tools/hygiene_baseline.json")


@dataclass(frozen=True)
class HygieneReport:
    imports: tuple[ImportViolation, ...]
    encodings: tuple[EncodingViolation, ...]
    comments: tuple[CommentViolation, ...]
    fonts: tuple[FontViolation, ...]
    budgets: BudgetFindings
    steps: tuple[RatchetStep, ...]
    baseline_written: bool

    @property
    def passed(self) -> bool:
        ratchet_held = self.baseline_written or all(step.holds for step in self.steps)
        return not (self.imports or self.encodings or self.comments or self.fonts) and ratchet_held


def project_files(root: Path) -> list[PurePosixPath]:
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--deduplicate"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    paths = {PurePosixPath(entry) for entry in listing.split("\0") if entry}
    return sorted(path for path in paths if (root / path).is_file())


def run_check(root: Path, files: Sequence[PurePosixPath], *, update_baseline: bool = False) -> HygieneReport:
    contents = {path: (root / path).read_bytes() for path in files}
    encodings = encoding_violations(contents.items())
    unreadable = {violation.path for violation in encodings}
    texts = [
        (path, contents[path].decode("utf-8"))
        for path in files
        if comment_language(path) and str(path) not in unreadable
    ]
    python = [(path, text) for path, text in texts if path.suffix == ".py"]
    imports = import_violations((path, text) for path, text in python if path.is_relative_to(BACKEND_APP))
    comments = comment_violations(texts)
    fonts = font_violations(contents.items())
    budgets = measure_budgets(python)
    counts = {**_counts(budgets), REGISTER_COUNT: register_entries(contents)}
    baseline_path = root / BASELINE_FILE
    if update_baseline:
        steps = _steps_for_update(baseline_path, counts)
        write_baseline(baseline_path, counts)
    else:
        steps = tuple(compare(read_baseline(baseline_path), counts))
    return HygieneReport(
        tuple(imports),
        tuple(encodings),
        tuple(comments),
        tuple(fonts),
        budgets,
        steps,
        baseline_written=update_baseline,
    )


def render(report: HygieneReport) -> list[str]:
    lines = [f"import direction: {violation.describe()}" for violation in report.imports]
    lines += [f"text encoding: {violation.describe()}" for violation in report.encodings]
    lines += [f"code comment: {violation.describe()}" for violation in report.comments]
    lines += [f"web font: {violation.describe()}" for violation in report.fonts]
    overruns = dict(zip(BUDGET_COUNTS, _overruns(report.budgets), strict=True))
    for step in report.steps:
        lines.append(_step_line(step, written=report.baseline_written))
        if step.rose:
            lines += _rise_details(step.name, overruns)
    lines.append("hygiene check passed" if report.passed else "hygiene check FAILED")
    return lines


def _rise_details(name: str, overruns: dict[str, tuple[Overrun, ...]]) -> list[str]:
    if name == REGISTER_COUNT:
        return [f"  {REGISTER_RISE}"]
    return [f"  {overrun.describe()}" for overrun in overruns[name]]


def _counts(budgets: BudgetFindings) -> dict[str, int]:
    return dict(zip(BUDGET_COUNTS, (len(group) for group in _overruns(budgets)), strict=True))


def _overruns(budgets: BudgetFindings) -> tuple[tuple[Overrun, ...], ...]:
    return budgets.oversized_files, budgets.long_functions, budgets.wide_functions


def _steps_for_update(baseline_path: Path, counts: dict[str, int]) -> tuple[RatchetStep, ...]:
    if not baseline_path.is_file():
        return tuple(RatchetStep(name, counts[name], counts[name]) for name in RATCHETED_COUNTS)
    steps = tuple(compare(read_baseline(baseline_path), counts))
    risen = [f"{step.name} {step.baseline} -> {step.current}" for step in steps if step.rose]
    if risen:
        raise BaselineError(f"refusing to raise the hygiene baseline: {', '.join(risen)}")
    return steps


def _step_line(step: RatchetStep, *, written: bool) -> str:
    if written:
        return f"{step.name}: baseline {step.baseline} -> {step.current} (written)"
    if step.rose:
        return f"{step.name}: {step.current}, above the baseline of {step.baseline}"
    if step.fell and step.holds:
        return (
            f"{step.name}: {step.current}, below the baseline of {step.baseline}; --update-baseline lowers it"
        )
    if step.fell:
        return f"{step.name}: {step.current}, below the baseline of {step.baseline}; run --update-baseline"
    return f"{step.name}: {step.current} (baseline {step.baseline})"
