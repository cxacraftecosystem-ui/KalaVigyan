"use client";

import { ReliabilityMark } from "@/components/editorial/EvidenceMark";
import { CitedText, useCiteMaps } from "@/components/landing/CitedText";
import type { LandingContent } from "@/components/landing/landingContent";
import { TextLink } from "@/components/ui/TextLink";
import { citationCluster, entryByline, shortTitle, type ClusterEntry } from "@/lib/citationCluster";

export const READING_KEYS = [
  { key: "a", text: "The numerals after a sentence name its sources, numbered as they first appear on the page." },
  { key: "b", text: "Each opens the source’s own words, quoted exactly." },
  { key: "c", text: "Then where they sit in the source," },
  { key: "d", text: "and how far to trust it: A for peer-reviewed or official, B for a reputable reference, C for the general web, D for a source we cannot yet place." }
] as const;

function Mark({ shown, letter }: { shown: boolean; letter: string }) {
  if (!shown) return null;
  return (
    <span className="kv-mk" data-key={letter} aria-hidden>
      {letter}
    </span>
  );
}

function QuoteCard({ entry, marked }: { entry: ClusterEntry; marked: boolean }) {
  const quoted = entry.citations.find((citation) => citation.quote) ?? entry.citations[0];
  const source = entry.source;
  return (
    <figure className="kv-qcard">
      <figcaption>
        <Mark shown={marked} letter="a" />
        <b>{entry.number}</b>
        <strong>{source ? shortTitle(source.title) : null}</strong>
        <span>{entryByline(source)}</span>
      </figcaption>
      {quoted?.quote ? (
        <blockquote>
          <Mark shown={marked} letter="b" />
          {`“${quoted.quote}”`}
        </blockquote>
      ) : null}
      <p className="kv-qmeta">
        {quoted?.locator ? (
          <span>
            <Mark shown={marked} letter="c" />
            {quoted.locator}
          </span>
        ) : null}
        {source?.reliability ? (
          <span>
            <Mark shown={marked} letter="d" />
            <ReliabilityMark reliability={source.reliability} />
          </span>
        ) : null}
      </p>
    </figure>
  );
}

export function exampleLine(name: string): string {
  return `An example from ${name}`;
}

export function HowToRead({ content }: { content: LandingContent }) {
  const cite = useCiteMaps(content.sources);
  const demo = content.demo;
  if (!demo) return null;
  const entries = citationCluster(demo.citations, cite.numbers, cite.sourcesById).entries;
  return (
    <section className="kv-howto" aria-labelledby="how-to-read-h" data-testid="how-to-read">
      <div className="kv-shell-wrap">
        <div className="kv-howto-grid">
          <div>
            <p className="kv-chapter-no">How to read a page</p>
            <h2 id="how-to-read-h" className="m-0 font-headline text-h2 text-ink-1">
              Every numeral opens a source.
            </h2>
            <p className="kv-howto-example">
              {content.craftPath ? (
                <TextLink href={content.craftPath} standalone>
                  {exampleLine(content.name)}
                </TextLink>
              ) : (
                exampleLine(content.name)
              )}
            </p>
            <p className="kv-howto-sentence">
              <CitedText sentence={demo} cite={cite} />
            </p>
            <ol className="kv-howto-keys">
              {READING_KEYS.map((item) => (
                <li key={item.key}>
                  <b className="kv-mk" aria-hidden>
                    {item.key}
                  </b>
                  <span>{item.text}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="kv-howto-cards" role="group" aria-label="What the numerals open">
            {entries.map((entry, index) => (
              <QuoteCard key={entry.sourceId} entry={entry} marked={index === 0} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
