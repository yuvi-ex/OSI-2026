"""
The fraud analyst agent -- an MCP client, scoped by database identity.

What changed from the first version, and why it matters:

  before                                  now
  ------------------------------------    ------------------------------------
  pyexasol handle opened as SYS           MCP server authenticated as a persona
  our regex decided what SQL was safe     SQLGlot AST guard inside the server
  every table in the database reachable   SELECT on two row-filtered views
  the agent was inside the trust boundary the agent is outside all of it

The agent has no credential of its own. Whatever it can see is decided by which
database user the MCP server connected as -- so "which rows may this agent
read?" is answered by a GRANT, not by a prompt. Change the persona and the same
agent, asking the same question, gets a different answer.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import anthropic

import mcp_client as M
import pipeline as P
import runlog

MODEL = "claude-opus-5"

# Four of the server's twenty-four tools. A curated surface keeps the agent's
# behaviour legible on stage -- and the first one is a demo moment in itself,
# because the answer differs per persona.
ALLOWED_TOOLS = [
    "list_exasol_tables_and_views",
    "describe_exasol_tables_and_views",
    "execute_exasol_query",
    "summarize_exasol_table",
]

CONCLUDE = {
    "name": "conclude",
    "description": "Finish with a decision a human can act on.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string",
                        "enum": ["CONFIRMED_FRAUD", "LIKELY_FRAUD", "INCONCLUSIVE",
                                 "LIKELY_LEGITIMATE", "NOTHING_VISIBLE"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "headline": {
                "type": "string",
                "description": "ONE sentence, under 30 words, that a human reads first.",
            },
            "findings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Three to five findings. Each ONE line, under 22 words, "
                               "leading with the number that matters. No paragraphs.",
            },
            "evidence_sql": {
                "type": "string",
                "description": "A single SELECT that best demonstrates your conclusion "
                               "to a human -- the rows they should look at. It will be "
                               "executed and shown as a table, so keep it under 20 rows "
                               "and under 7 columns, and name the columns readably.",
            },
            "actions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Two to four imperatives, one line each, most urgent "
                               "first. No paragraphs.",
            },
        },
        "required": ["verdict", "confidence", "headline", "findings",
                     "evidence_sql", "actions"],
        "additionalProperties": False,
    },
    "strict": True,
}


SYSTEM = """You are a fraud analyst at a bank, working through an MCP connection to the
bank's Exasol warehouse.

Your database identity decides what you can see. You are entitled to your own business
unit and nothing else -- other analysts' customers are not merely hidden from the screen,
they are absent from every query you run. If you find nothing, that is a real and
reportable answer: say so with the verdict NOTHING_VISIBLE rather than speculating about
rows you cannot read.

Two views are available to you, and they are the only objects you can read:

  FRAUD_DEMO.V_SCORED_TRANSACTIONS
    TXN_ID, MERCHANT_NAME, MERCHANT_MCC, CHANNEL, COUNTRY_CODE, CITY, DEVICE_ID,
    STATUS, INITIATED_AT, AMOUNT_USD, TXN_COUNT_1H, AMOUNT_VS_AVG_RATIO,
    MCC_BASE_RISK, IS_CROSS_BORDER, IS_NEW_COUNTRY_30D, IS_NEW_DEVICE_30D,
    FRAUD_SCORE, DECISION, BUSINESS_UNIT

  FRAUD_DEMO.V_CUSTOMERS
    CUSTOMER_ID, FULL_NAME, COUNTRY_CODE, KYC_STATUS, RISK_BAND, ACCOUNT_ID,
    ACCOUNT_NUMBER, ACCOUNT_TYPE, BALANCE, CREDIT_LIMIT, BUSINESS_UNIT

Query those directly. The SYS catalogue tables are NOT granted to you -- do not try to
read SYS.EXA_ALL_OBJECTS, SYS.EXA_ALL_TABLES or similar; they will fail and waste your
turns. You do not need to discover the schema, it is above.

Guidance, not a checklist: compare a payment against the customer's own baseline; look
for the small-test-then-escalate pattern; check whether several accounts hit the same
merchant, which would point at a compromised merchant rather than a compromised card;
notice unfamiliar devices and countries. Investigate as you see fit.

Your conclusion is read on a projector by people who cannot pause. Be terse: one-line
findings that lead with a number, short imperative actions, no paragraphs. Nominate an
`evidence_sql` that shows the rows a human should actually look at -- it will be run and
rendered as a table beneath your answer, so keep it small and name its columns readably.

Rules:
- Never write SELECT *. Name the columns you need.
- Always LIMIT your result sets.
- Work in at most 5 queries, then call `conclude`. Fewer is better if you are sure.
- You MUST finish by calling `conclude`. An investigation with no conclusion is a
  failure, however good the queries were.
"""


@dataclass
class Step:
    kind: str                      # "tool" | "conclusion" | "error"
    tool: str = ""
    rationale: str = ""
    args: dict = field(default_factory=dict)
    text: str = ""
    ms: float = 0.0
    error: bool = False
    payload: dict = field(default_factory=dict)

    @property
    def sql(self) -> str:
        return self.args.get("query", "")

    def table(self):
        """Parse the server's tabular JSON, if that is what came back."""
        try:
            d = json.loads(self.text)
            if isinstance(d, dict) and "columns" in d and "rows" in d:
                return d["columns"], d["rows"]
        except Exception:
            pass
        return None, None


DEFAULT_QUESTION = (
    "Some payments on your book have been blocked by the scoring model. "
    "Find them, work out what is going on, and tell me what to do.")

