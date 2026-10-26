import type { MouseEvent, ReactNode } from "react";
import type { Citation } from "./types";
// Renders the small Markdown subset the model is asked to use, as React text
// nodes only: paragraphs, "- " and "1." lists, **bold**, `code`, fences, [Sn].
type Block =
  | { kind: "p"; text: string }
  | { kind: "code"; text: string }
  | { kind: "ul" | "ol"; items: string[]; start: number };
const INLINE = /\*\*(?:(?!\*\*).)+\*\*|`[^`]+`|\[S\d+(?:\s*[,;]\s*S?\d+)*\]/g;
const BULLET = /^\s*[-*•]\s+/,
  NUMBERED = /^\s*(\d+)[.)]\s+/;
function parse(text: string): Block[] {
  const blocks: Block[] = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const last = blocks[blocks.length - 1];
    if (line.trim().startsWith("```")) {
      const code: string[] = [];
      while (++i < lines.length && !lines[i].trim().startsWith("```"))
        code.push(lines[i]);
      blocks.push({ kind: "code", text: code.join("\n") });
    } else if (BULLET.test(line) || NUMBERED.test(line)) {
      const kind = BULLET.test(line) ? "ul" : "ol";
      const item = line.replace(kind === "ul" ? BULLET : NUMBERED, "");
      if (
        last &&
        (last.kind === "ul" || last.kind === "ol") &&
        last.kind === kind
      )
        last.items.push(item);
      else
        blocks.push({
          kind,
          items: [item],
          start: Number(NUMBERED.exec(line)?.[1] || 1),
        });
    } else if (!line.trim()) blocks.push({ kind: "p", text: "" });
    else {
      const content = line.replace(/^#{1,6}\s+/, "");
      if (last?.kind === "p" && last.text) last.text += "\n" + content;
      else blocks.push({ kind: "p", text: content });
    }
  }
  return blocks.filter((b) => b.kind !== "p" || b.text.trim());
}
export function focusSource(anchor: string, number: number) {
  const target = document.getElementById(anchor + "-" + number);
  target?.scrollIntoView({ block: "nearest" });
  target?.focus({ preventScroll: true });
}
export default function AnswerText({
  text,
  anchor,
  citations,
}: {
  text: string;
  anchor: string;
  citations: Citation[];
}) {
  const known = new Map(citations.map((c) => [c.number, c]));
  function inline(value: string, key: string): ReactNode[] {
    const nodes: ReactNode[] = [];
    let at = 0,
      n = 0;
    for (const match of value.matchAll(INLINE)) {
      const token = match[0],
        index = match.index ?? 0,
        id = key + "-" + n++;
      if (index > at) nodes.push(value.slice(at, index));
      if (token.startsWith("**"))
        nodes.push(<strong key={id}>{inline(token.slice(2, -2), id)}</strong>);
      else if (token.startsWith("`"))
        nodes.push(<code key={id}>{token.slice(1, -1)}</code>);
      else {
        const numbers = (token.match(/\d+/g) || []).map(Number);
        const cited = numbers.filter((value) => known.has(value));
        if (!cited.length) nodes.push(token);
        cited.forEach((value) =>
          nodes.push(
            <a
              key={id + "-" + value}
              className="assistant-cite"
              href={"#" + anchor + "-" + value}
              aria-label={
                "Source " + value + " : " + known.get(value)!.source_title
              }
              onClick={(e: MouseEvent) => {
                e.preventDefault();
                focusSource(anchor, value);
              }}
            >
              {value}
            </a>,
          ),
        );
      }
      at = index + token.length;
    }
    if (at < value.length) nodes.push(value.slice(at));
    return nodes;
  }
  return (
    <div className="assistant-answer-text">
      {parse(text).map((block, i) =>
        block.kind === "p" ? (
          <p key={i}>{inline(block.text, "p" + i)}</p>
        ) : block.kind === "code" ? (
          <pre key={i}>
            <code>{block.text}</code>
          </pre>
        ) : block.kind === "ul" ? (
          <ul key={i}>
            {block.items.map((item, j) => (
              <li key={j}>{inline(item, i + "-" + j)}</li>
            ))}
          </ul>
        ) : (
          <ol key={i} start={block.start}>
            {block.items.map((item, j) => (
              <li key={j}>{inline(item, i + "-" + j)}</li>
            ))}
          </ol>
        ),
      )}
    </div>
  );
}
