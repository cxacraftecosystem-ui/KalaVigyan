from typing import Any

DOT = {
    "tag": "svg",
    "attrs": {"viewBox": "0 0 10 10"},
    "children": [{"tag": "circle", "attrs": {"r": "4", "fill": "var(--ink-1)"}}],
}
WATER = {"formula": ["H", {"text": "2", "style": "sub"}, "O"], "name": "water"}
OXYGEN = {"formula": ["O", {"text": "2", "style": "sub"}], "name": None}
LINE = {"reactants": [WATER], "products": [OXYGEN]}
HEAD = {"figure": "chem:1", "number": "u0001", "title": "u0002", "titleId": "t-1", "dek": "u0003"}
EQUATION = {"label": "Water gives oxygen", "style": None, "line": LINE, "atoms": None, "notes": []}


def equation_card() -> dict[str, Any]:
    return {"kicker": "u0010", "title": "u0011", "mark": "u0012", "line": LINE, "why": "u0013"}


def chain_diagram() -> dict[str, Any]:
    step = {"part": "step", "player": "rp-blue", "step": 1, "figure": "chem:3", "figureLabel": "Fig. 4"}
    text = {"part": "text", "text": {"tag": "p", "style": "ch-t", "unit": "u0021"}}
    return {
        "drawing": None,
        "chain": {
            "headingId": "ch-h",
            "heading": "u0020",
            "links": [
                {"style": "ch-1", "kicker": "u0022", "parts": [text, step]},
                {"style": None, "kicker": "u0023", "parts": [{"part": "drawing", "drawing": DOT}]},
            ],
        },
    }


def structure_diagram() -> dict[str, Any]:
    molecule = {
        "drawing": DOT,
        "name": "Alizarin",
        "formula": ["C", {"text": "14", "style": "sub"}],
        "note": "closes a ring",
        "atomsTerm": "u0031",
        "atoms": "u0032",
        "recordTerm": "u0033",
        "cid": 6293,
    }
    return {
        "id": "fig3-en",
        "head": HEAD,
        "dekStyle": None,
        "scale": "u0030",
        "molecules": [molecule],
        "notes": [],
        "key": "Marked: the ring",
        "swatches": [{"colour": "--dye-lime", "label": "under the lime"}],
        "swatchNote": None,
    }


def molecule_3d() -> dict[str, Any]:
    model = {
        "key": "m1",
        "cid": 441564,
        "yaw": 0.416,
        "pitch": 0.25,
        "name": "Indican",
        "dialLabel": "Turn the indican model",
        "formula": ["C", {"text": "14", "style": "sub"}],
        "atoms": "14 carbon",
        "note": "In the leaf",
        "drawing": DOT,
    }
    key = [
        {"swatch": "--atom-c", "label": "Carbon"},
        {"swatch": "ring", "label": "Ringed"},
        {"swatch": None, "label": "3D"},
    ]
    return {"head": HEAD, "molecules": [model], "side": [], "key": key}


def material_cards() -> dict[str, Any]:
    card = {
        "swatch": "crystal",
        "role": "u0041",
        "name": "u0042",
        "local": "u0043",
        "botanical": None,
        "chemistry": "u0044",
        "facts": ["u0045"],
    }
    return {
        "id": "materials",
        "headingId": "mat-h",
        "heading": "Six materials",
        "intro": "u0040",
        "cards": [card],
        "after": [{"component": "kutch-ajrakh/materials/natural-dye-materials-photo"}],
    }


def model_explainer() -> dict[str, Any]:
    still = {
        "width": "wide",
        "heading": "u0051",
        "lede": "u0052",
        "drawing": DOT,
        "phase": "u0053",
        "numbers": "u0054",
    }
    controls = {
        "play": "Play",
        "playIcon": DOT,
        "sliderLabel": "Time through the dip",
        "sliderMax": 1000,
        "sliderAt": 750,
        "ticks": ["In the vat", "In the air"],
    }
    model = {
        "title": "Inside one fibre",
        "height": 760,
        "stylesheet": ".kx{margin:0}",
        "document": "<!doctype html>",
        "sandbox": "allow-scripts",
    }
    return {
        "head": HEAD,
        "badge": "Model-built explainer",
        "badgeNote": "Drawn by the model",
        "stills": [still],
        "controls": controls,
        "key": [{"style": "ox", "icon": DOT, "label": "Oxygen"}],
        "model": model,
    }


