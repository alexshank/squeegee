"""Tests for the read-only HTTP server."""

import json
import re
import socket
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from squeegee.cli import main
from squeegee.errors import SqueegeeError
from squeegee.stages import clear_registry
from squeegee.ui import server as ui_server

EXAMPLES = Path(__file__).parents[2] / "examples"
API_DOC = Path(__file__).parents[2] / "docs" / "api.md"


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("served") / "squeegee.db"
    script = str(EXAMPLES / "clean_orders.py")
    for arguments in (
        ["--input", str(EXAMPLES / "orders.csv")],
        ["--input", str(EXAMPLES / "orders_with_a_bad_row.csv")],
    ):
        clear_registry()
        main(["run", script, "--db", str(path), "--quiet", *arguments])
    clear_registry()
    return path


@pytest.fixture(scope="module")
def base_url(database: Path) -> Iterator[str]:
    server = ui_server.build_server(database, port=0, quiet=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.socket.getsockname()[:2]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def get(base_url: str, path: str) -> Any:
    with urlopen(f"{base_url}{path}") as response:
        return json.loads(response.read())


def get_error(base_url: str, path: str) -> tuple[int, Any]:
    try:
        urlopen(f"{base_url}{path}")
    except HTTPError as error:
        return error.code, json.loads(error.read())
    raise AssertionError(f"{path} did not fail")


def test_meta_answers(base_url: str) -> None:
    assert get(base_url, "/api/meta")["run_count"] == 2


def test_runs_are_listed(base_url: str) -> None:
    listed = get(base_url, "/api/runs")

    assert [run["run_id"] for run in listed["items"]] == [2, 1]
    assert listed["has_more"] is False


def test_query_parameters_reach_the_query_layer(base_url: str) -> None:
    page = get(base_url, "/api/runs?limit=1")

    assert len(page["items"]) == 1
    assert page["has_more"] is True


def test_a_run_its_stages_and_one_stage(base_url: str) -> None:
    assert get(base_url, "/api/runs/2")["status"] == "failed"
    assert len(get(base_url, "/api/runs/2/stages")["items"]) == 5
    assert get(base_url, "/api/runs/2/stages/2")["name"] == "parse_amount"


def test_stage_records_filter_by_status(base_url: str) -> None:
    errors = get(base_url, "/api/runs/2/stages/2/records?status=error")

    assert [event["record_index"] for event in errors["items"]] == [8]


def test_a_record_trace_is_served(base_url: str) -> None:
    trace = get(base_url, "/api/runs/2/records/8")

    assert trace["final_status"] == "error"
    assert trace["events"][2]["stage_name"] == "parse_amount"


def test_field_statistics_are_served(base_url: str) -> None:
    fields = get(base_url, "/api/runs/1/stages/2/fields")

    assert {field["field"] for field in fields["items"]} == {
        "order_id",
        "email",
        "placed_on",
        "amount_cents",
    }


def test_a_field_detail_is_served_with_its_parameters(base_url: str) -> None:
    detail = get(base_url, "/api/runs/1/stages/2/fields/amount_cents?bins=5")

    assert len(detail["after"]["histogram"]) == 5


def test_a_field_name_may_be_percent_encoded(base_url: str) -> None:
    assert get(base_url, "/api/runs/1/stages/2/fields/amount%5Fcents")["field"] == "amount_cents"


def test_a_bad_parameter_is_a_400_naming_the_problem(base_url: str) -> None:
    status, body = get_error(base_url, "/api/runs?limit=lots")

    assert status == 400
    assert body["error"]["code"] == "invalid_parameter"
    assert "limit must be a whole number" in body["error"]["message"]


def test_an_unknown_run_is_a_400_rather_than_a_crash(base_url: str) -> None:
    status, body = get_error(base_url, "/api/runs/99")

    assert status == 400
    assert "no run 99" in body["error"]["message"]


def test_an_unknown_api_path_is_a_json_404(base_url: str) -> None:
    status, body = get_error(base_url, "/api/nothing/here")

    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_an_unknown_page_path_serves_the_single_page(base_url: str) -> None:
    with urlopen(f"{base_url}/runs/2/records/8") as response:
        body = response.read().decode()

    assert response.headers["Content-Type"].startswith("text/html")
    assert "squeegee" in body


def test_the_server_binds_to_localhost_only(database: Path) -> None:
    server = ui_server.build_server(database, port=0, quiet=True)

    assert server.socket.getsockname()[0] == "127.0.0.1"

    server.server_close()


def test_a_busy_port_is_explained(database: Path) -> None:
    taken = ui_server.build_server(database, port=0, quiet=True)
    port = taken.socket.getsockname()[1]

    with pytest.raises(SqueegeeError, match=f"port {port} is already in use"):
        ui_server.build_server(database, port=port, quiet=True)

    taken.server_close()


def test_serving_a_missing_database_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SqueegeeError, match="no squeegee database"):
        ui_server.serve(tmp_path / "absent.db", port=0)


