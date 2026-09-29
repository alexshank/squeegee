"""The 2022 words and quotes journal, cleaned into one record per day.

Run it with::

    squeegee run examples/words_2022.py --input examples/words-2022.txt --output /tmp/words.json

The input is a file a person kept by hand, so it has no header row and its
entries are separated by nothing but the date they start with. The reader
registered below is the only custom thing here: every field is parsed by an
ordinary stage, so each step shows up in the recorded run.
"""

import re

from squeegee import stage
from squeegee.io import register_reader
from squeegee.io.text_io import blocks_starting_with

# blank lines fall inside entries as often as between them, so the date that
# opens an entry is the only reliable boundary in the file
register_reader(".txt", blocks_starting_with(r"\d{1,2}/\d{1,2}"))

# the file is the 2022 list, and most of its dates carry no year at all
YEAR = 2022

DATE_AND_BODY = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*-?\s*(.*)$", re.DOTALL)
QUOTED = re.compile("“(.+?)”([^“]*)", re.DOTALL)


@stage
def drop_the_title(record):
    """Drop the file's title, which is everything before the first date."""
    return None if not DATE_AND_BODY.match(record["text"]) else record


@stage
def split_the_date_from_the_body(record):
    """Separate the leading date from the text of the entry."""
    month, day, year, body = DATE_AND_BODY.match(record["text"]).groups()
    record["date_text"] = "/".join(part for part in (month, day, year) if part)
    record["body"] = " ".join(body.split())
    return record


@stage
def parse_the_date(record):
    """Turn MM/DD, MM/DD/YY and MM/DD/YYYY alike into an ISO date."""
    month, day, *given = record.pop("date_text").split("/")
    # the file writes the year as "22", as "2022", and most often not at all
    year = int(given[0]) if given else YEAR
    record["date"] = f"{year if year > 99 else 2000 + year}-{int(month):02d}-{int(day):02d}"
    return record


@stage
def collect_the_quotes(record):
    """Pull out each quoted passage, with whatever follows it as its attribution.

    A few entries were written down without quote marks. Those keep the whole
    body as one passage rather than being dropped, since they are quotes too.
    """
    body = record.pop("body")
    found = QUOTED.findall(body) or [_split_on_the_dash(body)]
    record["quotes"] = [{"text": text.strip(), "source": source} for text, source in found]
    return record


@stage
def attribute_each_quote(record):
    """Tidy the attribution: drop the dash a source is sometimes introduced by."""
    for quote in record["quotes"]:
        quote["source"] = quote["source"].strip().lstrip("-").strip() or None
    record["quote_count"] = len(record["quotes"])
    return record


def _split_on_the_dash(body):
    # an unquoted entry runs "the words -the source", and a source never has a dash
    text, dash, source = body.rpartition("-")
    return (text, source) if dash else (body, "")
