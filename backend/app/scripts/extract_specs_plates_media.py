from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.core.errors import InvalidInput

from .extract_specs_files import Extractor, Found
from .extract_specs_markup import Element, has_classes, is_tag
from .extract_specs_parts import (
    drawing,
    held_or_unit,
    held_text,
    held_text_or_unit,
    shown_day,
    slot_unit,
    url_reference,
)

__all__ = ["MEDIA_EXTRACTORS", "clock"]

AI_CAPTION = re.compile(
    r"(?P<subject>.+)\. Drawn from sentences? (?P<numbers>\d+(, \d+)*) of this section; not a photograph\."
)
AI_MADE = re.compile(r"AI (illustration|video) · (.+ · )?(?P<day>\d{1,2} [A-Z][a-z]{2} \d{4})")
AI_LABEL_PREFIX = "AI illustration: "
SCENE_LABEL = re.compile(r"Scene (?P<n>\d+): (?P<title>.+?)(?P<forming>, arriving)?")
MINUTES = re.compile(r"Listen · (?P<minutes>\d+) min")
MILLISECONDS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60


def clock(milliseconds: int) -> str:
    seconds = round(milliseconds / MILLISECONDS_PER_SECOND)
    return f"{seconds // SECONDS_PER_MINUTE}:{seconds % SECONDS_PER_MINUTE:02d}"


def ai_illustration(found: Found) -> dict[str, Any]:
    figure = found.element
    caption = figure.first(is_tag("figcaption"))
    said = AI_CAPTION.fullmatch(caption.elements()[0].text())
    if said is None:
        raise InvalidInput(f"{found.component.label}: the caption does not say what it is drawn from")
    if figure.first(has_classes("ai-art")).attrs["aria-label"] != AI_LABEL_PREFIX + said.group("subject"):
        raise InvalidInput(f"{found.component.label}: the picture's name and caption differ")
    button = caption.first(is_tag("button"))
    if button.attrs["data-dl-ill"] != figure.attrs["data-sym"]:
        raise InvalidInput(f"{found.component.label}: the download names another drawing")
    return {
        "section": int(figure.attrs["data-sec"]),
        "art": _art_frame(figure.first(is_tag("svg"))),
        "subject": said.group("subject"),
        "sentences": [int(number) for number in said.group("numbers").split(", ")],
        "made": shown_day(caption.first(has_classes("meta")).text(), AI_MADE),
        "downloadName": button.attrs["data-name"],
    }


def ai_video(found: Found) -> dict[str, Any]:
    figure = found.element
    caption = figure.first(is_tag("figcaption"))
    button = caption.first(is_tag("button"))
    return {
        "section": int(figure.attrs["data-sec"]),
        "art": drawing(figure.first(is_tag("svg"))),
        "phase": slot_unit(figure.first(has_classes("vid-phase"))),
        "playback": _playback(figure),
        "caption": held_text(caption.elements()[0], found.sources),
        "made": shown_day(caption.first(has_classes("meta")).text(), AI_MADE),
        "downloadKey": button.attrs["data-dl-video"],
        "downloadName": button.attrs["data-name"],
    }


def film(found: Found) -> dict[str, Any]:
    block = found.element
    strip = block.first(has_classes("film-strip")).all(is_tag("button"))
    tags = [tag.text() for tag in block.first(has_classes("tagline")).elements()]
    if block.first(has_classes("film-stage")).first(has_classes("ai-tag")).text() != tags[0]:
        raise InvalidInput("The film's stage carries its first tag")
    return {
        "title": slot_unit(block.first(has_classes("film-h")).first(is_tag("h3"))),
        "meta": slot_unit(block.first(has_classes("film-meta"))),
        "sceneLabel": slot_unit(block.first(has_classes("film-scene-l"))),
        "subtitle": slot_unit(block.first(has_classes("film-sub"))),
        "scenes": [_scene(number, button) for number, button in enumerate(strip, start=1)],
        "playback": _playback(block),
        "tags": tags,
        "note": block.first(has_classes("fl-text")).text().strip(),
        "downloadName": block.first(is_tag("button", "dl")).attrs["data-name"],
        "subtitlesName": block.all(is_tag("button", "dl"))[1].attrs["data-name"],
    }


