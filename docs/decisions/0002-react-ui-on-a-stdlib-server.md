# 0002. A built React app served by the standard library

- Status: accepted
- Date: 2026-09-18
- Supersedes: the FastAPI choice in the first draft of the UI specification

## Context

The UI is a local, read-only explorer for the SQLite database. The first draft chose FastAPI plus a vanilla JavaScript page, served as an optional `squeegee[ui]` extra.

A browser cannot open SQLite directly. It has no filesystem handle and no driver, so a React app "talking to SQLite" means one of two things: a small server process that runs the SQL and returns JSON, or SQLite compiled to WebAssembly running inside the page over the fetched database file.

## Decision

The UI is a React application, built ahead of time, served by Python's standard library `http.server` alongside a small read-only JSON API. There is no FastAPI, no Uvicorn, and no `squeegee[ui]` extra. The entire package has no third-party runtime dependencies.

Components are written by hand with plain CSS. The icon set is Lucide.

## Rationale

1. **The API surface is tiny.** Eight read-only `GET` endpoints with cursor pagination. A `ThreadingHTTPServer` subclass with a path match and `json.dumps` covers it in roughly a hundred and fifty lines. FastAPI would earn its weight on a real API with validation, auth, and mutation; here it is a dependency in exchange for routing sugar.
2. **It makes the whole package dependency-free.** Previously only the core was. Now `uvx squeegee ui` works with nothing to install and nothing to resolve, which matters for a tool whose whole pitch is being reached for casually.
3. **React is a build-time dependency only.** Contributors need Node; users never do. The wheel ships the built assets.
4. **WebAssembly SQLite was considered and rejected.** Running `sql.js` in the page removes the server entirely, but costs about 1.5MB of WASM, loads the whole database into browser memory, and reimplements the query layer in JavaScript. The lazy-loading variant, `sql.js-httpvfs`, requires the database file to be immutable, which conflicts with reading a database that a run is actively writing.
5. **React rather than vanilla JavaScript** because the record trace and field analytics screens carry real client state: filters, pagination cursors, an expanded JSON tree, a selected field, diff highlighting between adjacent stages. Hand-rolled DOM updates for that get worse over time, and the developer writing this prefers React.

## Consequences

- The repository gains a frontend toolchain: Vite, React, TypeScript in strict mode, and Biome. See [engineering-standards.md](../engineering-standards.md).
- `src/squeegee/ui/static/` holds build output, is gitignored, and is produced by CI on release. A Hatch build hook fails the wheel build if the assets are missing, so a wheel can never ship a UI that 404s.
- The server is single-user and localhost-only by construction. It binds `127.0.0.1`, opens SQLite read-only, serves same-origin so no CORS is needed, and has no authentication because it has no attack surface worth naming and never writes.
- Routing, pagination, and error responses are written by hand and must be tested directly, since no framework is validating them.

## Revisit when

- The API grows past roughly a dozen endpoints or needs request bodies, at which point a framework starts paying for itself.
