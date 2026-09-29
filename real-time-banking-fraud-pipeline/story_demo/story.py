"""
The script of the demo. Data only -- no UI.

Each act is one transaction. The escalation is driven by merchant risk, amount
and velocity together, because the model's strongest coefficient is merchant
category (+1.49) and its next two are the velocity counts.
"""
from dataclasses import dataclass

HOME_DEVICE = "DEV-ELENA-IPHONE-13"
FRAUD_DEVICE = "DEV-UNKNOWN-ANDROID-X"


@dataclass
class Act:
    key: str
    number: str
    title: str
    subtitle: str
    narration: str
    expect: str
    amount: float
    merchant: str
    mcc: str
    channel: str
    country: str
    city: str
    device: str


ACTS = [
    Act("normal", "1", "An ordinary Tuesday",
        "Elena buys coffee, the way she has 40 times this month",
        "This is the whole pipeline, running on a transaction that matters to nobody. "
        "Postgres writes a row. Debezium notices. Kafka carries it. Exasol lands it, "
        "builds the features and scores it.",
        "Expect: approved, and near zero.",
        5.40, "Corner Coffee", "5812", "POS", "US", "Austin", HOME_DEVICE),

    Act("probe", "2", "The card is stolen",
        "A one-dollar test charge, from Malta, on a device she has never used",
        "This is what card testing looks like. A trivial amount, just to see whether "
        "the card is live. New country, new device — both flags fire.",
        "Expect: still approved. One dollar is not fraud, and the model knows it.",
        1.00, "GlobalMart", "5999", "ONLINE", "MT", "Valletta", FRAUD_DEVICE),

    Act("escalate1", "3", "It worked. They go shopping",
        "Electronics, 180 dollars, same device, same country",
        "The card is live, so the amount climbs. Nothing here is alarming on its own — "
        "people do buy electronics online.",
        "Expect: rising, but still approved.",
        180.00, "TechDirect EU", "5045", "ONLINE", "MT", "Valletta", FRAUD_DEVICE),

    Act("escalate2", "4", "Now they move money",
        "A 2,400 dollar wire transfer, through an API channel",
        "Three things change at once: the merchant category is a wire-transfer service, "
        "the amount is eight times her normal spend, and this is her third transaction "
        "in an hour when her average is two a day.",
        "Expect: blocked.",
        2400.00, "FX Global Wire", "4829", "API", "MT", "Valletta", FRAUD_DEVICE),

    Act("blocked", "5", "And then they get greedy",
        "8,750 dollars at an online casino",
        "Highest-risk merchant category in the book, twenty-seven times her normal "
        "transaction, fourth in an hour, foreign country, unknown device.",
        "Expect: blocked, at effectively certainty.",
        8750.00, "LuckyBet Online", "7995", "ONLINE", "MT", "Valletta", FRAUD_DEVICE),
]

# Act 6 is not a transaction -- it is the receipt for act 5, and act 7 is the
# architectural claim. Both are rendered from data already on screen.
RECEIPT_ACT = {
    "number": "6",
    "title": "Why it blocked",
    "subtitle": "The score, taken apart",
    "narration": "Every contribution below is coefficient times scaled value for the "
                 "logistic regression in BucketFS. They sum to the log-odds, and the "
                 "sigmoid of that sum reproduces the score the database returned to "
                 "six decimal places. This is arithmetic, not an explanation generated "
                 "after the fact.",
}

CLAIM_ACT = {
    "number": "7",
    "title": "Where all of that ran",
    "subtitle": "One database did the work",
    "narration": "No stream processor. No feature store. No model server.",
}

ACT_BY_KEY = {a.key: a for a in ACTS}
