-- ===========================================================================
--  The audit trail.
--
--  Exasol Personal does not materialise EXA_DBA_AUDIT_SQL or
--  EXA_DBA_SESSIONS_LAST_DAY, so the demo keeps its own log. Two properties
--  make it worth trusting:
--
--    * DB_USER is not a variable this application was holding. It is read back
--      from the engine with SELECT CURRENT_USER through the agent's own MCP
--      session, so it records who the DATABASE believed was asking.
--    * The agent cannot write to it. The MCP server refuses every write, so
--      there is no path from the agent to its own audit trail -- it cannot
--      add, alter or erase a line about itself.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS FRAUD_DEMO.AGENT_AUDIT (
    ASKED_AT       TIMESTAMP    NOT NULL,
    DB_USER        VARCHAR(128) NOT NULL,   -- from the engine, not from the app
    QUESTION       VARCHAR(500),            -- what the human asked
    SQL_TEXT       VARCHAR(2000),           -- the SQL the agent wrote (STATEMENT is reserved)
    ROWS_RETURNED  DECIMAL(18,0),
    DURATION_MS    DECIMAL(10,1)
);

-- Each analyst sees their own calls and no one else's -- the same row filter
-- that governs the data governs the log of who read it.
CREATE OR REPLACE VIEW FRAUD_DEMO.V_MY_AUDIT AS
SELECT ASKED_AT, DB_USER, QUESTION, SQL_TEXT, ROWS_RETURNED, DURATION_MS
FROM   FRAUD_DEMO.AGENT_AUDIT
WHERE  DB_USER = CURRENT_USER;
