"""The local, read-only HTTP server.

Standard library only: eight read-only endpoints and a static file handler do
not need a framework. See docs/decisions/0002-react-ui-on-a-stdlib-server.md,
and the hand-written server checklist in docs/ui-specification.md, every item
of which is implemented here and tested.
"""

from __future__ import annotations

import errno
import json
import mimetypes
import re
from collections.abc import Callable
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from squeegee.errors import SqueegeeError
from squeegee.store import queries

STATIC = Path(__file__).parent / "static"
Params = dict[str, list[str]]
Handler = Callable[[Path, re.Match[str], Params], dict[str, Any]]

_ROUTES: list[tuple[re.Pattern[str], Handler]] = []


def route(pattern: str) -> Callable[[Handler], Handler]:
    """Register a handler for an anchored path pattern."""

    def register(handler: Handler) -> Handler:
        _ROUTES.append((re.compile(f"^{pattern}$"), handler))
        return handler

    return register


@route(r"/api/meta")
def _meta(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.meta(database)


@route(r"/api/runs")
def _runs(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.list_runs(
        database,
        limit=_integer(params, "limit", default=queries.DEFAULT_PAGE),
        cursor=_text(params, "cursor"),
        script=_text(params, "script"),
    )


@route(r"/api/runs/(?P<run_id>\d+)")
def _run(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.run_summary(database, int(match["run_id"]))


@route(r"/api/runs/(?P<run_id>\d+)/stages")
def _stages(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return {"items": queries.run_summary(database, int(match["run_id"]))["stages"]}


@route(r"/api/runs/(?P<run_id>\d+)/stages/(?P<position>\d+)")
def _stage(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.stage_detail(database, int(match["run_id"]), int(match["position"]))


@route(r"/api/runs/(?P<run_id>\d+)/stages/(?P<position>\d+)/records")
def _stage_records(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.stage_records(
        database,
        int(match["run_id"]),
        int(match["position"]),
        status=_text(params, "status"),
        search=_text(params, "q"),
        limit=_integer(params, "limit", default=queries.DEFAULT_PAGE),
        cursor=_text(params, "cursor"),
    )


@route(r"/api/runs/(?P<run_id>\d+)/records/(?P<record_index>\d+)")
def _record(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.record_trace(
        database,
        int(match["run_id"]),
        int(match["record_index"]),
        status=_text(params, "status"),
    )


@route(r"/api/runs/(?P<run_id>\d+)/stages/(?P<position>\d+)/fields")
def _fields(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.stage_fields(database, int(match["run_id"]), int(match["position"]))


@route(r"/api/runs/(?P<run_id>\d+)/stages/(?P<position>\d+)/fields/(?P<field>[^/]+)")
def _field(database: Path, match: re.Match[str], params: Params) -> dict[str, Any]:
    return queries.field_detail(
        database,
        int(match["run_id"]),
        int(match["position"]),
        unquote(match["field"]),
        bins=_integer(params, "bins", default=20),
        top=_integer(params, "top", default=20),
    )


class RequestHandler(SimpleHTTPRequestHandler):
    """Serves the API and the built UI assets, and nothing else."""

    database: Path = Path()
    quiet: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Serve static files from the built assets directory."""
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self) -> None:
        """Answer a GET: the API, a static asset, or the single page."""
        path = urlparse(self.path)
        if path.path.startswith("/api"):
            self._api(path.path, parse_qs(path.query))
            return
        if not STATIC.is_dir():
            self._send(HTTPStatus.OK, _placeholder_page().encode(), "text/html; charset=utf-8")
            return
        # SimpleHTTPRequestHandler.translate_path already normalizes away "..",
        # so static files are looked up through it rather than by hand
        if Path(self.translate_path(self.path)).is_file():
            super().do_GET()
            return
        # anything else is a client-side route, so the single page answers it
        self.path = "/index.html"
        super().do_GET()

    def _api(self, path: str, params: Params) -> None:
        for pattern, handler in _ROUTES:
            match = pattern.match(path)
            if match is None:
                continue
            try:
                self._json(HTTPStatus.OK, handler(self.database, match, params))
            except SqueegeeError as error:
                self._error(HTTPStatus.BAD_REQUEST, "invalid_parameter", str(error))
            return
        self._error(HTTPStatus.NOT_FOUND, "not_found", f"no endpoint at {path}")

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _error(self, status: HTTPStatus, code: str, message: str, parameter: str = "") -> None:
        self._json(
            status,
            {"error": {"code": code, "message": message, "parameter": parameter or None}},
        )

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the signature is fixed
        """Keep the terminal quiet; this is a local viewer, not a web server."""
        if not self.quiet:
            super().log_message(format, *args)


def build_server(database: Path, port: int, quiet: bool = False) -> ThreadingHTTPServer:
    """Bind the server to localhost, or explain why the port will not do.

    Raises:
        SqueegeeError: The port is already in use.
    """
    _register_mime_types()
    bound = {"database": database, "quiet": quiet}
    handler = type("BoundRequestHandler", (RequestHandler,), bound)
    # daemon threads, so Ctrl-C exits instead of waiting on open connections
    server_type = type("SqueegeeServer", (ThreadingHTTPServer,), {"daemon_threads": True})
    try:
        # 127.0.0.1, never 0.0.0.0: the UI has no authentication because it is
        # unreachable from the network, and that has to stay true
        return server_type(("127.0.0.1", port), handler)  # type: ignore[no-any-return]
    except OSError as error:
        if error.errno != errno.EADDRINUSE:  # pragma: no cover - any other bind failure
            raise
        raise SqueegeeError(
            f"port {port} is already in use; pass --port to choose another"
        ) from error


def serve(database: Path, port: int) -> int:
    """Serve until interrupted, and return a process exit code."""
    if not database.is_file():
        raise SqueegeeError(f"no squeegee database at {database}")
    server = build_server(database, port)
    host, bound = server.socket.getsockname()[:2]
    print(f"squeegee ui on http://{host}:{bound}  (ctrl-c to stop)")
    if not STATIC.is_dir():
        print("the UI assets are not built; serving the API and a placeholder page")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


def _register_mime_types() -> None:
    # Windows reads these from the registry, where .js is often text/plain, which
    # makes the browser refuse the module scripts
    for suffix, content_type in (
        (".js", "text/javascript"),
        (".mjs", "text/javascript"),
        (".css", "text/css"),
        (".json", "application/json"),
        (".svg", "image/svg+xml"),
        (".woff2", "font/woff2"),
    ):
        mimetypes.add_type(content_type, suffix)


def _integer(params: Params, name: str, default: int) -> int:
    raw = _text(params, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SqueegeeError(f"{name} must be a whole number, not {raw!r}") from None


def _text(params: Params, name: str) -> str | None:
    values = params.get(name)
    return values[0] if values else None


def _placeholder_page() -> str:
    return (
        "<!doctype html><meta charset='utf-8'><title>squeegee</title>"
        "<body style='font-family: system-ui; max-width: 40rem; margin: 4rem auto'>"
        "<h1>squeegee</h1>"
        "<p>The UI assets are not built. The read-only API is live; "
        "<a href='/api/runs'>/api/runs</a> is a good place to start.</p>"
        "<p>In a checkout, build the UI with <code>make ui</code>.</p>"
    )