def _scene(number: int, button: Element) -> dict[str, Any]:
    said = SCENE_LABEL.fullmatch(button.attrs["aria-label"])
    if said is None or int(said.group("n")) != number:
        raise InvalidInput(f"Scene {number} is not named in order")
    return {
        "art": _art_frame(button.first(is_tag("svg"))),
        "title": said.group("title"),
        "field": button.first(has_classes("fs-t")).text(),
        "forming": button.has_class("forming"),
    }


def comic(found: Found) -> dict[str, Any]:
    strip = found.element
    panels = []
    for panel in strip.all(is_tag("li", "panel")):
        caption = panel.first(has_classes("pcap"))
        told = [child for child in caption.children if not _is_counter(child)]
        panels.append(
            {
                "layout": " ".join(cls for cls in panel.classes if cls != "panel") or None,
                "caption": held_or_unit(told, found.sources),
                "art": drawing(panel.first(is_tag("svg"))),
                "tag": panel.first(has_classes("ai-tag")).text(),
            }
        )
    return {"label": strip.attrs["aria-label"], "panels": panels}


def audio_player(found: Found) -> dict[str, Any]:
    block = found.element
    button = block.first(is_tag("button"))
    said = MINUTES.fullmatch(button.text())
    if said is None:
        raise InvalidInput("The listen button says how many minutes the page takes")
    return {
        "title": slot_unit(block.first(is_tag("h3"))),
        "description": slot_unit(block.first(has_classes("kv-sub-d"))),
        "action": "Listen",
        "minutes": int(said.group("minutes")),
        "playerId": button.attrs["aria-controls"],
    }


def voice(found: Found) -> dict[str, Any]:
    element = found.element
    if element.has_class("kv-coda"):
        return {"setting": "coda", "coda": _coda(element)}
    kicker = element.first(has_classes("kicker"))
    echo = element.all(has_classes("voice-q2"))
    testimony = {
        "kicker": slot_unit(kicker),
        "kickerId": kicker.attrs["id"],
        "evidence": element.first(has_classes("voice-ev")).text().strip(),
        "quote": slot_unit(element.first(has_classes("voice-q")).first(is_tag("p"))),
        "credit": slot_unit(element.first(has_classes("voice-credit"))),
        "meta": slot_unit(element.first(has_classes("voice-meta"))),
        "echo": _echo(echo[0], found) if echo else None,
    }
    return {"setting": "testimony", "testimony": testimony}


def _echo(quote: Element, found: Found) -> dict[str, Any]:
    return {
        "quote": slot_unit(quote.first(is_tag("p"))),
        "attribution": held_text_or_unit(quote.first(is_tag("footer")), found.sources),
    }


def _coda(section: Element) -> dict[str, Any]:
    cloth = section.first(is_tag("svg"))
    fills = [rect.attrs["fill"] for rect in cloth.elements()]
    card = section.first(is_tag("figure"))
    return {
        "label": section.attrs["aria-label"],
        "viewBox": cloth.attrs["viewBox"],
        "tile": url_reference(fills[0]),
        "weave": url_reference(fills[1]),
        "kicker": slot_unit(card.first(has_classes("lc-k"))),
        "quote": slot_unit(card.first(is_tag("blockquote")).first(is_tag("p"))),
        "caption": slot_unit(card.first(is_tag("figcaption"))),
        "note": slot_unit(card.first(has_classes("kv-coda-n"))),
    }


def _art_frame(svg: Element) -> dict[str, Any]:
    use = svg.first(is_tag("use"))
    return {
        "symbol": use.attrs["href"].removeprefix("#"),
        "viewBox": svg.attrs["viewBox"],
        "width": int(use.attrs["width"]),
        "height": int(use.attrs["height"]),
    }


def _playback(element: Element) -> dict[str, Any]:
    scrubber = element.first(is_tag("input"))
    shown = {
        "durationMs": int(scrubber.attrs["max"]),
        "stepMs": int(scrubber.attrs["step"]),
        "restMs": int(scrubber.attrs["value"]),
    }
    if (
        element.first(has_classes("vid-time")).text()
        != f"{clock(shown['restMs'])} / {clock(shown['durationMs'])}"
    ):
        raise InvalidInput("The player's clock shows another time than its position")
    return shown


def _is_counter(node: object) -> bool:
    return isinstance(node, Element) and (node.has_class("pnum") or node.has_class("vh"))


MEDIA_EXTRACTORS: Mapping[str, Extractor] = {
    "ai_illustration": ai_illustration,
    "ai_video": ai_video,
    "film": film,
    "comic": comic,
    "audio_player": audio_player,
    "voice": voice,
}
