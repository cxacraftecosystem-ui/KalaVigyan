from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.varLib import instancer

from webfonts.ranges import (
    KEPT_FEATURES,
    NEWSREADER_COMMIT,
    NEWSREADER_PATH,
    WEIGHT_RANGE,
    Face,
    Output,
    codepoints,
)

__all__ = ["build_face", "features_of", "read_source"]

RAW_ROOT = "https://raw.githubusercontent.com/google/fonts"
FETCH_TIMEOUT_SECONDS = 60
UNHINTED_PREP = ["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"]
GASP_ALL_SIZES = {0xFFFF: 15}


def git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(content) + content, usedforsecurity=False).hexdigest()


def read_source(face: Face, cache: Path) -> bytes:
    cached = cache / face.source
    if cached.is_file():
        content = cached.read_bytes()
    else:
        url = f"{RAW_ROOT}/{NEWSREADER_COMMIT}/{NEWSREADER_PATH}/{urllib.parse.quote(face.source)}"
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
            content = response.read()
        cache.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(content)
    found = git_blob(content)
    if found != face.blob:
        raise ValueError(f"{face.source} is blob {found}, not the pinned {face.blob}")
    return content


def _subset_options() -> subset.Options:
    options = subset.Options()
    options.layout_features = list(KEPT_FEATURES)
    options.hinting = False
    options.notdef_outline = True
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.glyph_names = False
    options.flavor = "woff2"
    return options


def _mark_unhinted(font: TTFont) -> None:
    program = ttProgram.Program()
    program.fromAssembly(UNHINTED_PREP)
    prep = newTable("prep")
    prep.program = program
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = dict(GASP_ALL_SIZES)
    font["prep"] = prep
    font["gasp"] = gasp


def build_face(output: Output, source: bytes) -> bytes:
    font = instancer.instantiateVariableFont(
        TTFont(BytesIO(source), recalcTimestamp=False), {"wght": WEIGHT_RANGE}
    )
    options = _subset_options()
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(codepoints(output.spans)))
    subsetter.subset(font)
    _mark_unhinted(font)
    written = BytesIO()
    font.flavor = options.flavor
    font.recalcTimestamp = False
    font.save(written)
    return written.getvalue()


def features_of(content: bytes) -> list[str]:
    font = TTFont(BytesIO(content))
    tags = set()
    for table in ("GSUB", "GPOS"):
        if table in font and font[table].table.FeatureList is not None:
            tags.update(record.FeatureTag for record in font[table].table.FeatureList.FeatureRecord)
    return sorted(tags)
