from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.composer.material_cards import CardChoice
from app.data.craft_text import fold
from app.research.blocks_matter import Molecule3dBlock, ReactionPlayerBlock, ReactionStep
from app.research.craft_chapters import Borrowed
from app.research.craft_page import OverviewSection
from app.research.craft_parts import PlatePart
from app.research.reactions import ReactionSpecies, mhchem_equation, reaction_level
from app.research.vocabulary import FACT_LEVELS
from app.science.reaction_colours import step_colours
from app.science.reaction_player import reaction_player
from app.science.records import CompoundRecord, KnownClaim

from .chapter_balance import inferred_step, named_compounds
from .chapter_context import ChapterContext
from .chapter_draft import ChapterDraft, Drafted
from .chapter_figures import CHEMISTRY_FIGURES, signature_figures
from .chapter_plates import PicturePlan
from .chapter_prose import prose_blocks
from .craft_matter import CraftMatter, MaterialRows
from .curated_index import IndexReaction
from .material_cards import CardOffer, material_card, merged_materials

__all__ = ["CARD_FACTS_MAX", "CARD_ROLES", "chem_chapter"]

KEY = "chem"
PLAYER_ID = "chem.reactions"
CARD_ROLES = frozenset({"DYE", "MORDANT", "RESIST", "BINDER", "FLUX"})
CARD_FACTS_MAX = 3
HEALTH = "HEALTH"
CURATED = "CURATED"


def chem_chapter(ctx: ChapterContext, sections: Sequence[OverviewSection], plan: PicturePlan) -> ChapterDraft:
    matter = ctx.matter()
    items = [Drafted.of_block(block) for block in prose_blocks(ctx, KEY, sections)]
    items += [
        Drafted.of_block(figure, figure={"kind": figure.kind})
        for figure in signature_figures(ctx, CHEMISTRY_FIGURES, KEY)
    ]
    player = _player(ctx)
    if player is not None:
        borrowed = _borrowed(ctx, player)
        values = {"mechanism": _mechanism(ctx, player)}
        items.append(Drafted.of_block(player, figure=values, borrowed=borrowed))
    items += _explainers(ctx)
    items += [
        Drafted.of_block(block, figure={"name": block.name}) for block in _molecules(ctx, matter, player)
    ]
    items += [Drafted.of_block(card) for card in _cards(ctx, matter)]
    items += [
        Drafted.of_part(PlatePart(kind="plate", plate=p.plate))
        for p in plan.plates(KEY, ("PLATE", "MATERIAL"))
    ]
    return ChapterDraft(KEY, plan.opener(KEY), items)


def _player(ctx: ChapterContext) -> ReactionPlayerBlock | None:
    own = reaction_player(ctx.process(), block_id=PLAYER_ID)
    steps = list(own.steps) if own is not None else []
    played = {step.reaction_id for step in steps}
    steps += [step for step in _family_steps(ctx) if step.reaction_id not in played]
    if not steps:
        return None
    named = named_compounds(list(ctx.rows.compounds.values()), _material_compounds(ctx))
    steps = [inferred_step(step, named) for step in steps]
    notes = list(own.notes) if own is not None else []
    return ReactionPlayerBlock(
        id=PLAYER_ID, kind="reaction_player", version=1, reuse=None, steps=steps, notes=notes
    )


def _family_steps(ctx: ChapterContext) -> list[ReactionStep]:
    family = ctx.rows.family
    if family is None or family.index is None:
        return []
    names = _craft_names(ctx)
    steps = []
    for reaction in family.index.reactions:
        species = [*reaction.reactants, *reaction.products]
        if not any(fold(item.name) in names for item in species):
            continue
        step = _family_step(ctx, family.slug, reaction)
        if step is not None:
            steps.append(step)
    return steps


def _family_step(ctx: ChapterContext, slug: str, reaction: IndexReaction) -> ReactionStep | None:
    claims = [
        fact for claim_id in reaction.claim_ids if (fact := ctx.known(claim_id)) and fact.level in FACT_LEVELS
    ]
    if not claims:
        return None
    species = [
        ReactionSpecies(role=role, formula=item.formula, name=item.name, coefficient=None, compound_id=None)
        for role, side in (("REACTANT", reaction.reactants), ("PRODUCT", reaction.products))
        for item in side
    ]
    citations = list({c.id: c for claim in claims for c in claim.citations}.values())
    level, _ = reaction_level([c.level for c in citations], balanced=False, species=species)
    label = (
        " and ".join(item.name for item in reaction.reactants)
        + " to "
        + " and ".join(item.name for item in reaction.products)
    )
    return ReactionStep(
        reaction_id=reaction.reaction_id
        or uuid.uuid5(uuid.NAMESPACE_URL, f"family-reaction:{slug}:{reaction.key}"),
        stage_id=None,
        kind=reaction.kind,
        label=label[:200],
        species=species,
        equation=mhchem_equation(species),
        balanced=False,
        level=level,
        citations=citations,
        colours=step_colours(citations),
    )