def test_the_server_uses_daemon_threads(database: Path) -> None:
    server = ui_server.build_server(database, port=0, quiet=True)

    assert isinstance(server, ThreadingHTTPServer)
    assert server.daemon_threads is True

    server.server_close()


def test_javascript_is_served_as_javascript(database: Path) -> None:
    import mimetypes

    ui_server.build_server(database, port=0, quiet=True).server_close()

    assert mimetypes.guess_type("bundle.js")[0] == "text/javascript"
    assert mimetypes.guess_type("bundle.mjs")[0] == "text/javascript"


def test_directory_traversal_cannot_escape_the_static_directory(base_url: str) -> None:
    # SimpleHTTPRequestHandler.translate_path normalizes the path, so this cannot
    # reach the file even though it exists
    with urlopen(f"{base_url}/../../../../etc/passwd") as response:
        body = response.read().decode()

    assert "root:" not in body


def test_every_route_is_documented_in_api_md() -> None:
    documented = set(re.findall(r"`GET (/api[^`]*)`", API_DOC.read_text()))
    served = {_readable(pattern.pattern) for pattern, _ in ui_server._ROUTES}

    assert served - documented == set()
    assert documented - served == set()


def _readable(pattern: str) -> str:
    """Turn a route regex back into the path shape api.md documents."""
    path = re.sub(r"\(\?P<(\w+)>[^)]*\)", r"{\1}", pattern)
    return path.removeprefix("^").removesuffix("$")


def test_a_port_can_be_taken_by_something_that_is_not_squeegee(database: Path) -> None:
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    port = holder.getsockname()[1]
    holder.listen(1)

    with pytest.raises(SqueegeeError, match="already in use"):
        ui_server.build_server(database, port=port, quiet=True)

    holder.close()


def test_built_assets_are_served_when_they_exist(
    database: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>built</title>")
    (static / "app.js").write_text("export const ready = true;\n")
    monkeypatch.setattr(ui_server, "STATIC", static)

    server = ui_server.build_server(database, port=0, quiet=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.socket.getsockname()[:2]
    try:
        with urlopen(f"http://{host}:{port}/app.js") as asset:
            assert asset.headers["Content-Type"] == "text/javascript"
            assert "ready" in asset.read().decode()
        with urlopen(f"http://{host}:{port}/runs/1") as page:
            assert "built" in page.read().decode()
    finally:
        server.shutdown()
        server.server_close()


def test_serve_prints_where_it_is_listening_and_stops_cleanly(
    database: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_build = ui_server.build_server

    def interrupted(*arguments: Any, **keywords: Any) -> ThreadingHTTPServer:
        server = real_build(*arguments, **keywords)
        monkeypatch.setattr(
            server, "serve_forever", lambda *_, **__: (_ for _ in ()).throw(KeyboardInterrupt)
        )
        return server

    monkeypatch.setattr(ui_server, "build_server", interrupted)

    assert ui_server.serve(database, port=0) == 0
    printed = capsys.readouterr().out
    assert "squeegee ui on http://127.0.0.1:" in printed
    assert "stopped" in printed
    assert "assets are not built" in printed


def test_requests_are_logged_when_not_quiet(
    database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    server = ui_server.build_server(database, port=0, quiet=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.socket.getsockname()[:2]
    try:
        with urlopen(f"http://{host}:{port}/api/meta"):
            pass
    finally:
        server.shutdown()
        server.server_close()

    assert "/api/meta" in capsys.readouterr().err
