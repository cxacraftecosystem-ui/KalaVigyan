import Link from "next/link";

import { cn } from "@/lib/utils";

export const INSTITUTION_LINE = "KalaVigyan, from IIT Kharagpur and its Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform.";
export const CITATION_PROMISE = "Every reader sentence is cited to a verbatim quote.";
export const DATASET_PAGE = "/data";
export const CITE_DATASET_LINK = "Cite this dataset";

export function InstitutionFooter({ className }: { className?: string }) {
  return (
    <footer className={cn("kv-footer", className)} data-testid="institution-footer">
      <div className="kv-shell-wrap">
        <p>
          {INSTITUTION_LINE} {CITATION_PROMISE}{" "}
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
