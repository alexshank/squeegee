import { Highlight } from "prism-react-renderer";
import { useState } from "react";
import { THEME } from "./StageSource";
import { Label, outlineButton } from "./shared";

// one colour per column, cycling, from the code palette the theme already defines
const RAINBOW = [
  "var(--code-function)",
  "var(--code-string)",
  "var(--code-number)",
  "var(--code-keyword)",
  "var(--accent)",
  "var(--ok)",
];

interface Props {
  label: string;
  value: unknown;
  // what the stage says its raw input is; only consulted once JSON has been ruled out
  format?: string | null;
  maxHeight?: string;
}

/** A value as raw text, highlighted as JSON or CSV when it is one, else plain. */
export function RawValue({ label, value, format = null, maxHeight = "20rem" }: Props) {
  const { text, language } = infer(value, format);
  const [asTable, setAsTable] = useState(false);
  const preStyle = {
    margin: 0,
    fontFamily: "var(--mono)",
    fontSize: "0.8rem",
    lineHeight: 1.5,
    // raw data never wraps: a long line scrolls inside its own box, so lines read
    // as they were written and the panel around it keeps its size
    whiteSpace: "pre" as const,
    maxWidth: "100%",
    maxHeight,
    overflow: "auto",
    // a horizontal scrollbar can draw over the last line, so it gets room of its own
    paddingBottom: "0.75rem",
  };
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Label>{`${label} · ${language ?? "text"}`}</Label>
        {language === "csv" && (
          <button
            type="button"
            onClick={() => setAsTable(!asTable)}
            style={{ ...outlineButton, fontSize: "0.7rem", padding: "0 0.4rem" }}
          >
            {asTable ? "view as text" : "view as table"}
          </button>
        )}
      </div>
      {language === null && <pre style={preStyle}>{text}</pre>}
      {language === "csv" && asTable && <CsvTable text={text} maxHeight={maxHeight} />}
      {language === "csv" && !asTable && (
        <pre style={preStyle}>
          {csvRows(text).map((row, number) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are rebuilt whole on every render
            <div key={number}>
              {row.map((field, column) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: as above
                <span key={column}>
                  {column > 0 && <span style={{ color: "var(--muted)" }}>,</span>}
                  <span style={{ color: RAINBOW[column % RAINBOW.length] }}>{field}</span>
                </span>
              ))}
            </div>
          ))}
        </pre>
      )}
      {language === "json" && (
        <Highlight code={text} language="json" theme={THEME}>
          {({ style, tokens, getLineProps, getTokenProps }) => (
            <pre style={{ ...style, ...preStyle }}>
              {tokens.map((line, number) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the token list is rebuilt whole on every render
                <div key={number} {...getLineProps({ line })}>
                  {line.map((token, index) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: as above
                    <span key={index} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </pre>
          )}
        </Highlight>
      )}
    </>
  );
}

function CsvTable({ text, maxHeight }: { text: string; maxHeight: string }) {
  const [header = [], ...rows] = csvRows(text).map((row) => row.map(unquote));
  const cell = {
    padding: "0.15rem 0.5rem",
    borderBottom: "1px solid var(--border)",
    textAlign: "left" as const,
    // cells never wrap, so a wide row scrolls inside its box instead of stretching the
    // panel, but a line break written inside a quoted field still shows as one
    whiteSpace: "pre" as const,
  };
  return (
    <div style={{ maxWidth: "100%", maxHeight, overflow: "auto", paddingBottom: "0.75rem" }}>
      <table style={{ borderCollapse: "collapse", fontFamily: "var(--mono)", fontSize: "0.8rem" }}>
        <thead>
          <tr>
            {header.map((name, column) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: columns are positional
              <th key={column} style={{ ...cell, color: RAINBOW[column % RAINBOW.length] }}>
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, number) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are positional
            <tr key={number}>
              {row.map((field, column) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: as above
                <td key={column} style={cell}>
                  {field}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A CSV field as its value: surrounding quotes off, doubled quotes single again. */
export function unquote(field: string): string {
  return field.startsWith('"') && field.endsWith('"') && field.length > 1
    ? field.slice(1, -1).replaceAll('""', '"')
    : field;
}

export function infer(
  value: unknown,
  format: string | null,
): { text: string; language: "json" | "csv" | null } {
  if (typeof value !== "string") return { text: JSON.stringify(value, null, 2), language: "json" };
  try {
    const parsed: unknown = JSON.parse(value);
    if (parsed !== null && typeof parsed === "object") {
      return { text: JSON.stringify(parsed, null, 2), language: "json" };
    }
  } catch {
    // not JSON, so it is whatever the stage says it is, or plain text
  }
  // a JSON Lines file parses as no single value, but is still JSON to highlight; a
  // single line that failed to parse is shown as the text it is
  if (format === "json" && value.includes("\n")) return { text: value, language: "json" };
  return { text: value, language: format === "csv" || looksLikeCsv(value) ? "csv" : null };
}

// one line with commas is as likely prose as CSV, so it takes a header and a row
// that agree on a column count before text is called CSV without the stage saying so
function looksLikeCsv(text: string): boolean {
  const columns = csvRows(text).map((row) => row.length);
  return (
    columns.length >= 2 && (columns[0] ?? 0) >= 2 && columns.every((count) => count === columns[0])
  );
}

/**
 * Split CSV text into rows of fields, each field's text kept as written.
 *
 * Quoting decides both splits, so a line break inside a quoted field stays in
 * that field rather than starting a new row.
 */
export function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  // an escaped "" flips twice, so it leaves the quoting as it was
  let quoted = false;
  for (const character of text) {
    // a quote only means quoting in a field that opened with one, so a stray inch
    // mark in an unquoted field cannot swallow the rest of the text
    if (character === '"' && (field === "" || field.startsWith('"'))) quoted = !quoted;
    if (!quoted && character === ",") {
      row.push(field);
      field = "";
    } else if (!quoted && character === "\n") {
      rows.push([...row, field]);
      row = [];
      field = "";
    } else if (quoted || character !== "\r") {
      field += character;
    }
  }
  rows.push([...row, field]);
  // a trailing newline or a blank line is not a row
  return rows.filter((fields) => fields.length > 1 || fields[0] !== "");
}