def _craft_names(ctx: ChapterContext) -> set[str]:
    names = {fold(material.name) for material in ctx.records.process.materials}
    curated = ctx.records.curated
    if curated is not None:
        for item in curated.materials:
            names |= {fold(item.name), *(fold(name) for name in item.local_names)}
    names |= {fold(compound.name) for compound in ctx.rows.compounds.values()}
    return {name for name in names if name}


def _borrowed(ctx: ChapterContext, player: ReactionPlayerBlock) -> tuple[Borrowed, ...]:
    family = ctx.rows.family
    if family is None:
        return ()
    own = {step.reaction_id for step in player.steps if step.stage_id is not None}
    if all(step.reaction_id in own for step in player.steps):
        return ()
    return (Borrowed(scope="FAMILY", slug=family.slug, label=family.label),)


def _mechanism(ctx: ChapterContext, player: ReactionPlayerBlock) -> str:
    return player.steps[0].label if len(player.steps) == 1 else f"The reactions of {ctx.craft_name}"


def _explainers(ctx: ChapterContext) -> list[Drafted]:
    found = []
    for stored in ctx.rows.explainers:
        cited = {uuid.UUID(citation.claim_id) for citation in stored.block.citations()}
        if stored.block.hidden or not cited <= set(ctx.claims):
            continue
        found.append(
            Drafted.of_block(
                stored.block.model_copy(update={"id": f"chem.explainer-{stored.term_key}"}),
                piece_id=stored.piece_id,
            )
        )
    return found


def _molecules(
    ctx: ChapterContext, matter: CraftMatter, player: ReactionPlayerBlock | None
) -> list[Molecule3dBlock]:
    named = [
        s.compound_id for step in (player.steps if player else []) for s in step.species if s.compound_id
    ]
    named += [m.compound.id for m in merged_materials(matter.materials) if m.compound is not None]
    blocks = []
    for compound_id in dict.fromkeys(named):
        compound = matter.compounds.get(compound_id)
        if (
            compound is None
            or compound.pubchem_cid is None
            or compound.pubchem_cid not in ctx.rows.conformers
        ):
            continue
        source_id = str(compound.source_id) if compound.source_id else None
        if source_id is None or source_id not in ctx.rows.record_sources:
            continue
        blocks.append(
            Molecule3dBlock(
                id=f"chem.molecule-{compound.pubchem_cid}",
                kind="molecule_3d",
                version=1,
                reuse=None,
                compound_id=compound.id,
                pubchem_cid=compound.pubchem_cid,
                name=compound.name,
                formula=compound.formula,
                source_id=source_id,
            )
        )
    return blocks


def _cards(ctx: ChapterContext, matter: CraftMatter) -> list:
    cards = []
    for material in sorted(merged_materials(matter.materials), key=_card_order):
        roles = {use.role for use in material.uses}
        botanical = _botanical(ctx, material.material_id)
        if not (roles & CARD_ROLES or material.compound is not None or botanical):
            continue
        claims = _card_claims(ctx, [c for use in material.uses for c in use.claim_ids])
        facts = [ref for ref, claim in claims if ctx.claims[claim.id].discipline != HEALTH][:CARD_FACTS_MAX]
        handling = [ref for ref, claim in claims if ctx.claims[claim.id].discipline == HEALTH][
            :CARD_FACTS_MAX
        ]
        if not facts:
            continue
        ref = f"m{len(cards) + 1}"
        offer = CardOffer(ref, material, {f"{ref}.{key}": claim for key, claim in claims})
        choice = CardChoice(
            material=ref,
            facts=[f"{ref}.{key}" for key in facts],
            handling=[f"{ref}.{key}" for key in handling],
        )
        card = material_card(
            offer, choice, block_id=f"chem.card-{len(cards) + 1}", records=ctx.rows.record_sources
        )
        if card is not None:
            cards.append(card)
    return cards


def _card_order(material: MaterialRows) -> tuple[str, str]:
    return material.name.casefold(), str(material.material_id)


def _card_claims(ctx: ChapterContext, claim_ids: Sequence[uuid.UUID]) -> list[tuple[str, KnownClaim]]:
    found = [ctx.claims[claim_id] for claim_id in dict.fromkeys(claim_ids) if claim_id in ctx.claims]
    facts = [claim for claim in found if claim.level in FACT_LEVELS]
    facts.sort(key=lambda claim: (claim.provenance != CURATED, ctx.visible.order.get(claim.id, 0)))
    return [(f"c{n}", known) for n, claim in enumerate(facts, start=1) if (known := ctx.known(claim.id))]


def _botanical(ctx: ChapterContext, material_id: uuid.UUID) -> str | None:
    curated = ctx.records.curated
    found = (
        next((item for item in curated.materials if item.material_id == material_id), None)
        if curated
        else None
    )
    return found.botanical_name if found is not None else None


def _material_compounds(ctx: ChapterContext) -> dict[str, CompoundRecord]:
    found: dict[str, CompoundRecord] = {}
    for use in ctx.process().materials:
        if use.compound is not None:
            found.setdefault(use.name, use.compound)
    return found
