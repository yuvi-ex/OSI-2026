"""
MCP client: the agent's only route to the database.

Why this replaces the previous build. Before, the agent held a pyexasol handle
opened as SYS and we filtered its SQL with a regex. That is the wrong shape
twice over: the credential was all-powerful, and the guard lived in the same
process as the thing being guarded.

Now:
  * the agent talks to the official `exasol-mcp-server` over stdio;
  * that server authenticates as a PERSONA, not SYS, so the row filter is
    applied by the engine against CURRENT_USER;
  * writes are refused by the server's own settings, not by our regex;
  * the persona holds SELECT on two views and nothing else, so even a
    perfectly-crafted query cannot reach another unit's rows.

Three independent layers, and the agent is outside all of them.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import pipeline as P

# Least privilege, expressed as server configuration. Reading is on; writing,
# BucketFS and profiling are off. Only the demo schema is visible at all.
SERVER_SETTINGS = {
    "enable_read_query": True,
    "enable_write_query": False,
    "enable_read_bucketfs": False,
    "enable_write_bucketfs": False,
    "enable_query_profiling": False,
    "enable_summarize_table": True,
    "default_row_limit": 50,
    "views": {"enable": True},
    "schemas": {"enable": True, "like_pattern": "FRAUD_DEMO"},
    "tables": {"enable": True, "like_pattern": "FRAUD_DEMO.%"},
}


@dataclass(frozen=True)
class Persona:
    key: str
    db_user: str
    password: str
    title: str
    blurb: str


PERSONAS = [
    Persona("us", "FRAUD_ANALYST_US", "us-analyst-demo",
            "Fraud Analyst · US retail",
            "Scoped to the US retail book. Elena Fischer's account is theirs."),
    Persona("eu", "FRAUD_ANALYST_EU", "eu-analyst-demo",
            "Fraud Analyst · EU retail",
            "Scoped to the EU retail book. Cannot see US accounts at all."),
    Persona("lead", "FRAUD_LEAD", "fraud-lead-demo",
            "Fraud Lead · both books",
            "Entitled to both units. Same client, same question, more rows."),
]
BY_KEY = {p.key: p for p in PERSONAS}


def _server_params(persona: Persona) -> StdioServerParameters:
    env = dict(os.environ)
    env.update({
        "EXA_DSN": os.getenv("EXASOL_DSN", ""),
        "EXA_USER": persona.db_user,          # <- the identity that reaches the filter
        "EXA_PASSWORD": persona.password,
        "EXA_MCP_SETTINGS": json.dumps(SERVER_SETTINGS),
        # Exasol Personal serves a self-signed certificate. The variable is
        # EXA_SSL_CERT_VALIDATION -- the other spellings are silently ignored,
        # and the failure surfaces as a generic "a database error occurred".
        "EXA_SSL_CERT_VALIDATION": "false",
        "EXA_MCP_LOG_LEVEL": "ERROR",
    })
    return StdioServerParameters(
        command=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             ".venv", "bin", "exasol-mcp-server"),
        args=[],
        env=env,
    )


@asynccontextmanager
async def session_for(persona: Persona):
    """One MCP session, authenticated as this persona."""
    async with stdio_client(_server_params(persona)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _list_tools(persona: Persona):
    async with session_for(persona) as s:
        return [
            {"name": t.name,
             "description": (t.description or "").strip(),
             "input_schema": t.inputSchema or {"type": "object", "properties": {}}}
            for t in (await s.list_tools()).tools
        ]


def list_tools(persona: Persona):
    return asyncio.run(_list_tools(persona))


async def _call(persona: Persona, name: str, args: dict):
    async with session_for(persona) as s:
        res = await s.call_tool(name, args)
        parts = []
        for c in res.content:
            parts.append(getattr(c, "text", None) or str(c))
        return "\n".join(parts), bool(res.isError)


def call_tool(persona: Persona, name: str, args: dict):
    """Returns (text, is_error). Every database access in the demo goes through here."""
    return asyncio.run(_call(persona, name, args))
