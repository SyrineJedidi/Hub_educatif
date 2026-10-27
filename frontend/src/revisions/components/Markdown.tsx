import type { ReactNode } from "react";
// Renders the limited Markdown used by summaries (## titles, lists, **bold**,
// *italic*, `code`) as React elements: no HTML string is ever injected.
function inline(text: string, key: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g;
  let last = 0,
    match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0],
      id = key + "-" + match.index;
    if (token.startsWith("**"))
      parts.push(<strong key={id}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("`"))
      parts.push(<code key={id}>{token.slice(1, -1)}</code>);
    else parts.push(<em key={id}>{token.slice(1, -1)}</em>);
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
export default function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null,
    paragraph: string[] = [];
  const flushParagraph = () => {
    if (paragraph.length) {
      const k = "p" + blocks.length;
      blocks.push(<p key={k}>{inline(paragraph.join(" "), k)}</p>);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      const k = "l" + blocks.length,
        Tag = list.ordered ? "ol" : "ul";
      blocks.push(
        <Tag key={k}>
          {list.items.map((item, i) => (
            <li key={i}>{inline(item, k + i)}</li>
          ))}
        </Tag>,
      );
      list = null;
    }
  };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    const bullet = /^[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\d+[.)]\s+(.*)$/.exec(line);
    if (!line) {
      flushParagraph();
      flushList();
    } else if (heading) {
      flushParagraph();
      flushList();
      const k = "h" + blocks.length;
      const Tag = heading[1].length <= 2 ? "h3" : "h4";
      blocks.push(<Tag key={k}>{inline(heading[2], k)}</Tag>);
    } else if (bullet || numbered) {
      flushParagraph();
      const ordered = !!numbered;
      if (list && list.ordered !== ordered) flushList();
      list ??= { ordered, items: [] };
      list.items.push((bullet || numbered)![1]);
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return <div className="sheet-prose">{blocks}</div>;
}
