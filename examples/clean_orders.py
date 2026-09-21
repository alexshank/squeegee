"""An example Squeegee pipeline, used as documentation and as a fixture.

Run it with::

    squeegee run examples/clean_orders.py --input examples/orders.csv --output /tmp/clean.csv

Each function below is one stage. They run in the order they are written, one
record at a time. Note that none of them are annotated: Squeegee never asks a
user script for type hints.
"""

import re

from squeegee import stage

EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_ids_already_seen: set[str] = set()


@stage
def normalize_headers(record):
    """Lowercase every column name and turn spaces into underscores."""
    return {key.strip().lower().replace(" ", "_"): value for key, value in record.items()}


@stage(name="drop_internal_test_orders")
def drop_test_rows(record):
    """Remove the orders placed by internal QA accounts."""
    return None if record["email"].endswith("@internal.test") else record


@stage
def parse_amount(record):
    """Convert the amount from a currency string to whole cents.

    Raises a ValueError on anything that is not a number, which is what makes
    this example useful for seeing a fail-fast run.
    """
    record["amount_cents"] = round(float(record.pop("amount").lstrip("$").replace(",", "")) * 100)
    return record


@stage
def validate_email(record):
    """Drop records whose email cannot be an email."""
    return record if EMAIL_SHAPE.match(record["email"]) else None


@stage
def dedupe_by_id(record):
    """Keep the first record for each order id, drop the rest.

    This stage holds state between records, which is allowed but worth
    noticing: it makes the result depend on the order records arrive in.
    """
    if record["order_id"] in _ids_already_seen:
        return None
    _ids_already_seen.add(record["order_id"])
    return record
