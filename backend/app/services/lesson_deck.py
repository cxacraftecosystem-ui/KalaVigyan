from __future__ import annotations

import base64
import uuid
from collections.abc import Iterable, Mapping
from html import escape

from app.core.clock import INDIA_TZ
from app.data.export_assets import REVEAL_VERSION, reveal_licence, reveal_script, reveal_styles
from app.research.citation_export import CitationEntry
from app.research.export_text import References, picture_credit
from app.research.lesson_words import LessonWords, lesson_words
from app.research.lessons import LessonPack, Slide
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, RIGHT_TO_LEFT_SCRIPTS

from .export_pictures import Picture

__all__ = ["DECK_POLICY", "lesson_deck"]

DECK_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
    "base-uri 'none'; form-action 'none'"
)
REVEAL_SETTINGS = (
    '{"hash":false,"slideNumber":true,"transition":"fade","center":false,"width":1280,"height":720}'
)
UNSAFE_IN_SCRIPT = ("</script", "<!--")
DECK_STYLES = """
:root{--kv-ink:#111827;--kv-muted:#4b5563;--kv-accent:#5b21b6;--kv-paper:#ffffff}
html,body{margin:0;background:var(--kv-paper)}
.reveal{font-family:"Noto Sans","Noto Sans Devanagari","Noto Sans Bengali","Noto Sans Tamil","Noto Sans Telugu",
"Noto Sans Gujarati","Noto Sans Kannada","Noto Sans Malayalam","Noto Sans Oriya","Noto Sans Gurmukhi",
"Noto Naskh Arabic",system-ui,sans-serif;color:var(--kv-ink);font-size:30px}
.reveal .slides section{text-align:start;height:100%;box-sizing:border-box;padding:24px 8px;overflow-y:auto}
.reveal h1,.reveal h2{color:var(--kv-accent);font-weight:700;line-height:1.15;margin:0 0 20px}
.reveal h1{font-size:2.1em}.reveal h2{font-size:1.4em}
.kv-meta{color:var(--kv-muted);font-size:.8em}
.kv-body{display:grid;grid-template-columns:minmax(0,1fr);gap:28px;align-items:start}
.kv-body.kv-pictured{grid-template-columns:minmax(0,3fr) minmax(0,2fr)}
.kv-body.kv-lede{margin-top:28px}
.kv-body ul,.kv-list{margin:0;padding-inline-start:1.1em}
.kv-body li,.kv-list li{margin:0 0 .45em;line-height:1.35;overflow-wrap:anywhere}
.kv-cite{color:var(--kv-accent);font-size:.7em;white-space:nowrap}
figure{margin:0}figure img{max-width:100%;max-height:440px;object-fit:contain}
figcaption,.kv-small{color:var(--kv-muted);font-size:.55em;line-height:1.35;overflow-wrap:anywhere}
.kv-list{font-size:.62em}
.kv-options{list-style:upper-alpha}
.kv-answer{color:var(--kv-accent)}
.reveal a{color:var(--kv-accent);overflow-wrap:anywhere}
"""


