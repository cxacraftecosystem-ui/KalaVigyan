from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from app.research.component_specs_science_figures import Molecule3dSpec, MoleculeModel
from app.research.component_specs_science_parts import Differs, Equation, Species
from app.research.component_specs_science_players import (
    DipPlayerSpec,
    LaneArrow,
    LaneSpecies,
    ReactionPlayerSpec,
    ReactionStep,
    StagePlayerSpec,
    StepEquation,
    StepLane,
    StepNoEquation,
)

from .export_still_figures import molecule_still, swatch_strip
from .export_still_svg import svg_still
from .export_stills import Still
from .page_export_figures import FigureAsk, prefixed, scene_of
from .page_export_model import ExportFigure, ExportText, Run, plain_text
from .page_export_units import rich_runs
from .page_export_words import AT_REST, KEY

__all__ = ["dip_player_figure", "molecule_figure", "raw_at", "reaction_player_figure", "stage_player_figure"]

ARROW = " → "
PLUS = " + "


def raw_at(ask: FigureAsk, *path: str | int) -> Any:
    value: Any = ask.spec
    for step in path:
        if isinstance(step, int) and isinstance(value, list) and 0 <= step < len(value):
            value = value[step]
        elif isinstance(step, str) and isinstance(value, dict):
            value = value.get(step)
        else:
            return None
    return value


def reaction_player_figure(ask: FigureAsk, spec: object) -> ExportFigure | None:
    if not isinstance(spec, ReactionPlayerSpec):
        return None
    ask.replaced(spec.head.number)
    rest = spec.current - 1
    scene = raw_at(ask, "steps", rest, "scene", "art") or raw_at(
        ask, "scenes", min(rest, len(spec.scenes) - 1)
    )
    lines: list[ExportText | None] = [ask.unit(spec.head.dek, "note")]
    for number, step in enumerate(spec.steps, start=1):
        lines += _step_lines(ask, step, number, rest=number == spec.current)
    lines.append(ask.unit(spec.status, "note"))
    return ask.figure([scene_of(scene)], lines, ask.title(spec.head.title))


def _step_lines(ask: FigureAsk, step: ReactionStep, number: int, *, rest: bool) -> list[ExportText | None]:
    text = step.text
    named = Run(f"{number}. {step.name}")
    resting = (Run(f" ({ask.words.said(AT_REST)})", lang=ask.words.lang(AT_REST)),) if rest else ()
    lines: list[ExportText | None] = [
        ExportText(runs=(named, *resting), role="item"),
        ask.unit(text.kicker, "note"),
        ask.unit(text.heading, "subheading"),
        *ask.units(text.paragraphs),
        *(
            prefixed(f"{ask.plain(condition.term)}: ", ask.unit(condition.value), "body")
            for condition in text.conditions
        ),
    ]
    for part in step.chemistry.parts:
        if isinstance(part, StepLane):
            lines.append(_lane(part))
        elif isinstance(part, StepEquation):
            lines += _equation(ask, part.equation)
        elif isinstance(part, StepNoEquation):
            lines.append(ask.unit(part.unit, "note"))
    lines += _differs(ask, text.differs)
    if step.scene is not None:
        lines.append(ask.unit(step.scene.where, "note"))
    return lines


def _lane(lane: StepLane) -> ExportText:
    runs: list[Run] = [Run(f"{lane.label}: ")]
    for item in lane.items:
        if isinstance(item, LaneSpecies):
            runs += rich_runs(item.name)
            if item.formula:
                runs += [Run(" ("), *rich_runs(item.formula), Run(")")]
        elif isinstance(item, LaneArrow):
            runs.append(Run(f" → {item.label} → "))
        else:
            runs.append(Run(PLUS))
    return ExportText(runs=tuple(runs), role="body")


def _equation(ask: FigureAsk, equation: Equation) -> list[ExportText | None]:
    runs = [
        Run(f"{equation.label}: "),
        *_side(equation.line.reactants),
        Run(ARROW),
        *_side(equation.line.products),
    ]
    return [ExportText(runs=tuple(runs), role="body"), *ask.units(equation.notes, "note")]


