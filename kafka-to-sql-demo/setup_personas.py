#!/usr/bin/env python3
"""
Create the persona users and grant them the minimum that works.

Each persona gets SELECT on two row-filtered views and nothing else -- no base
table, no schema-wide grant. Verified at the end by connecting as each persona
and counting what it can actually see.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P

PERSONAS = {
    "FRAUD_ANALYST_US": "us-analyst-demo",
    "FRAUD_ANALYST_EU": "eu-analyst-demo",
    "FRAUD_LEAD":       "fraud-lead-demo",
}

GRANTS = [
    "GRANT SELECT ON FRAUD_DEMO.V_SCORED_TRANSACTIONS TO {u}",
    "GRANT SELECT ON FRAUD_DEMO.V_CUSTOMERS TO {u}",
    # read their own audit trail -- never anyone else's, and never write
    "GRANT SELECT ON FRAUD_DEMO.V_MY_AUDIT TO {u}",
]


def main():
    ex = P.exa_connect()
    try:
        sql = (Path(__file__).parent / "sql" / "personas.sql").read_text()
        sql += "\n" + (Path(__file__).parent / "sql" / "audit.sql").read_text()
        sql = re.sub(r"--[^\n]*", "", sql)
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            ex.execute(stmt)
        print("schema, views and entitlements applied")

        for user, pwd in PERSONAS.items():
            try:
                ex.execute(f"DROP USER {user} CASCADE")
            except Exception:
                pass
            ex.execute(f"CREATE USER {user} IDENTIFIED BY \"{pwd}\"")
            ex.execute(f"GRANT CREATE SESSION TO {user}")
            for g in GRANTS:
                ex.execute(g.format(u=user))
            print(f"  created {user}")

        print("\nwhat each persona can actually see:")
        for user, pwd in PERSONAS.items():
            c = P.exa_connect_as(user, pwd)
            try:
                n = c.execute(
                    "SELECT COUNT(*) FROM FRAUD_DEMO.V_SCORED_TRANSACTIONS").fetchall()[0][0]
                units = [r[0] for r in c.execute(
                    "SELECT DISTINCT BUSINESS_UNIT FROM FRAUD_DEMO.V_SCORED_TRANSACTIONS"
                ).fetchall()]
                who = c.execute("SELECT CURRENT_USER").fetchall()[0][0]
                # prove the base table is NOT reachable
                try:
                    c.execute("SELECT COUNT(*) FROM ANALYTICS.FRAUD_FEATURES").fetchall()
                    base = "REACHABLE  <-- too much privilege"
                except Exception:
                    base = "denied"
                print(f"  {who:<18} {n:>4} rows  units={units or '[]'}  base table: {base}")
            finally:
                c.close()
    finally:
        ex.close()


if __name__ == "__main__":
    main()