def lesson_deck(pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> bytes:
    script = reveal_script()
    if any(unsafe in script.lower() for unsafe in UNSAFE_IN_SCRIPT):
        raise ValueError(f"reveal.js {REVEAL_VERSION} holds text that would end its script early")
    words = lesson_words(pack.language)
    script_name = ANSWER_LANGUAGE_SPECS[pack.language].script
    direction = "rtl" if script_name in RIGHT_TO_LEFT_SCRIPTS else "ltr"
    slides = "\n".join(_slide(slide, pack, refs, pictures, words) for slide in pack.slides)
    page = (
        f'<!doctype html>\n<html lang="{pack.language}" dir="{direction}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{DECK_POLICY}">\n'
        f'<meta name="generator" content="KalaVigyan with reveal.js {REVEAL_VERSION}">\n'
        f"<title>{escape(pack.title)}</title>\n<style>{reveal_styles()}</style>\n<style>{DECK_STYLES}</style>\n"
        f'</head>\n<body>\n<div class="reveal"><div class="slides">\n{slides}\n</div></div>\n'
        f'<template id="reveal-licence">{escape(reveal_licence())}</template>\n'
        f"<script>{script}</script>\n<script>Reveal.initialize({REVEAL_SETTINGS});</script>\n</body>\n</html>\n"
    )
    return page.encode("utf-8")


def _slide(
    slide: Slide,
    pack: LessonPack,
    refs: References,
    pictures: Mapping[uuid.UUID, Picture],
    words: LessonWords,
) -> str:
    kind = slide.kind
    if kind == "TITLE":
        body = f"<h1>{escape(slide.title)}</h1>{_meta(pack)}{_opening(slide, refs)}"
    elif kind == "SECTION":
        body = f"<h2>{escape(slide.title)}</h2>{_section(slide, refs, pictures)}"
    elif kind == "QUIZ":
        body = _question(slide, pack, refs, words)
    elif kind == "READING":
        items = (refs.of_source(item.source.id) for item in pack.reading_list)
        body = f"<h2>{escape(slide.title)}</h2>{_references(items)}"
    else:
        items = (refs.of_source(source.id) for source in pack.sources)
        body = f"<h2>{escape(slide.title)}</h2>{_references(items)}"
    return f'<section data-kind="{kind}" data-number="{slide.number}">{body}</section>'


def _meta(pack: LessonPack) -> str:
    made = pack.created_at.astimezone(INDIA_TZ).date().isoformat()
    parts = [pack.craft.name if pack.craft else None, made]
    return f'<p class="kv-meta">{escape(" · ".join(part for part in parts if part))}</p>'


def _bullets(slide: Slide, refs: References) -> str:
    return "".join(
        f'<li>{escape(sentence.text)} <span class="kv-cite">{refs.sentence_marker(sentence)}</span></li>'
        for sentence in slide.bullets
    )


def _opening(slide: Slide, refs: References) -> str:
    return f'<div class="kv-body kv-lede"><ul>{_bullets(slide, refs)}</ul></div>' if slide.bullets else ""


def _section(slide: Slide, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> str:
    bullets = _bullets(slide, refs)
    picture = pictures.get(slide.image.id) if slide.image is not None else None
    if slide.image is None or picture is None:
        return f'<div class="kv-body"><ul>{bullets}</ul></div>'
    data = base64.b64encode(picture.data).decode("ascii")
    figure = (
        f'<figure><img src="data:image/jpeg;base64,{data}" alt="{escape(slide.image.alt)}">'
        f"<figcaption>{escape(picture_credit(slide.image))}</figcaption></figure>"
    )
    return f'<div class="kv-body kv-pictured"><ul>{bullets}</ul>{figure}</div>'


def _question(slide: Slide, pack: LessonPack, refs: References, words: LessonWords) -> str:
    if pack.quiz is None or slide.question is None:
        raise ValueError(f"slide {slide.number} asks a question the lesson does not hold")
    question = pack.quiz.questions[slide.question]
    options = "".join(f"<li>{escape(option.text)}</li>" for option in question.options)
    key = question.options[question.answer]
    letter = chr(ord("A") + question.answer)
    answer = (
        f'<p class="fragment kv-answer">{letter}. {escape(key.text)}</p>'
        f'<p class="fragment kv-small">{escape(key.sentence.text)} {refs.sentence_marker(key.sentence)}</p>'
    )
    notes = f'<aside class="notes">{escape(words.answers)}: {letter}. {escape(key.text)}</aside>'
    return (
        f"<h2>{escape(slide.title)}</h2><p>{escape(question.prompt)}</p>"
        f'<ol class="kv-options">{options}</ol>{answer}{notes}'
    )


def _references(entries: Iterable[CitationEntry]) -> str:
    items = "".join(f'<li value="{entry.number}">{escape(entry.apa)}</li>' for entry in entries)
    return f'<ol class="kv-list">{items}</ol>'
