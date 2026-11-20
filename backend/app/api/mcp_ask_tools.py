from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.core.db import release_connection
from app.core.errors import InvalidInput
from app.core.mcp_scopes import ASK_SCOPE
from app.core.roles import role_value
from app.models import User
from app.research.crafts import QUESTION_MAX_CHARS, SLUG_MAX_CHARS
from app.research.depth import default_depth
from app.research.mcp_ask import ANSWER_VIEW_URI, AskedAnswer, asked_answer
from app.research.vocabulary import AnswerLanguage, Depth
from app.services.answering import AnswerAsk
from app.services.explainer_history import UnknownExplainer

from .mcp_ask_run import (
    AskTools,
    ask_refusal,
    asker_reading_style,
    run_to_the_end,
    throttle_refusal,
    withheld_terms,
)
from .mcp_tool_base import DATA_NOTE, READING, WRITES, Arguments, Tool, ToolContext, signed_in

__all__ = ["ASK_TOOLS", "Ask", "ask_tool"]

NOT_KEPT = "The answer was written but could not be read back. Open your answers on the site."
ASK_DESCRIPTION = (
    "Ask KalaVigyan a question about a craft in the signed-in person's name, as they would on the site, and get "
    "the finished answer: the question, the craft, each section with its cited sentences (each with the ids of "
    "the facts and sources it rests on and its citation numbers), the registered components placed in it by "
    "label, the sources with their licences, and the link to the same answer on the site. It runs our research "
    "and writing pipeline to the end and counts against the person's asks and AI budget exactly like the site, "
    "so it can take several minutes; allow up to ten. Clients that render MCP Apps draw it in KalaVigyan's "
    "design from the ui resource it names; otherwise show the answer_url, or draw it yourself with the "
    "kalavigyan://design/answer-kit.md resource. Name KalaVigyan and the Centre wherever you show it."
)


class Ask(Arguments):
    question: str = Field(
        min_length=2, max_length=QUESTION_MAX_CHARS, description="The question, as the person asked it"
    )
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A slug from find_crafts; when absent the craft is found from the question",
    )
    any_craft: bool = Field(default=False, description="Ask across crafts rather than about one craft")
    depth: Depth | None = Field(
        default=None, description="How deep to answer; the person's own default when absent"
    )
    language: AnswerLanguage | None = Field(
        default=None, description="The answer's language; English when absent"
    )

    @model_validator(mode="after")
    def _one_craft_or_any(self) -> Self:
        if self.any_craft and self.craft_slug is not None:
            raise ValueError("ask about one craft or any craft, not both")
        return self


def ask_tool(tools: AskTools) -> Tool:
    async def run(context: ToolContext, arguments: Ask) -> AskedAnswer:
        user = signed_in(context)
        ask = await _asked(context, user, arguments)
        outcome = await run_to_the_end(ask, user, context.index, tools)
        if outcome.problem is not None or outcome.answer_id is None:
            raise InvalidInput(outcome.problem or NOT_KEPT)
        try:
            document = await tools.stored(context.session, outcome.answer_id, user.id)
        except UnknownExplainer:
            raise InvalidInput(NOT_KEPT) from None
        return asked_answer(document, site=context.site, data_note=DATA_NOTE)

    return Tool(
        "ask",
        "Ask KalaVigyan",
        ASK_DESCRIPTION,
        Ask,
        AskedAnswer,
        run,
        ASK_SCOPE,
        WRITES,
        group=READING,
        view=ANSWER_VIEW_URI,
        shows_output=True,
    )


async def _asked(context: ToolContext, user: User, arguments: Ask) -> AnswerAsk:
    depth = arguments.depth or default_depth(user)
    refusal = await ask_refusal(context.session, user, depth)
    if refusal is not None:
        raise InvalidInput(refusal)
    style = await asker_reading_style(context.session, user)
    throttled = throttle_refusal(user)
    if throttled is not None:
        raise InvalidInput(throttled)
    await release_connection(context.session)
    return AnswerAsk(
        question=arguments.question,
        depth=depth,
        craft_slug=arguments.craft_slug,
        any_craft=arguments.any_craft,
        language=arguments.language,
        user_id=user.id,
        role=role_value(user),
        withheld_terms=withheld_terms(user),
        reading_style=style,
    )


ASK_TOOLS: tuple[Tool, ...] = (ask_tool(AskTools()),)
