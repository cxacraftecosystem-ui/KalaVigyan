from typing import Any

from app.scripts.write_component_homes import HOMES_FILE, homes_text
from app.services.document_components_homes import (
    ComponentHome,
    FrameStep,
    HomeSource,
    authored_home_source,
    component_homes,
    frame_steps,
    kind_scopes,
)

CHAIN = "test-craft/chemistry/chain"
LAB = "test-craft/chemistry/lab"
TOGGLE = "test-craft/chemistry/toggle"
CHART = "test-craft/chemistry/chart"
AUTHORED = "Kutch-Ajrakh"


def _source(
    shell: str, fragments: dict[str, str], specs: dict[str, dict[str, Any]], kinds: dict[str, str]
) -> HomeSource:
    return HomeSource(shell=shell, fragments=fragments, specs=specs, kinds=kinds, native=frozenset(specs))


def _chain_source() -> HomeSource:
    shell = (
        '<main id="kv-main"><section class="kv-ch" id="chem"><div class="bx bx-ask"><section class="screen">'
        f'<div class="kv-chain kv-wrap"><kv-slot component="{CHAIN}"></kv-slot></div>'
        "</section></div></section></main>"
    )
    fragments = {CHAIN: '<section class="chain" aria-labelledby="ch-h"><h2 id="ch-h">Chain</h2></section>'}
    return _source(
        shell, fragments, {CHAIN: {"chain": {"heading": "u0001"}, "drawing": None}}, {CHAIN: "diagram"}
    )


def test_a_component_is_at_home_in_the_scope_and_the_frame_of_its_authored_slot() -> None:
    home = component_homes(_chain_source())[CHAIN]
    assert home == ComponentHome(
        kind="diagram",
        scope="ask",
        frame=(
            FrameStep(("screen",), box=True),
            FrameStep(("kv-chain",), box=False),
            FrameStep(("kv-wrap",), box=True),
        ),
        root="section.chain",
    )


def test_a_native_component_inside_a_fragment_keeps_the_fragments_ancestors() -> None:
    shell = (
        '<div class="bx bx-pt"><div class="screen"><section class="sec wrap" id="lab-sec">'
        f'<kv-slot component="{LAB}"></kv-slot></section></div></div>'
    )
    fragments = {
        LAB: f'<div class="wif" id="lab"><img src="a.png" alt=""><div class="lab-panel"><kv-slot component="{TOGGLE}"></kv-slot></div></div>',
        TOGGLE: '<div class="lab-panel-toggle"><svg viewBox="0 0 2 2"><path d="M0 0"/></svg></div>',
    }
    source = HomeSource(
        shell=shell,
        fragments=fragments,
        specs={TOGGLE: {"options": ["a", "b"]}},
        kinds={LAB: "experiment_lab", TOGGLE: "choice_toggle"},
        native=frozenset({TOGGLE}),
    )
    homes = component_homes(source)
    assert homes[LAB].frame == (
        FrameStep(("screen",), True),
        FrameStep(("sec",), False),
        FrameStep(("wrap",), True),
    )
    assert homes[LAB].root == "div#lab.wif"
    assert [step.classes for step in homes[TOGGLE].frame] == [
        ("screen",),
        ("sec",),
        ("wrap",),
        ("wif",),
        ("lab-panel",),
    ]
    assert [step.box for step in homes[TOGGLE].frame] == [True, False, True, False, False]


def test_a_component_a_native_view_places_shares_its_parents_scope() -> None:
    source = _chain_source()
    specs = {CHAIN: {"chain": {"figure": CHART}}, CHART: {"form": "rows"}}
    nested = HomeSource(
        source.shell,
        {**source.fragments, CHART: "<svg></svg>"},
        specs,
        {**source.kinds, CHART: "chart"},
        frozenset(specs),
    )
    home = component_homes(nested)[CHART]
    assert (home.scope, home.frame, home.within, home.root) == ("ask", (), CHAIN, "svg")


def test_a_home_inside_a_language_panel_keeps_the_panel_s_language_but_not_its_hidden_state() -> None:
    shell = (
        '<div class="bx bx-rm"><div class="screen"><div class="lang-panel" lang="hi" data-ui-lang="hi" '
        f'hidden><div class="spread railed"><div class="main hi-prose"><kv-slot component="{CHAIN}">'
        "</kv-slot></div></div></div></div></div>"
    )
    source = _source(
        shell, {CHAIN: '<figure class="fig"></figure>'}, {CHAIN: {"chain": None}}, {CHAIN: "diagram"}
    )
    frame = component_homes(source)[CHAIN].frame
    assert frame[1] == FrameStep(("lang-panel",), box=False, attrs=(("lang", "hi"), ("data-ui-lang", "hi")))
    assert [step.attrs for step in frame if step.classes != ("lang-panel",)] == [(), (), ()]
    authored = component_homes(authored_home_source(AUTHORED))
    hindi = authored["shared/chemistry/alizarin-purpurin-structures-hindi"].frame
    assert [dict(step.attrs) for step in hindi if step.attrs] == [{"lang": "hi", "data-ui-lang": "hi"}]


def test_the_reading_column_keeps_its_boxes_and_a_margin_does_not() -> None:
    column = frame_steps([("screen",), ("spread", "railed"), ("main", "prose")])
    margin = frame_steps([("screen",), ("spread", "railed"), ("margin", "note")])
    assert [step.box for step in column] == [True, True, True]
    assert [step.box for step in margin] == [True, False, False]


def test_the_authored_page_gives_each_borrowed_chemistry_figure_its_own_home() -> None:
    homes = component_homes(authored_home_source(AUTHORED))
    chain = homes["shared/chemistry/indigo-leaf-to-cloth-chain"]
    player = homes["shared/chemistry/indigo-reduction-player"]
    vat = homes["shared/chemistry/indigo-vat-dip"]
    assert (chain.scope, [s.classes for s in chain.frame]) == (
        "ask",
        [("screen",), ("kv-chain",), ("kv-wrap",)],
    )
    assert (player.scope, [s.classes for s in player.frame], player.root) == (
        "chem",
        [("screen",), ("wrap",), ("sec",)],
        "figure#rp-blue.rp.rx-player",
    )
    assert [(s.classes, s.box) for s in vat.frame] == [
        (("screen",), True),
        (("wrap",), True),
        (("opener",), False),
        (("op-r",), False),
    ]


def test_a_kind_lists_each_scope_its_authored_specs_are_drawn_in() -> None:
    source = authored_home_source(AUTHORED)
    scopes = kind_scopes(source, component_homes(source))
    assert {"scope": "ask", "keys": ["chain"]} in scopes["diagram"]
    assert {"scope": "mb", "keys": ["drawing"]} in scopes["diagram"]
    assert {entry["scope"] for entry in scopes["reaction_player"]} == {"chem"}


def test_the_web_app_holds_the_homes_the_authored_pages_give() -> None:
    assert HOMES_FILE.read_bytes().decode("utf-8") == homes_text()
