from __future__ import annotations

from typing import Any

from design.colour import oklch
from design.system import System

__all__ = ["validate"]

TEXT_RATIO = 4.5
HIGH_CONTRAST_TEXT_RATIO = 7
GRAPHIC_RATIO = 3
FIRST_STEP_GAP = 10
ADJACENT_STEP_GAP = 8
ELEVATION_ADJACENT_GAP = 5
FAMILY_CVD_FLOOR = 6
FAMILY_NORMAL_FLOOR = 15
WATER_LAND_GAP = 10
SALT_LAND_GAP = 5
PLATE_INK_RATIO = 5
PLATE_TEXTURE_GAP = 3
MATERIAL_RESERVED_GAP = 3
INTERACTIVE_CHROMA = 0.15
BLUE_HUES = (230, 290)


def _needed_ratio(kind: str, theme: str) -> float | None:
    text = HIGH_CONTRAST_TEXT_RATIO if theme.startswith("hc") else TEXT_RATIO
    return {"text": text, "onFill": text, "large-text": GRAPHIC_RATIO, "graphic": GRAPHIC_RATIO}.get(kind)


def _colour_violations(tokens: dict[str, Any], system: System) -> list[str]:
    bad = []
    for name, entry in tokens["color"].items():
        for theme in system.themes:
            lowest = min(entry[theme]["contrast"].values())
            need = _needed_ratio(entry["class"], theme)
            if need and lowest < need:
                bad.append(f"{name} {theme} contrast {lowest} < {need}")
    gaps = tokens["color"]["indigo"]["checks"]["infoVsIndigoDeltaE"]
    bad += [
        f"info vs indigo {theme} {gaps[theme]}"
        for theme in system.themes
        if gaps[theme] < system.data["floor"]
    ]
    return bad


def _ramp_theme_violations(key: str, theme: str, entry: dict[str, Any], floor: float) -> list[str]:
    bad = []
    reserved = entry["reservedMin"]
    if reserved["deltaE"] < floor:
        bad.append(
            f"ramp {key} {theme} step {reserved['step']} {reserved['deltaE']} from {reserved['token']}"
        )
    bad += [f"ramp {key} {theme} first vs {s} {v}" for s, v in entry["firstVs"].items() if v < FIRST_STEP_GAP]
    for marker in ("neutralVs", "highestVs"):
        bad += [
            f"ramp {key} {theme} {marker} {s} {v}"
            for s, v in entry.get(marker, {}).items()
            if v < FIRST_STEP_GAP
        ]
    limit = ELEVATION_ADJACENT_GAP if key == "elevation" else ADJACENT_STEP_GAP
    if entry["adjacentMin"] < limit:
        bad.append(f"ramp {key} {theme} adjacent {entry['adjacentMin']} < {limit}")
    return bad


def _ramp_violations(tokens: dict[str, Any], system: System) -> list[str]:
    floor = system.data["floor"]
    bad = []
    for key, ramp in tokens["dataviz"]["ramps"].items():
        for theme in system.themes:
            bad += _ramp_theme_violations(key, theme, ramp[theme], floor)
    return bad


def _chart_violations(tokens: dict[str, Any], system: System) -> list[str]:
    bad = []
    for name, entry in tokens["dataviz"]["chart"].items():
        for theme in system.themes:
            values = entry[theme]
            if entry["class"] == "graphic" and min(values["onGround"], values["onSunk"]) < GRAPHIC_RATIO:
                bad.append(f"chart {name} {theme} {values['onGround']}/{values['onSunk']} < {GRAPHIC_RATIO}")
            if "reservedMin" in values and values["reservedMin"]["deltaE"] < system.data["floor"]:
                bad.append(f"series {name} {theme} {values['reservedMin']}")
            if name == "series-count" and values["onLand"] < GRAPHIC_RATIO:
                bad.append(f"series-count {theme} on land {values['onLand']}")
    return bad


def _family_violations(tokens: dict[str, Any], system: System) -> list[str]:
    families = tokens["dataviz"]["categorical"]
    bad = []
    for theme in system.themes:
        entry = families[theme]
        if entry["reservedMin"]["deltaE"] < system.data["floor"]:
            bad.append(f"family {theme} {entry['reservedMin']}")
        cvd, normal = entry["worstAdjacentCvdDeltaE"], entry["worstAdjacentNormalDeltaE"]
        if cvd < FAMILY_CVD_FLOOR or normal < FAMILY_NORMAL_FLOOR:
            bad.append(f"family {theme} cvd {cvd} normal {normal}")
    return bad


def _map_entry_violations(name: str, kind: str, theme: str, entry: dict[str, Any]) -> list[str]:
    need = TEXT_RATIO if kind == "text" else GRAPHIC_RATIO
    bad = []
    if kind in ("graphic", "text"):
        bad += [
            f"map {name} {theme} vs {s} {v} < {need}"
            for s, v in entry.get("contrast", {}).items()
            if v < need
        ]
    if name == "map-water" and entry["deltaE"]["land"] < WATER_LAND_GAP:
        bad.append(f"map water vs land {theme} {entry['deltaE']['land']}")
    if name == "map-salt" and entry["deltaE"]["land"] < SALT_LAND_GAP:
        bad.append(f"map salt vs land {theme} {entry['deltaE']['land']}")
    return bad


def _map_violations(tokens: dict[str, Any], system: System) -> list[str]:
    bad = []
    for name, entry in tokens["dataviz"]["map"].items():
        if name in ("rules", "map-hillshade"):
            continue
        for theme in system.themes:
            bad += _map_entry_violations(name, entry["class"], theme, entry[theme])
    return bad


def _plate_violations(tokens: dict[str, Any], system: System) -> list[str]:
    bad = []
    for key, plate in tokens["plate"].items():
        if key == "rules":
            continue
        for theme in system.themes:
            if plate[theme]["contrast"] < PLATE_INK_RATIO:
                bad.append(f"plate {key} {theme} ink {plate[theme]['contrast']}")
            if plate[theme]["textureDeltaE"] < PLATE_TEXTURE_GAP:
                bad.append(f"plate {key} {theme} texture {plate[theme]['textureDeltaE']}")
    return bad


def _material_violations(name: str, entry: dict[str, Any], system: System) -> list[str]:
    bad = [
        f"specimen {name} {theme} frame"
        for theme in system.themes
        if not entry["frame"][theme]["edgeVisible"]
    ]
    bad += [
        f"specimen {name} {theme} {near['deltaE']} from {near['token']}"
        for theme, near in entry["nearestSemantic"].items()
        if near["deltaE"] < MATERIAL_RESERVED_GAP
    ]
    _, chroma, hue = oklch(entry["hex"])
    if BLUE_HUES[0] <= hue <= BLUE_HUES[1] and chroma >= INTERACTIVE_CHROMA:
        bad.append(f"specimen {name} chroma {chroma:.3f} reads as the interactive indigo")
    return bad


def _specimen_violations(tokens: dict[str, Any], system: System) -> list[str]:
    bad = []
    for name, entry in tokens["specimen"].items():
        if isinstance(entry, dict) and "material" in entry:
            bad += _material_violations(name, entry, system)
    return bad


def validate(tokens: dict[str, Any], system: System) -> list[str]:
    checks = (
        _colour_violations,
        _ramp_violations,
        _chart_violations,
        _family_violations,
        _map_violations,
        _plate_violations,
        _specimen_violations,
    )
    return [violation for check in checks for violation in check(tokens, system)]