def process_replay() -> dict[str, Any]:
    return {
        "heading": "u1055",
        "play": "Watch it being made",
        "understood": "u0060",
        "angles": "u0061",
        "stages": [{"label": "Understood", "detail": "Kutch Ajrakh", "startMs": 0, "endMs": 600}],
        "sourcesKicker": "u0062",
        "sources": [{"title": "GI Journal No. 188", "grade": "A"}],
        "sectionsKicker": "u0063",
        "sections": [{"title": "Tannin first", "made": ["Drawing the molecules"]}],
        "ready": "u0064",
    }


def reaction_step(name: str, first: int) -> dict[str, Any]:
    lane = {
        "part": "lane",
        "label": "Species in this step",
        "items": [
            {
                "item": "species",
                "swatch": "clear",
                "name": ["Water"],
                "formula": None,
                "state": [],
                "cid": None,
            },
            {"item": "arrow", "label": "heated"},
        ],
    }
    text = {
        "kicker": f"u{first:04d}",
        "heading": f"u{first + 1:04d}",
        "paragraphs": [f"u{first + 2:04d}"],
        "bond": None,
        "link": None,
        "conditions": [],
        "differs": None,
    }
    chemistry = {"parts": [lane, {"part": "none", "unit": f"u{first + 3:04d}"}]}
    return {"name": name, "text": text, "chemistry": chemistry, "scene": None}


def reaction_player() -> dict[str, Any]:
    return {
        "id": "rp-red",
        "track": "red",
        "head": HEAD,
        "current": 2,
        "steps": [reaction_step("Tannin first", 100), reaction_step("The mordant", 110)],
        "scenes": [DOT],
        "key": None,
        "status": "u0099",
    }


def dip_player() -> dict[str, Any]:
    phases = [
        {"pose": pose, "drawing": DOT, "kicker": f"u07{index}0", "text": f"u07{index}1"}
        for index, pose in enumerate(("vat", "lifted", "air"))
    ]
    return {
        "id": "fig1",
        "head": HEAD,
        "phase": "u0700",
        "scene": DOT,
        "stripLabel": "Three phases of one dip",
        "phases": phases,
        "dipAgain": "Dip again",
        "status": "u0790",
        "dipsLabel": "u0791",
        "dips": ["--dip-1", "--dip-2"],
        "equation": EQUATION,
    }


def stage_entry(name: str, first: int) -> dict[str, Any]:
    return {
        "name": name,
        "english": name.title(),
        "local": True,
        "after": "pale yellow",
        "number": f"u{first:04d}",
        "heading": f"u{first + 1:04d}",
        "texts": [f"u{first + 2:04d}"],
        "why": None,
        "differs": None,
        "afterSentence": None,
        "materials": None,
    }


def stage_player() -> dict[str, Any]:
    return {
        "key": "a",
        "head": HEAD,
        "drawing": DOT,
        "restName": "u0800",
        "play": "Play the stages",
        "source": "u0801",
        "stages": [stage_entry("saaj", 810), stage_entry("kasanu", 820)],
        "finish": {"heading": "u0830", "paragraphs": ["u0831"]},
        "afterLabel": "Cloth after",
    }


def choice_toggle() -> dict[str, Any]:
    options = [
        {
            "value": value,
            "label": value.title(),
            "heading": f"u09{index}0",
            "parts": [{"part": "text", "unit": f"u09{index}1"}],
        }
        for index, value in enumerate(("madder", "alizarin"))
    ]
    chip = {"formula": ["NaOH"], "name": "Caustic soda", "cid": 14798, "source": None}
    return {
        "experiment": "red",
        "questionId": "q-red",
        "question": "u0900",
        "options": options,
        "textParts": [{"part": "formulas", "option": None, "chips": [chip]}],
        "visualParts": [
            {
                "part": "switch",
                "hook": "pa",
                "label": ["Let the ", {"text": "pa", "style": "i"}, " touch"],
                "description": "A warning",
            }
        ],
    }


def experiment_lab() -> dict[str, Any]:
    experiments = [
        {"key": key, "label": label, "toggle": {"component": f"kutch-ajrakh/chemistry/what-if-{key}"}}
        for key, label in (("blue", "The blue vat"), ("red", "The red bath"))
    ]
    return {
        "id": "lab",
        "figure": "pt:8",
        "number": "u0950",
        "pickerLabel": "Experiment",
        "experiments": experiments,
    }
