# every check runs locally; there is no CI, by choice
.PHONY: check lint format typecheck test hooks sync ui ui-check wheel

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

# the UI targets need Node; users installing a wheel never do
ui:
	cd frontend && npm install && npm run build

ui-check:
	cd frontend && npm run check && npx tsc --noEmit && npm test

wheel:
	uv build --wheel
