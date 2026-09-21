import { Check, Copy } from "lucide-react";
import { Highlight, themes } from "prism-react-renderer";
import { useState } from "react";

interface Props {
  source: string;
  name: string;
  sha: string;
}

/** The stage's source exactly as it ran: monospace, highlighted, line numbered. */
export function StageSource({ source, name, sha }: Props) {
  const [copied, setCopied] = useState(false);
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

  return (
    <section style={{ border: "1px solid var(--border)", overflow: "hidden" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.25rem 0.5rem",
          background: "var(--surface)",
          borderBottom: "1px solid var(--border)",
          fontFamily: "var(--mono)",
          fontSize: "0.75rem",
          color: "var(--muted)",
        }}
      >
        <span>
          {name} · {sha.slice(0, 8)}
        </span>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(source);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
            background: "none",
            border: "1px solid var(--border)",
            color: "var(--muted)",
            cursor: "pointer",
            font: "inherit",
            padding: "0 0.4rem",
          }}
        >
          {copied ? <Check size={11} aria-hidden /> : <Copy size={11} aria-hidden />}
          {copied ? "copied" : "copy"}
        </button>
      </header>
      <Highlight
        code={source.trimEnd()}
        language="python"
        theme={dark ? themes.vsDark : themes.github}
      >
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre
            style={{
              ...style,
              margin: 0,
              padding: "0.5rem 0",
              fontFamily: "var(--mono)",
              fontSize: "0.8rem",
              lineHeight: 1.55,
              // long lines scroll, because wrapped Python misleads about indentation
              overflowX: "auto",
            }}
          >
            {tokens.map((line, number) => (
              <div key={`${number}-${line.length}`} {...getLineProps({ line })}>
                <span
                  style={{
                    display: "inline-block",
                    width: "2.5rem",
                    textAlign: "right",
                    paddingRight: "0.75rem",
                    color: "var(--muted)",
                    userSelect: "none",
                  }}
                >
                  {number + 1}
                </span>
                {line.map((token, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: the token list is rebuilt whole on every render
                  <span key={`${number}-${index}`} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </section>
  );
}
