"""Persistence for run history."""

from squeegee.store.queries import list_runs, run_summary
from squeegee.store.sqlite import Store, to_json

__all__ = ["Store", "list_runs", "run_summary", "to_json"]
