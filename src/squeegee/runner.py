"""Driving records through the registered stages, and recording everything."""

from __future__ import annotations

import copy
import random
import time
import traceback
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from squeegee.errors import SqueegeeError
from squeegee.io import read_records, reader_for, write_records, writer_for
from squeegee.stages import Stage, registered_stages
from squeegee.store import Store

Record = dict[str, Any]


@dataclass(frozen=True)
class Failure:
    """The stage and record that stopped a run."""

    stage_position: int
    stage_name: str
    record_index: int
    error_type: str
    error_message: str


@dataclass(frozen=True)
class RunResult:
    """What a run did, for the CLI to print and the tests to assert on."""

    run_id: int
    status: str
    records_in: int
    records_out: int
    records_dropped: int
    records_errored: int
    duration_us: int
    failure: Failure | None
    database_path: Path


def run(
    *,
    script_path: Path,
    input_path: Path,
    output_path: Path | None,
    database_path: Path,
    limit: int | None = None,
    sample: int | None = None,
    seed: int | None = None,
    continue_on_error: bool = False,
) -> RunResult:
    """Run the registered stages over ``input_path`` and record every step.

    Stages run in declaration order, one record at a time. A stage returning
    None drops its record; a stage raising aborts the run unless
    ``continue_on_error`` is set, and either way the outcome is recorded.

    Raises:
        SqueegeeError: The run cannot start: no stages, an unreadable input, or
            an unsupported extension on either side.
    """
    stages = registered_stages()
    _check_wiring(stages, input_path, output_path)
    started = time.perf_counter_ns()

    with Store(database_path) as store:
        run_id = store.start_run(
            script_path=script_path,
            script_sha256=sha256(script_path.read_bytes()).hexdigest(),
            input_path=input_path,
            output_path=output_path,
            options={
                "limit": limit,
                "sample": sample,
                "seed": seed,
                "continue_on_error": continue_on_error,
            },
        )
        run_stage_ids = [
            store.register_stage(run_id, position, stage) for position, stage in enumerate(stages)
        ]
        counts = {"in": 0, "out": 0, "dropped": 0, "errored": 0}
        survivors: list[Record] = []
        failure: Failure | None = None

        for index, source in enumerate(_selected(input_path, limit, sample, seed)):
            counts["in"] += 1
            record_id = store.add_record(run_id, index, source)
            outcome, failure = _drive(
                store=store,
                stages=stages,
                run_stage_ids=run_stage_ids,
                record_id=record_id,
                record_index=index,
                source=source,
                counts=counts,
            )
            if outcome is not None:
                survivors.append(outcome)
                counts["out"] += 1
            if failure is not None:
                if not continue_on_error:
                    break
                # the error is recorded; the run carries on and finishes normally
                failure = None

        status = "failed" if failure is not None else "finished"
        # a failed run writes no output file: half a cleaned CSV is worse than none
        if output_path is not None and failure is None:
            write_records(output_path, survivors)
        duration_us = (time.perf_counter_ns() - started) // 1_000
        store.add_run_event(run_id, status, {**counts, "duration_us": duration_us})

    return RunResult(
        run_id=run_id,
        status=status,
        records_in=counts["in"],
        records_out=counts["out"],
        records_dropped=counts["dropped"],
        records_errored=counts["errored"],
        duration_us=duration_us,
        failure=failure,
        database_path=database_path,
    )


def _drive(
    *,
    store: Store,
    stages: list[Stage],
    run_stage_ids: list[int],
    record_id: int,
    record_index: int,
    source: Record,
    counts: dict[str, int],
) -> tuple[Record | None, Failure | None]:
    current = source
    for position, stage in enumerate(stages):
        # the stage gets its own copy, so the value recorded as its input stays true
        # even when a stage ignores the advice not to mutate in place. The store
        # serializes eagerly, so `current` itself is safe to hand over as the input.
        stage_input = copy.deepcopy(current)
        started = time.perf_counter_ns()
        try:
            output = stage.func(stage_input)
        # a stage is user code, so it may raise anything at all
        except Exception as error:
            counts["errored"] += 1
            store.add_record_event(
                record_id=record_id,
                run_stage_id=run_stage_ids[position],
                status="error",
                record_input=current,
                error_type=type(error).__name__,
                error_message=str(error),
                error_traceback="".join(traceback.format_exception(error)),
                duration_us=_elapsed_us(started),
            )
            return None, Failure(
                stage_position=position,
                stage_name=stage.name,
                record_index=record_index,
                error_type=type(error).__name__,
                error_message=str(error),
            )
        duration_us = _elapsed_us(started)
        if output is None:
            counts["dropped"] += 1
            store.add_record_event(
                record_id=record_id,
                run_stage_id=run_stage_ids[position],
                status="dropped",
                record_input=current,
                duration_us=duration_us,
            )
            return None, None
        store.add_record_event(
            record_id=record_id,
            run_stage_id=run_stage_ids[position],
            status="ok",
            record_input=current,
            record_output=output,
            duration_us=duration_us,
        )
        current = output
    return current, None


def _check_wiring(stages: list[Stage], input_path: Path, output_path: Path | None) -> None:
    if not stages:
        raise SqueegeeError(
            f"{input_path.name} has nowhere to go: the script registered no stages. "
            "Decorate at least one function with @stage."
        )
    if not input_path.is_file():
        raise SqueegeeError(f"input file {input_path} does not exist")
    reader_for(input_path)
    if output_path is not None:
        writer_for(output_path)


def _selected(
    input_path: Path, limit: int | None, sample: int | None, seed: int | None
) -> Iterable[Record]:
    if sample is None:
        records = read_records(input_path)
        return (record for number, record in enumerate(records) if limit is None or number < limit)
    # sampling has to see every record before it can choose, which is affordable
    # only because squeegee is for small data
    population = list(read_records(input_path))
    return random.Random(seed).sample(population, min(sample, len(population)))


def _elapsed_us(started_ns: int) -> int:
    return (time.perf_counter_ns() - started_ns) // 1_000