# Prepared questions. Each is chosen to expose something different, and the
# second and last are the ones that show the identity boundary most clearly:
# ask them as the US analyst, then as the EU analyst, and the answer changes
# because the rows are gone -- not because the agent behaved differently.
QUESTIONS = [
    ("Investigate the blocked payments", DEFAULT_QUESTION),

    ("What can you actually see?",
     "Before investigating anything, establish your own scope. List every table and "
     "view you can read, count the rows in each, and tell me which business unit "
     "they belong to. Be explicit about what is not available to you."),

    ("Everything on Elena Fischer",
     "Show me everything you can see about the customer Elena Fischer \u2014 her account, "
     "her recent payments, and anything that looks wrong. If you cannot see her, say so "
     "plainly and explain why."),

    ("Is the merchant compromised, or the card?",
     "Several payments to 'FX Global Wire' have been blocked. Work out whether this is a "
     "compromised merchant affecting many customers, or one compromised card. The "
     "distinction changes who we contact, so be specific about the evidence."),

    ("Find the card-testing pattern",
     "Fraudsters often make a tiny purchase to check a card is live, then escalate within "
     "minutes. Look for that shape in the payments you can see \u2014 small charge followed "
     "closely by a large one on the same account \u2014 and quantify the gap between them."),

    ("Show me the EU book",
     "List the blocked payments belonging to the EU retail business unit, with customer "
     "names. If your entitlements do not extend to that unit, say so rather than "
     "guessing."),
]


async def _run(persona: M.Persona, question: str, on_step, max_turns: int):
    import time
    client = anthropic.AsyncAnthropic()
    steps: list[Step] = []

    def emit(s: Step):
        steps.append(s)
        if on_step:
            on_step(s)

    # One session for the whole investigation. Spawning the server per tool call
    # would add its startup cost to every single query.
    async with M.session_for(persona) as session:
        # Ask the ENGINE who it thinks we are. This is the identity that goes in
        # the audit trail -- not persona.db_user, which is only what we intended.
        engine_user = persona.db_user
        try:
            who = await session.call_tool(
                "execute_exasol_query", {"query": "SELECT CURRENT_USER"})
            engine_user = json.loads(
                "\n".join(getattr(c, "text", None) or str(c) for c in who.content)
            )["rows"][0][0]
        except Exception:
            pass

        audit: list = []
        discovered = (await session.list_tools()).tools
        tools = [
            {"name": t.name,
             "description": (t.description or t.name).strip(),
             "input_schema": t.inputSchema or {"type": "object", "properties": {}}}
            for t in discovered if t.name in ALLOWED_TOOLS
        ] + [CONCLUDE]

        messages = [{"role": "user", "content":
                     f"You are connected as {persona.db_user}. {question}"}]

        for turn in range(max_turns):
            # One turn from the end, stop letting it explore. Running out of turns
            # with no verdict is the one failure the audience must never see.
            if turn == max_turns - 2:
                messages.append({
                    "role": "user",
                    "content": "You have one step left. Call `conclude` now with "
                               "whatever you have established so far.",
                })
            resp = await client.messages.create(
                model=MODEL, max_tokens=8000, system=SYSTEM, tools=tools,
                thinking={"type": "adaptive"}, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                emit(Step(kind="error", text="The agent stopped without concluding."))
                return steps

            results, finished = [], False
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                if block.name == "conclude":
                    payload = dict(block.input)
                    # Execute the query the model nominated, through the same
                    # persona-scoped session. The table under the answer is then
                    # something we ran, not something the model reported.
                    proof = payload.get("evidence_sql", "").strip()
                    if proof:
                        try:
                            pr = await session.call_tool(
                                "execute_exasol_query", {"query": proof})
                            ptxt = "\n".join(getattr(c, "text", None) or str(c)
                                              for c in pr.content)
                            if not pr.isError:
                                payload["_proof"] = json.loads(ptxt)
                        except Exception:
                            pass
                    emit(Step(kind="conclusion", payload=payload))
                    finished = True
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": "Recorded."})
                    continue

                args = dict(block.input)
                t0 = time.time()
                try:
                    res = await session.call_tool(block.name, args)
                    text = "\n".join(getattr(c, "text", None) or str(c)
                                     for c in res.content)
                    err = bool(res.isError)
                except Exception as exc:
                    text, err = f"{type(exc).__name__}: {exc}", True
                ms = (time.time() - t0) * 1000
                if block.name == "execute_exasol_query" and not err:
                    nrows = 0
                    try:
                        nrows = len(json.loads(text).get("rows", []))
                    except Exception:
                        pass
                    audit.append((args.get("query", ""), nrows, ms))
                emit(Step(kind="tool", tool=block.name, args=args, text=text,
                          ms=ms, error=err))
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": text[:6000],
                                **({"is_error": True} if err else {})})

            messages.append({"role": "user", "content": results})
            if finished:
                try:
                    P.write_audit(engine_user, question, audit)
                except Exception:
                    pass          # a failed audit write must not lose the answer
                runlog.log_investigation(persona, question, steps)
                return steps

    try:
        P.write_audit(engine_user, question, audit)
    except Exception:
        pass
    emit(Step(kind="error", text="The agent ran out of turns without concluding."))
    return steps


def investigate(persona: M.Persona, question: str = DEFAULT_QUESTION,
                on_step=None, max_turns: int = 10):
    """Run one investigation as this persona. Synchronous wrapper for Streamlit."""
    return asyncio.run(_run(persona, question, on_step, max_turns))
