"""The agent: Claude, the Exasol MCP server, and nothing else.

WHY THIS EXISTS. The rest of the demo argues that a semantic layer is what makes
trial data answerable. This runs the experiment: the SAME question, the SAME
database, the SAME model -- once with the layer's guidance and once without -- and
shows the difference in what the agent writes and what it concludes.

The agent has no SQL written for it. It discovers the schema through MCP, writes
its own statements, and is judged on whether it cites NCT ids and whether it
notices the traps. CT_LAKE is reached the same way as any native table, which is
the point: the lakehouse is a schema, so an agent needs no lakehouse client.
"""
import asyncio, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.expanduser("~/.exasol/personal/deployments/default/secrets.json")

MODEL = "claude-opus-5"

# Read queries are OFF by default in the MCP server; without this the agent can
# only describe the schema, never query it.
MCP_SETTINGS = {
    "enable_read_query": True,
    "enable_summarize_table": True,
    "default_row_limit": 50,
    "query_result_format": "dict",
}

# --- the two system prompts the demo compares --------------------------------
NAIVE = """You are a data analyst with access to an Exasol database through MCP tools.
Answer the user's question with SQL. Explain what you found."""

# This is the repository's own SKILL.md, which is what a team would actually ship
# alongside a semantic layer: not a prompt trick, but the layer's documentation.
WITH_LAYER = """You are a clinical-trial analyst with access to an Exasol database
through MCP tools. Answer questions about the trial landscape using SQL.

## The layer
- CT.V_LANDSCAPE - one row per trial: phase, status group, sponsor type, comparator
  design, primary endpoint category, region count. Start here.
- CT.V_TRIALS, CT.V_TRIAL_GEOGRAPHY, CT.V_TRIAL_ENDPOINTS, CT.V_TRIAL_DESIGN
- CT.ELIG_CHUNKS - eligibility criteria, one row per criterion, with
  CRITERION_SECTION in INCLUSION / EXCLUSION / UNKNOWN.
- CT_LAKE.PUBLICATIONS and CT_LAKE.TRIAL_PUBLICATIONS - PubMed records. These are
  a VIRTUAL SCHEMA over Iceberg tables in object storage, not native tables. Query
  them exactly like any other table; the join key NCT_ID is a real identifier.

## Three things that will make you wrong
1. PHASE = 'PHASE3' drops a third of the data. 34.4% of trials say NOT_APPLICABLE.
   If the user asks about phase, say how many trials have no phase, or filter on
   PHASE_IS_STATED and state that you did.
2. ENDPOINT_CATEGORY is derived from free text and 35.7% is 'Other / unclassified'.
   Never present an endpoint breakdown without that number.
3. Similarity cannot see negation, and neither can a LIKE. 'no', 'not' and
   'without' are stopwords to the retrieval index. Whenever polarity matters -
   whenever the question says exclude, without, or no prior - you MUST filter
   CRITERION_SECTION rather than trusting the text to tell you.

## Citing
Every claim about a trial carries its NCT ID. Every claim about a criterion quotes
the criterion text and names its CRITERION_SECTION - a criterion without its
section is not evidence, because the section is the half retrieval gets wrong.

CONDITION and SECTION are reserved words in Exasol; the columns are
CONDITION_NAME and CRITERION_SECTION. Keep queries small and cite what you find."""


def have_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _mcp_env():
    sec = json.load(open(SECRETS))
    return {**os.environ,
            "EXA_DSN": "127.0.0.1/nocertcheck:8563",
            "EXA_USER": "sys",
            "EXA_PASSWORD": sec["dbPassword"],
            "EXA_MCP_SETTINGS": json.dumps(MCP_SETTINGS)}


def _summarise(result, limit=420):
    """Tool output, trimmed for the trace. The full text still goes to the model."""
    txt = result if isinstance(result, str) else json.dumps(result)
    return txt[:limit] + (" …" if len(txt) > limit else "")


async def _run(question, system, max_turns=12):
    """One agent run. Returns a trace the UI can render."""
    from anthropic import AsyncAnthropic
    from anthropic.lib.tools.mcp import async_mcp_tool
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    trace = {"steps": [], "answer": "", "sql": [], "error": "", "turns": 0}
    client = AsyncAnthropic()
    params = StdioServerParameters(command="uvx", args=["exasol-mcp-server@latest"],
                                   env=_mcp_env())
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as mcp:
            await mcp.initialize()
            tools = [async_mcp_tool(t, mcp) for t in (await mcp.list_tools()).tools]

            runner = client.beta.messages.tool_runner(
                model=MODEL,
                max_tokens=16000,
                system=system,
                thinking={"type": "adaptive"},
                # Opus 5 may decline a request; route around it rather than
                # failing in front of an audience.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                tools=tools,
                messages=[{"role": "user", "content": question}],
            )

            async for message in runner:
                trace["turns"] += 1
                if trace["turns"] > max_turns:
                    trace["error"] = "stopped after %d turns" % max_turns
                    break
                for block in message.content:
                    if block.type == "text" and block.text.strip():
                        trace["steps"].append({"kind": "think", "text": block.text.strip()})
                        trace["answer"] = block.text.strip()
                    elif block.type == "tool_use":
                        args = block.input if isinstance(block.input, dict) else {}
                        sql = args.get("query", "")
                        if sql:
                            trace["sql"].append(sql)
                        trace["steps"].append({"kind": "tool", "name": block.name,
                                               "sql": sql, "args": args, "result": ""})
                resp = await runner.generate_tool_call_response()
                if resp is None:
                    continue
                # Attach each result to the tool step that produced it.
                pending = [s for s in trace["steps"] if s["kind"] == "tool" and not s["result"]]
                for step, blk in zip(pending, resp.get("content", [])):
                    content = blk.get("content")
                    step["result"] = _summarise(
                        "".join(c.get("text", "") for c in content)
                        if isinstance(content, list) else content)
    return trace


