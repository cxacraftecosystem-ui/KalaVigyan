"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

const LINK = "kv-link";

const components: Components = {
  p: ({ children }) => <p className="mb-[1.05em] last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-ink-1">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  hr: () => <hr className="my-4 border-rule" />,
  ul: ({ children }) => <ul className="mb-[1.05em] list-disc space-y-1 ps-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-[1.05em] list-decimal space-y-1 ps-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  h1: ({ children }) => <h1 className="mb-2 mt-6 font-headline text-h3 text-ink-1 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-6 font-reading text-h3 text-ink-1 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-4 font-ui text-h4 text-ink-1 first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1.5 mt-4 font-ui text-label font-semibold text-ink-2 first:mt-0">{children}</h4>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className={LINK}>
      {children}
    </a>
  ),
  img: ({ src, alt }) => {
    const href = typeof src === "string" && /^https?:/i.test(src.trim()) ? src.trim() : "";
    const label = alt?.trim() || "Image";
    return href ? (
      <a href={href} target="_blank" rel="noreferrer noopener" className={LINK}>
        {label}
      </a>
    ) : (
      <span>{label}</span>
    );
  },
  code: ({ children }) => <code className="rounded-control border border-rule bg-sunk px-1 py-0.5 font-code text-[0.88em] text-ink-1">{children}</code>,
  pre: ({ children }) => <pre className="mb-[1.05em] overflow-x-auto rounded-control border border-rule bg-sunk p-3 font-code text-caption last:mb-0">{children}</pre>,
  blockquote: ({ children }) => <blockquote className="mb-[1.05em] border-s-2 border-rule-strong ps-3 font-reading text-quote italic text-ink-2 last:mb-0">{children}</blockquote>,
  table: ({ children }) => (
    <div className="mb-[1.05em] overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-start font-ui text-ui [font-variant-numeric:lining-nums_tabular-nums]">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-ink-1 py-1.5 pe-4 text-start font-ui text-label font-semibold text-ink-2">{children}</th>,
  td: ({ children }) => <td className="border-b border-rule py-1.5 pe-4 align-top text-ink-1">{children}</td>
};

const SIZE = { body: "text-body", small: "text-body-sm" } as const;

export function Markdown({ text, className, size = "small" }: { text: string; className?: string; size?: keyof typeof SIZE }) {
  return (
    <div className={cn("font-reading text-ink-1", SIZE[size], className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
