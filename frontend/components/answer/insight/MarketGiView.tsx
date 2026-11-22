"use client";

import Link from "next/link";
import { BadgeCheck, Clock, MinusCircle, type LucideIcon } from "lucide-react";

import { CitedText } from "@/components/answer/ProseBlockView";
import type { GiStatus, MarketGiBlock, PriceRange } from "@/lib/explainerInsight";
import { GI_STATUS_LABEL, giFacts, priceMeta } from "@/lib/insightView";
import { bySentence, type SentenceGroup } from "@/lib/sentenceGroups";
import { cn } from "@/lib/utils";

const STATUS_LOOK: Record<GiStatus["status"], { Icon: LucideIcon; className: string }> = {
  REGISTERED: { Icon: BadgeCheck, className: "text-ink-1" },
  APPLIED: { Icon: Clock, className: "text-ink-2" },
  WITHDRAWN: { Icon: MinusCircle, className: "text-ink-3" }
};

const PROSE = "max-w-measure font-reading text-body-sm text-ink-1";

function GiStatusBadge({ status }: { status: GiStatus["status"] }) {
  const look = STATUS_LOOK[status];
  return (
    <span className={cn("kv-tag inline-flex w-fit items-center gap-1", look.className)} data-testid="gi-status" data-status={status}>
      <look.Icon className="h-3.5 w-3.5" aria-hidden />
      {GI_STATUS_LABEL[status]}
    </span>
  );
}

function GiRecord({ gi, id }: { gi: GiStatus; id: string }) {
  const facts = giFacts(gi);
  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-3" data-testid="gi-record">
      {facts.length > 0 ? (
        <dl className="grid min-w-0 grid-cols-[repeat(2,minmax(0,1fr))] gap-x-6 border-t border-ink-1 sm:grid-cols-[repeat(3,minmax(0,1fr))]">
          {facts.map((fact) => (
            <div key={fact.label} className="grid min-w-0 gap-0.5 border-b border-rule py-2.5" data-testid="gi-fact">
              <dt className="font-ui text-label text-ink-3">{fact.label}</dt>
              <dd className="break-words font-ui text-ui font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{fact.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {gi.proprietors.length > 0 ? (
        <p className="min-w-0 break-words font-ui text-ui font-normal text-ink-2" data-testid="gi-proprietors">
          <span className="font-semibold text-ink-1">{gi.proprietors.length === 1 ? "Proprietor" : "Proprietors"}: </span>
          {gi.proprietors.join("; ")}
        </p>
      ) : null}
      <CitedText id={`${id}-gi`} sentences={gi.sentences} className={PROSE} />
    </div>
  );
}

function Imitation({ block }: { block: MarketGiBlock }) {
  return (
    <section className="grid min-w-0 gap-1.5 border-t border-rule pt-3" aria-label="Signs of imitation" data-testid="gi-imitation">
      <h4 className="kicker">Signs of imitation</h4>
      <CitedText id={`${block.id}-imitation`} sentences={block.imitation} className={PROSE} />
    </section>
  );
}

function Price({ price }: { price: PriceRange }) {
  return (
    <li className="grid min-w-0 content-start gap-0.5" data-testid="price-range">
      <span className="break-words font-ui text-ui-lg font-semibold text-ink-1 [font-variant-numeric:lining-nums_tabular-nums]">{price.stated}</span>
      <span className="font-ui text-label text-ink-3" data-testid="price-meta">
        {priceMeta(price)}
      </span>
    </li>
  );
}

function PriceSentence({ group }: { group: SentenceGroup<PriceRange> }) {
  return (
    <li className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1 border-b border-rule py-3 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)] md:gap-x-8" data-testid="price-sentence">
      <ul className="grid min-w-0 content-start gap-2">
        {group.items.map((price, index) => (
          <Price key={`${index}-${price.stated}`} price={price} />
        ))}
      </ul>
      <CitedText id={group.sentence.id} sentences={[group.sentence]} className={PROSE} />
    </li>
  );
}

export function MarketGiView({ block }: { block: MarketGiBlock }) {
  if (!block.gi && block.imitation.length === 0 && block.prices.length === 0) return null;
  return (
    <article className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4" data-testid="market-gi">
      <header className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1.5">
        <h3 className="min-w-0 break-words font-reading text-h3 text-ink-1">
          <Link href={block.craft.path} className="kv-link">
            {block.craft.name}
          </Link>
        </h3>
        {block.gi ? <GiStatusBadge status={block.gi.status} /> : null}
      </header>
      {block.gi ? <GiRecord gi={block.gi} id={block.id} /> : null}
      {block.imitation.length > 0 ? <Imitation block={block} /> : null}
      {block.prices.length > 0 ? (
        <section className="grid min-w-0 gap-2" aria-label="Prices">
          <h4 className="kicker">Prices</h4>
          <ul className="grid min-w-0 grid-cols-[minmax(0,1fr)] border-t border-ink-1">
            {bySentence(block.prices, (price) => price.sentence).map((group) => (
              <PriceSentence key={group.key} group={group} />
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
