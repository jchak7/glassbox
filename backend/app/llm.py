"""Claude planning layer: tool definitions, system prompt, one call per step.

Design choice worth knowing: the model reads a distilled text form of the
page (numbered elements + text excerpt), not screenshots. Screenshots go to
the human. Text is cheaper, faster, and less ambiguous to act on; the human
gets the pixels because trust is visual.
"""

import os
import anthropic

MODEL = os.environ.get("GLASSBOX_MODEL", "claude-sonnet-5")

TOOLS = [
    {
        "name": "navigate",
        "description": "Go to a URL. Relative paths (starting with /) stay on the current host.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element by its numbered id from the page inventory.",
        "input_schema": {
            "type": "object",
            "properties": {"element_id": {"type": "integer"}},
            "required": ["element_id"],
        },
    },
    {
        "name": "type_text",
        "description": "Clear a field and type into it. Set press_enter to submit search boxes and forms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element_id": {"type": "integer"},
                "text": {"type": "string"},
                "press_enter": {"type": "boolean", "default": False},
            },
            "required": ["element_id", "text"],
        },
    },
    {
        "name": "select_option",
        "description": "Pick an option in a <select> dropdown by value or visible label.",
        "input_schema": {
            "type": "object",
            "properties": {
                "element_id": {"type": "integer"},
                "value": {"type": "string"},
            },
            "required": ["element_id", "value"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page to reveal content and elements below the fold.",
        "input_schema": {
            "type": "object",
            "properties": {"direction": {"type": "string", "enum": ["up", "down"]}},
            "required": ["direction"],
        },
    },
    {
        "name": "read_more",
        "description": "Page through the current document's text when 'text_remaining' is large (long filings, reports). Does not touch the browser.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "go_back",
        "description": "Browser back button.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "finish",
        "description": "End the run and deliver the result. Use status=success only if the goal is actually met; otherwise status=failure with an honest account of what happened and what you'd try next.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["success", "failure"]},
                "summary": {"type": "string", "description": "2-5 sentences, plain language, for a non-technical reader."},
                "table": {
                    "type": "object",
                    "description": "The structured result, if the goal produced tabular data.",
                    "properties": {
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                    },
                    "required": ["columns", "rows"],
                },
                "notes": {"type": "array", "items": {"type": "string"},
                          "description": "Caveats, anomalies, normalization decisions worth flagging."},
            },
            "required": ["status", "summary"],
        },
    },
]

SYSTEM = """You are Glassbox, a browser agent operating a real Chromium browser \
for a human who is watching every step you take on a live interface.

Each turn you receive the current page as: URL, title, a numbered inventory of \
interactive elements like [12] <button> 'Search', a plain-text excerpt, and \
text_remaining (unread characters in the document). You act by calling exactly \
one tool per turn.

Rules of conduct:
- TRANSPARENCY IS THE PRODUCT. Before every tool call, write 1-3 short \
sentences a non-technical person can follow: what you observe, what you are \
about to do, and why it moves toward the goal. Never call a tool silently.
- One tool call per turn. Observe the result before deciding the next move.
- Element ids are re-numbered after every action. Only use ids from the \
latest page state.
- Long documents: if text_remaining is large and the answer may be deeper in \
the document, use read_more instead of guessing.
- If an action fails or the page looks wrong, say so plainly, then try a \
different approach — different element, different navigation path, or a \
site search. Do not repeat a failing action more than twice.
- Messages from the operator may arrive mid-run. They outrank everything \
except honesty: acknowledge them and adjust your plan.
- Data discipline: when the goal is extraction, record values exactly as the \
site shows them, normalize explicitly (state the rule you used, e.g. dates to \
ISO 8601, one currency column), and flag anything suspicious in notes rather \
than silently fixing it.
- Finish honestly. A partial result with a clear account beats a padded \
'success'. Never invent data you did not see in the browser.
"""


class Planner:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()  # ANTHROPIC_API_KEY from env
        self.model = MODEL

    async def step(self, messages: list) -> anthropic.types.Message:
        return await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOLS,
            # One action per turn is a design invariant: the human watches and
            # can veto each step, so steps must be atomic.
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            messages=messages,
        )


def compact_history(messages: list, keep_last: int = 3) -> list:
    """Truncate old page states so context stays lean on long runs.
    Full detail for the last few steps; older tool_results shrink to a stub."""
    out = []
    tool_result_idxs = [i for i, m in enumerate(messages)
                        if m["role"] == "user" and isinstance(m["content"], list)
                        and any(c.get("type") == "tool_result" for c in m["content"])]
    stale = set(tool_result_idxs[:-keep_last]) if len(tool_result_idxs) > keep_last else set()
    for i, m in enumerate(messages):
        if i in stale:
            slim = []
            for c in m["content"]:
                if c.get("type") == "tool_result":
                    text = c["content"] if isinstance(c["content"], str) else ""
                    head = text[:400]
                    slim.append({**c, "content": head + "\n[earlier page state truncated]"})
                else:
                    slim.append(c)
            out.append({**m, "content": slim})
        else:
            out.append(m)
    return out