def ask(question, use_layer=True):
    """Sync wrapper for Streamlit. Returns the trace, or an error in it."""
    if not have_key():
        return {"steps": [], "answer": "", "sql": [], "turns": 0,
                "error": "no ANTHROPIC_API_KEY in the environment"}
    system = WITH_LAYER if use_layer else NAIVE
    try:
        return asyncio.run(_run(question, system))
    except BaseException as e:                                # noqa: BLE001
        return {"steps": [], "answer": "", "sql": [], "turns": 0, "error": _unwrap(e)}




# --- the simple demo --------------------------------------------------------
# The A/B run above is the rigorous version and it is slow: the agent spends
# five or six turns discovering the schema before it writes anything. For a
# booth, hand it the schema and let it do the one thing worth watching -- turn a
# sentence into SQL and answer with citations.
SCHEMA_BRIEF = """You answer clinical-trial questions against an Exasol database
by writing SQL. Use execute_exasol_query. Keep it to ONE query where you can.

TABLES (all live in this one engine):
  CT.V_LANDSCAPE(NCT_ID, INDICATION, BRIEF_TITLE, PHASE, PHASE_IS_STATED,
      STATUS_GROUP, LEAD_SPONSOR, SPONSOR_TYPE, ENROLLMENT, START_YEAR,
      PRIMARY_ENDPOINT_CATEGORY)         -- one row per trial
  CT.ELIG_CHUNKS(NCT_ID, CHUNK_ID, CRITERION_SECTION, CHUNK_TEXT)
      -- one row per eligibility criterion; CRITERION_SECTION is
         INCLUSION / EXCLUSION / UNKNOWN, recovered from prose
  CT_LAKE.PUBLICATIONS(PMID, DOI, TITLE, JOURNAL, PUB_YEAR)
  CT_LAKE.TRIAL_PUBLICATIONS(NCT_ID, PMID)
      -- CT_LAKE is a VIRTUAL SCHEMA over Iceberg tables in object storage.
         Query it exactly like a native table.
  CT.ELIG_VECTORS(NCT_ID, CHUNK_ID, DIM, VAL)
      -- every criterion embedded as 96 rows, L2-normalised

IN-DATABASE SEMANTIC SEARCH over the criteria. Use this INSTEAD of
UPPER(CHUNK_TEXT) LIKE '%...%' whenever the question is about MEANING rather than
an exact string -- a LIKE cannot tell "prior anti-PD-1" from "no prior anti-PD-1",
and it misses every paraphrase. CT.EMBED_QUERY is an in-database function: the
text never leaves the engine.

WITH QV AS (SELECT DIM, VAL FROM (SELECT CT.EMBED_QUERY('<the concept>') FROM DUAL))
SELECT c.NCT_ID, c.CHUNK_ID, c.CRITERION_SECTION,
       ROUND(SUM(v.VAL * q.VAL), 4) AS SIM,
       SUBSTR(c.CHUNK_TEXT, 1, 200) AS CRITERION
FROM CT.ELIG_VECTORS v
JOIN QV q  ON q.DIM = v.DIM
JOIN CT.ELIG_CHUNKS c ON c.NCT_ID = v.NCT_ID AND c.CHUNK_ID = v.CHUNK_ID
WHERE c.CRITERION_SECTION = 'EXCLUSION'          -- or 'INCLUSION'
GROUP BY c.NCT_ID, c.CHUNK_ID, c.CRITERION_SECTION, c.CHUNK_TEXT
ORDER BY SIM DESC LIMIT 10

Three rules for that query, all of which produce wrong answers if broken:
 - A UDF that EMITS columns cannot share a SELECT list. Always wrap it in a
   subquery exactly as shown.
 - GROUP BY the CHUNK_ID, never the truncated text. Grouping by the text merges
   two different criteria and sums their scores, which can report a cosine
   above 1.
 - ALWAYS filter CRITERION_SECTION, and ALWAYS report which section each hit
   came from. A criterion without its section is not evidence.

RULES
- INDICATION is only 'NSCLC' or 'BREAST'.
- 34.4% of trials have PHASE='NOT_APPLICABLE'. If the question is about phase,
  say how many were excluded, or use PHASE_IS_STATED.
- Whenever the question involves excluding / without / no prior, filter
  CRITERION_SECTION = 'EXCLUSION'. Never rely on the text alone: 'no' and 'not'
  are stopwords to every index, so the text cannot tell you polarity.
- CONDITION and SECTION are reserved words. Use CONDITION_NAME, CRITERION_SECTION.

ANSWERING - the result table is shown to the user already, so do NOT list its
rows back. Reply in exactly this shape and nothing else:

**<one sentence with the headline number>**
- <a caveat, if one applies>
- <a second caveat, if one applies>

Keep it under 45 words. Cite an NCT id in the headline only if the question asks
which trials. No preamble, no restating the table."""


