import Image from "next/image";
import Link from "next/link";

import { CITATION_PROMISE, CITE_DATASET_LINK, DATASET_PAGE, INSTITUTION_LINE } from "@/components/landing/Footer";

export type PartnerMark = { key: string; name: string; src: string; width: number; height: number; shape: "seal" | "wide" };

export const PARTNERS_LABEL = "Partners";
const KEPT_WHOLE = "AI-Enabled";

export function InstitutionLine() {
  const at = INSTITUTION_LINE.indexOf(KEPT_WHOLE);
  if (at < 0) return <>{INSTITUTION_LINE}</>;
  return (
    <>
      {INSTITUTION_LINE.slice(0, at)}
      <span className="whitespace-nowrap">{KEPT_WHOLE}</span>
      {INSTITUTION_LINE.slice(at + KEPT_WHOLE.length)}
    </>
  );
}

export const PARTNER_MARKS: readonly PartnerMark[] = [
  { key: "iit-kharagpur", name: "Indian Institute of Technology Kharagpur", src: "/partners/iit-kharagpur.svg", width: 268, height: 300, shape: "seal" },
  {
    key: "dc-handicrafts",
    name: "Development Commissioner (Handicrafts), Ministry of Textiles, Government of India",
    src: "/partners/dc-handicrafts.webp",
    width: 600,
    height: 221,
    shape: "wide"
  }
];

function Mark({ mark }: { mark: PartnerMark }) {
  return (
    <li className="kv-partner" data-shape={mark.shape} data-testid="partner-mark">
      <span className="kv-partner-plate">
        <Image src={mark.src} alt={mark.name} width={mark.width} height={mark.height} unoptimized loading="lazy" className="kv-partner-img" />
      </span>
      <span className="kv-partner-name" aria-hidden>
        {mark.name}
      </span>
    </li>
  );
}

export function PartnersFooter() {
  return (
    <footer className="kv-footer kv-partners" data-testid="institution-footer">
      <div className="kv-shell-wrap">
        <div className="kv-partners-grid">
          <div className="kv-partners-text">
            <p className="kicker">{PARTNERS_LABEL}</p>
            <p className="kv-partners-line font-reading text-lede text-ink-1">
              <InstitutionLine />
            </p>
          </div>
          <ul className="kv-partner-marks" aria-label={PARTNERS_LABEL}>
            {PARTNER_MARKS.map((mark) => (
              <Mark key={mark.key} mark={mark} />
            ))}
          </ul>
        </div>
        <p className="kv-partners-promise">
          {CITATION_PROMISE}{" "}
          <Link href={DATASET_PAGE} className="kv-link font-normal">
            {CITE_DATASET_LINK}
          </Link>{" "}
          <Link href="/privacy" className="kv-link font-normal">
            Privacy
          </Link>
        </p>
      </div>
    </footer>
  );
}
