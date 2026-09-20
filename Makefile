# every check runs locally; there is no CI, by choice
.PHONY: check lint format typecheck test hooks sync

check: lint typecheck test

sync:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

hooks:
	uv run pre-commit install
