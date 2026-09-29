"""
Page content. Three pages, not eleven steps:

  1. The challenge   -- why querying a stream with SQL is hard, and the fix
  2. Live            -- Kafka events and the SQL over them, side by side
  3. How it works    -- the architecture, and the limits
"""

PAGE1 = {
    "kicker": "The challenge",
    "title": "Streams are easy to capture and hard to ask anything of.",
    "copy": "Event-driven systems publish every change as it happens \u2014 durable, ordered, "
            "replayable, at a scale no nightly batch could match. That part is solved. The "
            "problem starts the moment somebody wants to <em>ask something</em>.",
    "points": [
        ("Streaming in", "Kafka keeps its job: carrying change safely and in order."),
        ("Querying out", "SQL keeps its job: joins, windows and thirty days of history."),
        ("Nothing in between", "No stream processor, no feature store, no model server."),
    ],
}


PAGE3 = {
    "kicker": "How it works",
    "title": "Four lanes to build it. Two paths to run it.",
    "copy": "The top band runs once, and each lane needs the one above it. The middle band "
            "runs on every transaction. The bottom band runs when somebody asks a question "
            "\u2014 and the agent in it holds no database credential of its own.",
}

ARCHITECTURE = [
    ("Source", "PostgreSQL", "The transaction is committed here. Nothing about this "
     "system knows analytics exists.", False),
    ("Capture", "Debezium", "Reads the write-ahead log and publishes the change. "
     "Measured at ~520ms, commit to topic.", False),
    ("Transport", "Kafka", "Avro on a topic, with Schema Registry. Durable, ordered, "
     "replayable.", False),
    ("Land", "Exasol import UDF", "The database consumes the topic itself and merges "
     "into a RAW table, resuming from its own stored offset.", True),
    ("Enrich", "Exasol SQL", "Velocity, deviation and geo flags as window functions "
     "over 30 days of history already in the engine.", True),
    ("Score", "Exasol Python UDF", "Model loaded from BucketFS, returned inside the "
     "SELECT like any built-in function.", True),
]

ARCH_NOTE = ("Those last three boxes are one database. That is the whole argument: the "
             "history, the feature definitions and the model live in the same place, so "
             "answering &ldquo;is this fraud?&rdquo; is a query rather than a distributed "
             "system.")

TUNING_NOTE = ("One number worth knowing if you build this yourself: the connector "
               "defaults to <code>POLL_TIMEOUT_MS=30000</code> and "
               "<code>MIN_RECORDS_PER_RUN=100</code>, so importing a single transaction "
               "sits in an empty poll waiting for 99 more that never arrive — 62 seconds "
               "per import, measured. Setting the poll window to 400ms took this pipeline "
               "from 62.96s to 3.32s end to end.")

LIMITS = [
    ("The model is deliberately small",
     "A logistic regression over twelve features. Its strongest coefficient is merchant "
     "category, ahead of both velocity counts — so if you ask what it keys on most, the "
     "honest answer is where she shopped, not how fast."),
    ("The customer is synthetic",
     "Elena Fischer and her 49 transactions were generated with a fixed seed so every run "
     "is identical. The spending pattern is plausible, not real."),
    ("Delivery is at-least-once",
     "Idempotence comes from merging on the primary key and resuming at the highest stored "
     "Kafka offset, not from a distributed transaction. Do not call it exactly-once."),
    ("One node, small volumes",
     "Exasol is running as a local single-node instance. This demonstrates where the "
     "computation happens, not how far it scales."),
]
