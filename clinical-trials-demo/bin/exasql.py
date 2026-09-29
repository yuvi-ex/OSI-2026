#!/usr/bin/env python3
"""The one route from Python to the database.

`exapump` is gone; the Exasol CLI's own SQL client replaces it. Its contract is
simpler than what it replaced -- the result CSV is the whole of stdout, header
row first, and its own chatter goes to stderr -- so the three separate parsers
that used to hunt for a banner line are now this one function.

Keep it thin. The SQL is the artefact; nothing about the retrieval belongs here.
"""
import csv, io, subprocess

# -k because Exasol Personal serves a self-signed certificate.
CMD = ["exasol", "connect", "-k", "--csv", "-c"]


def rows(sql):
    """Run one statement, return its result as a list of dicts."""
    p = subprocess.run(CMD + [sql], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr.strip() or p.stdout.strip())[:400])
    out = p.stdout.strip()
    if not out:
        return []
    return list(csv.DictReader(io.StringIO(out)))


def rows_timed(sql):
    """Same, plus the wall-clock round trip in ms.

    This is the CLIENT's measurement of the whole statement -- connect, execute,
    fetch -- not the engine's internal time. It is the honest number to show on
    a booth screen, and it is the pessimistic one.
    """
    import time
    t0 = time.perf_counter()
    out = rows(sql)
    return out, int((time.perf_counter() - t0) * 1000)
