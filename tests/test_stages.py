"""Tests for the stage decorator and its registry."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from squeegee.errors import StageDefinitionError
from squeegee.stages import Stage, clear_registry, registered_stages, stage


@pytest.fixture(autouse=True)
def _empty_registry() -> None:
    clear_registry()


def test_declaration_order_is_preserved() -> None:
    @stage
    def first(record: dict[str, Any]) -> dict[str, Any]:
        return record

    @stage
    def second(record: dict[str, Any]) -> dict[str, Any]:
        return record

    @stage
    def third(record: dict[str, Any]) -> dict[str, Any]:
        return record

    assert [s.name for s in registered_stages()] == ["first", "second", "third"]


def test_the_function_is_returned_unchanged() -> None:
    @stage
    def double(record: dict[str, int]) -> dict[str, int]:
        return {"n": record["n"] * 2}

    assert double({"n": 2}) == {"n": 4}


def test_description_defaults_to_the_first_docstring_line() -> None:
    @stage
    def documented(record: dict[str, Any]) -> dict[str, Any]:
        """Explain the transformation.

        A second paragraph that the UI does not need.
        """
        return record

    assert registered_stages()[0].description == "Explain the transformation."


def test_name_and_description_can_be_overridden() -> None:
    @stage(name="renamed", description="given directly")
    def original(record: dict[str, Any]) -> dict[str, Any]:
        """Ignored in favour of the argument."""
        return record

    registered = registered_stages()[0]
    assert (registered.name, registered.description) == ("renamed", "given directly")


def test_source_is_captured_and_hashed() -> None:
    @stage
    def hashed(record: dict[str, Any]) -> dict[str, Any]:
        return record

    registered = registered_stages()[0]
    assert "def hashed" in registered.source_text
    assert len(registered.source_sha256) == 64


def test_editing_a_stage_changes_its_hash(tmp_path: Path) -> None:
    # mirrors the real flow: the same stage, edited between two runs of a script
    unedited = _load_stage_module(tmp_path / "unedited.py", "    return record")
    clear_registry()
    edited = _load_stage_module(
        tmp_path / "edited.py", '    record["edited"] = True\n    return record'
    )

    assert unedited.name == edited.name == "parse"
    assert unedited.source_sha256 != edited.source_sha256


def _load_stage_module(path: Path, body: str) -> Stage:
    path.write_text(f"from squeegee import stage\n\n\n@stage\ndef parse(record):\n{body}\n")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    return registered_stages()[0]


def test_annotations_are_recorded_when_present() -> None:
    @stage
    def annotated(record: dict[str, Any]) -> dict[str, Any] | None:
        return record

    registered = registered_stages()[0]
    assert registered.input_type == "dict[str, Any]"
    assert registered.output_type == "dict[str, Any] | None"


def test_an_unannotated_stage_registers_with_no_types() -> None:
    @stage
    def bare(record):  # type: ignore[no-untyped-def] # a user script needs no annotations
        return record

    registered = registered_stages()[0]
    assert (registered.input_type, registered.output_type) == (None, None)


def test_an_explicit_none_return_is_not_mistaken_for_an_absent_annotation() -> None:
    @stage
    def returns_none(record: dict[str, Any]) -> None:
        return None

    assert registered_stages()[0].output_type == "None"


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        ("def two(a, b): return a", "takes 2 positional parameters"),
        ("def none_at_all(): return None", "takes 0 positional parameters"),
        ("def generating(record):\n    yield record", "is a generator"),
        ("async def asynchronous(record): return record", "is async"),
    ],
)
def test_unusable_stage_shapes_are_rejected(definition: str, expected: str) -> None:
    namespace: dict[str, Any] = {}
    exec(definition, namespace)
    function = next(value for key, value in namespace.items() if key != "__builtins__")

    with pytest.raises(StageDefinitionError) as raised:
        stage(function)

    assert expected in str(raised.value)
    assert function.__name__ in str(raised.value)


def test_a_stage_without_retrievable_source_still_registers() -> None:
    namespace: dict[str, Any] = {}
    exec("def from_a_string(record): return record", namespace)

    stage(namespace["from_a_string"])

    assert "source unavailable" in registered_stages()[0].source_text


def test_string_annotations_are_recorded_verbatim(tmp_path: Path) -> None:
    # a script using "from __future__ import annotations" hands over strings, not objects
    path = tmp_path / "postponed.py"
    path.write_text(
        "from __future__ import annotations\n\n"
        "from squeegee import stage\n\n\n"
        "@stage\n"
        "def parse(record: dict[str, int]) -> dict[str, int] | None:\n"
        "    return record\n"
    )
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))

    registered = registered_stages()[0]
    assert registered.input_type == "dict[str, int]"
    assert registered.output_type == "dict[str, int] | None"
