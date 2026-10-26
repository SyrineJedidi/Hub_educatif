import { Link } from "react-router-dom";
import type { Citation } from "./types";
import { sourceKinds } from "./types";
import { internalUrl, location } from "./format";
export default function SourceList({
  citations,
  anchor,
  headingLevel = 4,
}: {
  citations: Citation[];
  anchor: string;
  headingLevel?: 3 | 4;
}) {
  if (!citations.length) return null;
  const Heading = headingLevel === 3 ? "h3" : "h4";
  return (
    <div className="assistant-sources">
      <Heading>Sources</Heading>
      <ol>
        {citations.map((citation) => {
          const where = [citation.chapter_title, location(citation)]
            .filter(Boolean)
            .join(" · ");
          const url = internalUrl(citation.url);
          return (
            <li
              key={citation.number}
              value={citation.number}
              id={anchor + "-" + citation.number}
              tabIndex={-1}
            >
              <span className="assistant-source-number" aria-hidden="true">
                {citation.number}
              </span>
              <div>
                <p className="assistant-source-title">
                  <span className="visually-hidden">
                    Source {citation.number} :{" "}
                  </span>
                  <strong>{citation.source_title}</strong>
                  {where && <span> · {where}</span>}
                </p>
                <p className="assistant-source-kind">
                  {sourceKinds[citation.source_kind] || citation.source_kind}
                </p>
                {citation.excerpt && (
                  <blockquote className="assistant-excerpt">
                    {citation.excerpt}
                  </blockquote>
                )}
                {url && (
                  <Link className="text-button" to={url}>
                    Ouvrir la source
                    <span className="visually-hidden">
                      {" "}
                      {citation.number} : {citation.source_title}
                    </span>{" "}
                    ↗
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
