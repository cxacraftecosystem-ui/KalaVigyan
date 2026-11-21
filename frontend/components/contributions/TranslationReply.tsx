import { TextLink } from "@/components/ui/TextLink";
import type { BundleReply } from "@/lib/translationContract";

const OUTCOMES: Record<string, string> = { ACCEPTED: "Taken", SHOWN: "Shown in the preview", LISTED: "Listed", REFUSED: "Not taken" };

export function TranslationReply({ reply, sent }: { reply: BundleReply | null; sent: readonly string[] }) {
  if (!reply) return null;
  return (
    <section className="grid gap-3 border-t border-rule pt-4" aria-labelledby="translation-reply-h" role="status">
      <h2 id="translation-reply-h" className="font-reading text-h3 text-ink-1">
        What the checks said
      </h2>
      {reply.message ? <p className="max-w-measure font-ui text-ui text-ink-1">{reply.message}</p> : null}
      {reply.previewUrl ? (
        <p className="font-ui text-ui">
          <TextLink href={reply.previewUrl} external>
            Open the preview of the page
          </TextLink>
        </p>
      ) : null}
      <ul className="grid gap-2">
        {reply.parts.map((part) => (
          <li key={`${part.part}-${part.index}`} className="grid gap-1 font-ui text-label">
            <span className="font-medium text-ink-1">
              {OUTCOMES[part.outcome] ?? part.outcome} · passage {part.index + 1}
              {sent[part.index] ? <span className="text-ink-3"> ({sent[part.index]})</span> : null}
            </span>
            <span className="max-w-measure text-ink-2">{part.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
