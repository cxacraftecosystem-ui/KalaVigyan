from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, absent
from .blocks import SENTENCE, BlockBase, ExplainerSentence, SentenceSpec, named_in, require_facts
from .citations import AnswerSentence
from .crafts import COMPARED_CRAFTS_MAX, CraftRef
from .subject_keys import TermKey
from .terms import TERM_LABEL_MAX_CHARS
from .vocabulary import Discipline

__all__ = [
    "COMPARE_CRAFTS_MAX",
    "COMPARE_CRAFTS_MIN",
    "COMPARE_ROWS_MAX",
    "CONCEPT_CRAFTS_MAX",
    "CONCEPT_NODES_MAX",
    "QUIZ_BLANK",
    "QUIZ_MAX_QUESTIONS",
    "QUIZ_OPTIONS_MAX",
    "QUIZ_OPTIONS_MIN",
    "QUIZ_PROMPT_MAX_CHARS",
    "CompareBlock",
    "CompareCell",
    "CompareRow",
    "CompareTerm",
    "ConceptCraft",
    "ConceptGraphBlock",
    "ConceptNode",
    "QuizBlock",
    "QuizOption",
    "QuizQuestion",
    "quiz_prompt",
]

QUIZ_MAX_QUESTIONS = 10
QUIZ_OPTIONS_MIN = 2
QUIZ_OPTIONS_MAX = 5
QUIZ_PROMPT_MAX_CHARS = 1000
QUIZ_BLANK = "_____"
COMPARE_CRAFTS_MIN = 2
COMPARE_CRAFTS_MAX = 1 + COMPARED_CRAFTS_MAX
COMPARE_ROWS_MAX = 12
CONCEPT_NODES_MAX = 8
CONCEPT_CRAFTS_MAX = 100


class QuizOption(ContractModel):
    term_key: TermKey
    text: str = Field(min_length=1, max_length=TERM_LABEL_MAX_CHARS)
    sentence: ExplainerSentence

    @model_validator(mode="after")
    def _a_term_its_cited_sentence_marks(self) -> Self:
        if not any(s.term_key == self.term_key and s.text == self.text for s in self.sentence.terms):
            raise ValueError(f"quiz option {self.text!r} is a term its cited sentence marks")
        return self


class QuizQuestion(ContractModel):
    prompt: str = Field(min_length=1, max_length=QUIZ_PROMPT_MAX_CHARS)
    options: list[QuizOption] = Field(min_length=QUIZ_OPTIONS_MIN, max_length=QUIZ_OPTIONS_MAX)
    answer: int = Field(ge=0)

    @model_validator(mode="after")
    def _a_cloze_of_its_keyed_sentence(self) -> Self:
        if self.answer >= len(self.options):
            raise ValueError(f"quiz question {self.prompt!r} keys one of its options")
        keys = [option.term_key for option in self.options]
        texts = [option.text.casefold() for option in self.options]
        if len(set(keys)) != len(keys) or len(set(texts)) != len(texts):
            raise ValueError(f"quiz question {self.prompt!r} offers distinct terms")
        keyed = self.options[self.answer]
        if self.prompt != quiz_prompt(keyed.sentence.text, keyed.text):
            raise ValueError(f"quiz question {self.prompt!r} is its keyed sentence with the key blanked")
        problems = _distractor_problems(keyed, [o for i, o in enumerate(self.options) if i != self.answer])
        if problems:
            raise ValueError(f"quiz question {self.prompt!r}: {'; '.join(problems)}")
        return self


class QuizBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("questions", [(("options", [(("sentence", SENTENCE),)]),)]),)

    kind: Literal["quiz"]
    version: Literal[1]
    questions: list[QuizQuestion] = Field(min_length=1, max_length=QUIZ_MAX_QUESTIONS)

    @model_validator(mode="after")
    def _each_question_once_from_cited_facts(self) -> Self:
        require_facts(f"quiz {self.id}", list(self.cited_sentences()))
        prompts = [question.prompt for question in self.questions]
        if len(set(prompts)) != len(prompts):
            raise ValueError(f"quiz {self.id} asks each question once")
        return self

    def shown_labels(self) -> list[str]:
        return list(dict.fromkeys(option.text for q in self.questions for option in q.options))


class CompareTerm(ContractModel):
    key: TermKey
    label: str = Field(min_length=1, max_length=TERM_LABEL_MAX_CHARS)


class CompareCell(ContractModel):
    sentence: ExplainerSentence
    piece_id: uuid.UUID | None


class CompareRow(ContractModel):
    facet: Discipline
    term: CompareTerm | None
    cells: list[CompareCell | None] = Field(min_length=COMPARE_CRAFTS_MIN, max_length=COMPARE_CRAFTS_MAX)

    @model_validator(mode="after")
    def _a_row_two_crafts_fill(self) -> Self:
        filled = [cell for cell in self.cells if cell is not None]
        if len(filled) < COMPARE_CRAFTS_MIN:
            raise ValueError(f"compare row {self.facet} sets at least two crafts side by side")
        if self.term is not None and not all(named_in(self.term.label, cell.sentence) for cell in filled):
            raise ValueError(f"compare row {self.term.key} is named by every sentence it shows")
        claims = [_claims_of(cell.sentence) for cell in filled]
        if any(a & b for i, a in enumerate(claims) for b in claims[i + 1 :]):
            raise ValueError(f"compare row {self.facet} rests each craft's cell on its own claims")
        return self


class CompareBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("rows", [(("cells", [(("sentence", SENTENCE),)]),)]),)

    kind: Literal["compare"]
    version: Literal[1]
    crafts: list[CraftRef] = Field(min_length=COMPARE_CRAFTS_MIN, max_length=COMPARE_CRAFTS_MAX)
    rows: list[CompareRow] = Field(min_length=1, max_length=COMPARE_ROWS_MAX)

    @model_validator(mode="after")
    def _different_crafts_cell_by_cell(self) -> Self:
        slugs = [craft.slug for craft in self.crafts]
        if len(set(slugs)) != len(slugs):
            raise ValueError(f"compare {self.id} sets different crafts side by side")
        if any(len(row.cells) != len(self.crafts) for row in self.rows):
            raise ValueError(f"compare {self.id} gives every row one cell per craft")
        aspects = [(row.facet, row.term.key if row.term else None) for row in self.rows]
        if len(set(aspects)) != len(aspects):
            raise ValueError(f"compare {self.id} compares each aspect once")
        require_facts(f"compare {self.id}", list(self.cited_sentences()))
        return self

    def shown_labels(self) -> list[str]:
        terms = [row.term.label for row in self.rows if row.term is not None]
        return [*(craft.name for craft in self.crafts), *dict.fromkeys(terms)]


class ConceptCraft(ContractModel):
    craft: CraftRef
    concept_ids: list[uuid.UUID] = Field(min_length=1)
    sentence: ExplainerSentence


class ConceptNode(ContractModel):
    term_key: TermKey
    label: str = Field(min_length=1, max_length=TERM_LABEL_MAX_CHARS)
    crafts: list[ConceptCraft] = Field(min_length=COMPARE_CRAFTS_MIN, max_length=CONCEPT_CRAFTS_MAX)
    craft_count: int | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _a_concept_crafts_share(self) -> Self:
        if self.craft_count is not None and self.craft_count < len(self.crafts):
            raise ValueError(f"concept {self.term_key} counts at least the crafts it lists")
        slugs = [entry.craft.slug for entry in self.crafts]
        concepts = [concept for entry in self.crafts for concept in entry.concept_ids]
        if len(set(slugs)) != len(slugs) or len(set(concepts)) != len(concepts):
            raise ValueError(f"concept {self.term_key} lists each craft and each of its concepts once")
        if not all(named_in(self.label, entry.sentence) for entry in self.crafts):
            raise ValueError(f"concept {self.term_key} is named by each craft's cited sentence")
        require_facts(f"concept {self.term_key}", [entry.sentence for entry in self.crafts])
        return self


class ConceptGraphBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("nodes", [(("crafts", [(("sentence", SENTENCE),)]),)]),)

    kind: Literal["concept_graph"]
    version: Literal[1]
    focus: CraftRef | None
    nodes: list[ConceptNode] = Field(min_length=1, max_length=CONCEPT_NODES_MAX)

    @model_validator(mode="after")
    def _shared_concepts_around_the_focus(self) -> Self:
        keys = [node.term_key for node in self.nodes]
        if len(set(keys)) != len(keys):
            raise ValueError(f"concept graph {self.id} shows each concept once")
        if self.focus is not None and not all(_shares(node, self.focus.slug) for node in self.nodes):
            raise ValueError(f"concept graph {self.id} shows concepts its focus craft shares")
        require_facts(f"concept graph {self.id}", list(self.cited_sentences()))
        return self

    def shown_labels(self) -> list[str]:
        crafts = dict.fromkeys(entry.craft.name for node in self.nodes for entry in node.crafts)
        return [*(node.label for node in self.nodes), *crafts]


def quiz_prompt(text: str, key: str) -> str:
    start = text.find(key)
    if start < 0:
        raise ValueError(f"the key {key!r} is not in the keyed sentence")
    return f"{text[:start]}{QUIZ_BLANK}{text[start + len(key) :]}"


def _distractor_problems(keyed: QuizOption, distractors: Sequence[QuizOption]) -> list[str]:
    problems = []
    for option in distractors:
        if _claims_of(option.sentence) & _claims_of(keyed.sentence):
            problems.append(f"{option.text!r} is drawn from a claim other than the key's")
        if named_in(option.text, keyed.sentence):
            problems.append(f"{option.text!r} is stated by the keyed sentence, so it is no wrong answer")
    return problems


def _claims_of(sentence: AnswerSentence) -> frozenset[str]:
    return frozenset(citation.claim_id for citation in sentence.citations)


def _shares(node: ConceptNode, slug: str) -> bool:
    return any(entry.craft.slug == slug for entry in node.crafts)