async def _run_simple(question, max_turns=6):
    from anthropic import AsyncAnthropic
    from anthropic.lib.tools.mcp import async_mcp_tool
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    trace = {"steps": [], "answer": "", "sql": [], "error": "", "turns": 0}
    client = AsyncAnthropic()
    params = StdioServerParameters(command="uvx", args=["exasol-mcp-server@latest"],
                                   env=_mcp_env())
    try:
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as mcp:
                await mcp.initialize()
                # Only the executor. Fewer tools is fewer turns, and schema
                # discovery is already in the prompt.
                tools = [async_mcp_tool(t, mcp) for t in (await mcp.list_tools()).tools
                         if t.name == "execute_exasol_query"]
                runner = client.beta.messages.tool_runner(
                    model=MODEL, max_tokens=2000, system=SCHEMA_BRIEF,
                    output_config={"effort": "low"},      # one SQL query is not hard
                    tools=tools,
                    messages=[{"role": "user", "content": question}])
                async for message in runner:
                    trace["turns"] += 1
                    if trace["turns"] > max_turns:
                        trace["error"] = "stopped after %d turns" % max_turns
                        break
                    for block in message.content:
                        if block.type == "text" and block.text.strip():
                            trace["answer"] = block.text.strip()
                        elif block.type == "tool_use":
                            sql = (block.input or {}).get("query", "")
                            if sql:
                                trace["sql"].append(sql)
                                trace["steps"].append({"sql": sql, "result": ""})
                    resp = await runner.generate_tool_call_response()
                    if resp is None:
                        continue
                    pending = [s for s in trace["steps"] if not s["result"]]
                    for step, blk in zip(pending, resp.get("content", [])):
                        c = blk.get("content")
                        raw = ("".join(x.get("text", "") for x in c)
                               if isinstance(c, list) else (c or ""))
                        step["result"] = _summarise(raw, 300)
                        step["raw"] = raw
    finally:
        await client.close()
    trace["rows"] = _as_rows(trace["steps"])
    return trace


def _as_rows(steps):
    """The last statement that actually returned something, as a list of dicts.

    The MCP server is configured with query_result_format="dict", so a result is
    either a JSON array of row objects or {"result": []} when empty.
    """
    for step in reversed(steps):
        raw = (step.get("raw") or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            data = data.get("result") or data.get("rows") or []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data
    return []


def _unwrap(e):
    """An ExceptionGroup hides the message that actually matters.

    The first failure here was a plain 'credit balance is too low', reported as
    'ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)'. At a
    booth that is the difference between a five-second fix and a dead demo.
    """
    seen = e
    for _ in range(6):
        subs = getattr(seen, "exceptions", None)
        if not subs:
            break
        seen = subs[0]
    msg = str(seen)
    if "credit balance is too low" in msg:
        return "Anthropic account is out of credits — top up at console.anthropic.com → Plans & Billing."
    if "authentication" in msg.lower() or "invalid x-api-key" in msg.lower():
        return "The ANTHROPIC_API_KEY was rejected. Check .env."
    return "%s: %s" % (type(seen).__name__, msg[:300])


def ask_simple(question):
    if not have_key():
        return {"steps": [], "answer": "", "sql": [], "turns": 0,
                "error": "no ANTHROPIC_API_KEY — see .env.example"}
    try:
        return asyncio.run(_run_simple(question))
    except BaseException as e:                                # noqa: BLE001
        return {"steps": [], "answer": "", "sql": [], "turns": 0, "error": _unwrap(e)}


SIMPLE_PRESETS = [
    "How many Phase 3 NSCLC trials are recruiting, and who are the top sponsors?",
    "Which trials exclude patients with prior anti-PD-1 therapy? Cite NCT ids.",
    "How many completed Phase 3 trials have a linked publication in CT_LAKE?",
    "What are the biggest Phase 3 breast cancer trials by enrolment?",
]


PRESETS = [
    ("The polarity trap",
     "Which Phase 3 NSCLC trials exclude patients who have had prior anti-PD-1 therapy? "
     "Cite NCT ids."),
    ("The phase trap",
     "How many Phase 3 breast cancer trials are there, and who sponsors them?"),
    ("Across both storage tiers",
     "Of the completed Phase 3 trials, how many have a linked publication? "
     "The publications are in CT_LAKE."),
    ("The endpoint trap",
     "What are the most common primary endpoints in NSCLC trials?"),
]

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or PRESETS[0][1]
    t = ask(q, use_layer=True)
    print(json.dumps(t, indent=2)[:3000])
