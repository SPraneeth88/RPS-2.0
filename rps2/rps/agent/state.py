"""Shared state passed between LangGraph nodes."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

import operator


class AgentState(TypedDict, total=False):
    message: str            # raw user input
    intent: str             # classified intent
    entities: dict          # extracted entities
    nlu_source: str         # "llm" or "rules"
    result: dict            # structured outcome of the action node
    reply: str              # natural-language response shown to the user
    # `trace` accumulates an entry per node so the UI can render the agent's
    # reasoning pipeline. `operator.add` lets parallel/sequential nodes append.
    trace: Annotated[list[dict[str, Any]], operator.add]