def _side(species: Sequence[Species]) -> list[Run]:
    runs: list[Run] = []
    for at, one in enumerate(species):
        if at:
            runs.append(Run(PLUS))
        runs += rich_runs(one.formula)
    return runs


def _differs(ask: FigureAsk, differs: Differs | None) -> list[ExportText | None]:
    if differs is None:
        return []
    return [plain_text(differs.summary, "note"), *ask.units(differs.body)]


def dip_player_figure(ask: FigureAsk, spec: object) -> ExportFigure | None:
    if not isinstance(spec, DipPlayerSpec):
        return None
    ask.replaced(spec.head.number)
    lines: list[ExportText | None] = [ask.unit(spec.head.dek, "note"), ask.unit(spec.phase, "note")]
    for number, phase in enumerate(spec.phases, start=1):
        lines.append(prefixed(f"{number}. {ask.plain(phase.kicker)}: ", ask.unit(phase.text)))
    count = ", ".join(str(at) for at in range(1, len(spec.dips) + 1))
    lines.append(prefixed(f"{spec.strip_label} ({count}): ", ask.unit(spec.dips_label), "note"))
    if spec.equation is not None:
        lines += _equation(ask, spec.equation)
    lines.append(ask.unit(spec.status, "note"))
    stills = [scene_of(raw_at(ask, "scene")), swatch_strip(list(spec.dips))]
    return ask.figure(stills, lines, ask.title(spec.head.title))


def stage_player_figure(ask: FigureAsk, spec: object) -> ExportFigure | None:
    if not isinstance(spec, StagePlayerSpec):
        return None
    ask.replaced(spec.head.number, *(stage.number for stage in spec.stages))
    lines: list[ExportText | None] = [ask.unit(spec.head.dek, "note"), ask.unit(spec.rest_name, "note")]
    for number, stage in enumerate(spec.stages, start=1):
        named = (
            stage.name
            if not stage.local or stage.english == stage.name
            else f"{stage.name} ({stage.english})"
        )
        lines += [
            plain_text(f"{number}. {named}", "item"),
            ask.unit(stage.heading, "subheading"),
            *ask.units(stage.texts),
            plain_text(f"{spec.after_label}: {stage.after}", "note"),
            ask.unit(stage.after_sentence),
            ask.unit(stage.why),
            ask.unit(stage.materials, "note"),
            *_differs(ask, stage.differs),
        ]
    lines += [ask.unit(spec.finish.heading, "subheading"), *ask.units(spec.finish.paragraphs)]
    lines.append(ask.unit(spec.source, "credit"))
    swatches = [stage.swatch for stage in spec.stages]
    scenes = [scene_of(raw_at(ask, "stages", at, "scene")) for at in range(len(spec.stages))]
    stills = [scene_of(raw_at(ask, "drawing")), *scenes, swatch_strip(swatches) if any(swatches) else None]
    return ask.figure(stills, lines, ask.title(spec.head.title))


def molecule_figure(ask: FigureAsk, spec: object) -> ExportFigure | None:
    if not isinstance(spec, Molecule3dSpec):
        return None
    ask.replaced(spec.head.number)
    stills = [_molecule_still(ask, model, at) for at, model in enumerate(spec.molecules)]
    lines: list[ExportText | None] = [ask.unit(spec.head.dek, "note")]
    for model in spec.molecules:
        lines += list(_molecule_lines(model))
    lines += ask.units(block.unit for block in spec.side)
    key = [item.label for item in spec.key]
    lines.append(ask.words.labelled(KEY, "; ".join(key)) if key else None)
    return ask.figure(stills, lines, ask.title(spec.head.title))


def _molecule_still(ask: FigureAsk, model: MoleculeModel, at: int) -> Still | None:
    if model.geometry is not None:
        return molecule_still(model.geometry, model.yaw, model.pitch)
    drawing = raw_at(ask, "molecules", at, "drawing")
    return svg_still(drawing) if isinstance(drawing, dict) else None


def _molecule_lines(model: MoleculeModel) -> Iterator[ExportText]:
    named = ExportText(
        runs=(Run(f"{model.name} · "), *rich_runs(model.formula), Run(f" · PubChem CID {model.cid}")),
        role="item",
    )
    yield named
    yield plain_text(model.atoms, "body")
    yield plain_text(model.note, "note")
