from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, absent, empty
from .blocks import SENTENCE, BlockBase, ExplainerSentence, LadderCondition, SentenceSpec, require_facts
from .citations import Citation
from .colours import ColourSide, ColourWord, states_colour
from .quotes import quote_occurs
from .reactions import SPECIES_ROLES, ReactionSpecies, mhchem_equation, reaction_level
from .subject_keys import TermKey
from .terms import WIKIDATA_ID_PATTERN
from .vocabulary import MaterialKind, MaterialRole, ReactionKind, ShownLevel

__all__ = [
    "COMPOUND_RECORD_BASIS",
    "FORMULA_BASES",
    "MaterialCardBlock",
    "Molecule3dBlock",
    "ReactionNote",
    "ReactionPlayerBlock",
    "ReactionStep",
    "StepColour",
    "StepEnergy",
]


FORMULA_BASES = ("STATED", "COMPOUND_RECORD")
COMPOUND_RECORD_BASIS = "COMPOUND_RECORD"


class StepColour(ContractModel):
    side: ColourSide
    colour: ColourWord
    stated: str = Field(min_length=1, max_length=200)
    citations: list[Citation] = Field(min_length=1)

    @model_validator(mode="after")
    def _stated_by_a_cited_quote(self) -> Self:
        if not states_colour(self.stated, self.colour):
            raise ValueError(f"colour {self.colour} is not named by {self.stated!r}")
        if not any(c.quote and quote_occurs(self.stated, c.quote) for c in self.citations):
            raise ValueError(f"colour {self.colour} states {self.stated!r}, which no cited quote says")
        return self


class StepEnergy(ContractModel):
    kj_per_mol: float
    claim_id: str = Field(min_length=1)


class ReactionNote(ContractModel):
    reaction_id: uuid.UUID
    sentence: ExplainerSentence


class ReactionStep(ContractModel):
    reaction_id: uuid.UUID
    stage_id: uuid.UUID | None
    kind: ReactionKind
    label: str = Field(min_length=1, max_length=200)
    species: list[ReactionSpecies] = Field(min_length=2)
    equation: str | None
    balanced: bool
    level: ShownLevel
    citations: list[Citation] = Field(min_length=1)
    stage: str | None = Field(default=None, min_length=1, max_length=300, exclude_if=absent)
    conditions: list[LadderCondition] = Field(default_factory=list, exclude_if=empty)
    colours: list[StepColour] = Field(default_factory=list, exclude_if=empty)
    formula_basis: Literal[*FORMULA_BASES] | None = Field(default=None, exclude_if=absent)
    formula_sources: list[str] = Field(default_factory=list, exclude_if=empty)
    delta_h: StepEnergy | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _energy_from_a_cited_claim(self) -> Self:
        if self.delta_h is not None and self.delta_h.claim_id not in {c.claim_id for c in self.citations}:
            raise ValueError(f"reaction {self.reaction_id} states its ΔH only from a claim it cites")
        return self

    @model_validator(mode="after")
    def _formulas_from_compound_records(self) -> Self:
        inferred = self.formula_basis == COMPOUND_RECORD_BASIS
        if inferred != bool(self.formula_sources):
            raise ValueError(
                f"reaction {self.reaction_id} cites compound records exactly when its formulas come from them"
            )
        if inferred and not (self.balanced and all(s.compound_id for s in self.species)):
            raise ValueError(
                f"reaction {self.reaction_id} takes its formulas from compound records only when every "
                "species resolves to one and the science engine balances it"
            )
        if len(set(self.formula_sources)) != len(self.formula_sources):
            raise ValueError(f"reaction {self.reaction_id} cites each compound record once")
        return self

    @model_validator(mode="after")
    def _the_science_engine_s_reaction(self) -> Self:
        if {species.role for species in self.species} != set(SPECIES_ROLES):
            raise ValueError(f"reaction {self.reaction_id} names at least one reactant and one product")
        if self.equation != mhchem_equation(self.species):
            raise ValueError(f"reaction {self.reaction_id} equation is not built from its species")
        if self.balanced and self.equation is None:
            raise ValueError(f"reaction {self.reaction_id} is balanced only with a formula for every species")
        level, _ = reaction_level(
            [c.level for c in self.citations], balanced=self.balanced, species=self.species
        )
        if self.level != level:
            raise ValueError(f"reaction {self.reaction_id} is {level}, not {self.level}")
        sides = [colour.side for colour in self.colours]
        if len(set(sides)) != len(sides):
            raise ValueError(f"reaction {self.reaction_id} states each side's colour once")
        return self

    def all_citations(self) -> Iterator[Citation]:
        yield from self.citations
        for condition in self.conditions:
            yield from condition.citations
        for colour in self.colours:
            yield from colour.citations


class ReactionPlayerBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("notes", [(("sentence", SENTENCE),)]),)

    kind: Literal["reaction_player"]
    version: Literal[1]
    steps: list[ReactionStep] = Field(min_length=1)
    notes: list[ReactionNote] = Field(default_factory=list, exclude_if=empty)

    @model_validator(mode="after")
    def _each_reaction_once(self) -> Self:
        ids = [step.reaction_id for step in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError(f"reaction player {self.id} plays each reaction once")
        if any(note.reaction_id not in ids for note in self.notes):
            raise ValueError(f"reaction player {self.id} explains only the reactions it plays")
        require_facts(f"reaction player {self.id}", [note.sentence for note in self.notes])
        return self

    def citations(self) -> Iterator[Citation]:
        for step in self.steps:
            yield from step.all_citations()
        for note in self.notes:
            yield from note.sentence.citations

    def direct_source_ids(self) -> Iterator[str]:
        for step in self.steps:
            yield from step.formula_sources

    def shown_labels(self) -> list[str]:
        return [step.label for step in self.steps]


class MaterialCardBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("facts", [SENTENCE]), ("handling", [SENTENCE]))

    kind: Literal["material_card"]
    version: Literal[1]
    material_id: uuid.UUID | None
    compound_id: uuid.UUID | None
    term_key: TermKey | None
    name: str = Field(min_length=1, max_length=300)
    material_kind: MaterialKind | None
    role: MaterialRole | None
    formula: str | None = Field(min_length=1, max_length=120)
    pubchem_cid: int | None = Field(ge=1)
    wikidata_id: str | None = Field(pattern=WIKIDATA_ID_PATTERN)
    local_names: list[str]
    facts: list[ExplainerSentence] = Field(min_length=1)
    handling: list[ExplainerSentence]
    source_id: str | None = Field(default=None, min_length=1, exclude_if=absent)

    @model_validator(mode="after")
    def _values_from_stored_rows(self) -> Self:
        require_facts(f"material card {self.id}", [*self.facts, *self.handling])
        if self.source_id is not None and self.pubchem_cid is None:
            raise ValueError(f"material card {self.id} cites a compound record only with its PubChem id")
        if (self.material_kind or self.role) and self.material_id is None:
            raise ValueError(f"material card {self.id} shows a kind or role only from its stored material")
        if (self.formula or self.pubchem_cid) and self.compound_id is None:
            raise ValueError(f"material card {self.id} shows a formula or PubChem id only from its compound")
        if (self.local_names or self.wikidata_id) and self.term_key is None:
            raise ValueError(
                f"material card {self.id} shows local names or Wikidata only from its glossary term"
            )
        folded = [name.casefold() for name in self.local_names]
        if len(set(folded)) != len(folded) or any(not name.strip() for name in self.local_names):
            raise ValueError(f"material card {self.id} lists each local name once")
        return self

    def direct_source_ids(self) -> Iterator[str]:
        if self.source_id is not None:
            yield self.source_id

    def shown_labels(self) -> list[str]:
        return [self.name, *self.local_names]


class Molecule3dBlock(BlockBase):
    kind: Literal["molecule_3d"]
    version: Literal[1]
    compound_id: uuid.UUID
    pubchem_cid: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=300)
    formula: str | None = Field(min_length=1, max_length=120)
    source_id: str = Field(min_length=1)

    def direct_source_ids(self) -> Iterator[str]:
        yield self.source_id

    def shown_labels(self) -> list[str]:
        return [self.name]
