#!/usr/bin/env python3
"""
Full sync: import every Kafka topic into Exasol, merge into RAW and rebuild the
features. Run once after seed_story_persona.py, and again as the repair step if
PostgreSQL and Exasol ever drift apart.

    ./.venv/bin/python kafka-to-sql-demo/sync_history.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P

if __name__ == "__main__":
    P.sync_history()
    print("Synced: topics imported, RAW merged, features rebuilt.")
