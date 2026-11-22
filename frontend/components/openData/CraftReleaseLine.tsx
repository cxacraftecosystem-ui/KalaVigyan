import { TextLink } from "@/components/ui/TextLink";
import type { CraftRelease } from "@/lib/openDataContract";

export function craftReleaseLabel(release: CraftRelease): string {
  return `Its open data, version ${release.version}`;
}

export function CraftReleaseLine({ release }: { release: CraftRelease }) {
  return (
    <dl className="grid gap-1 font-ui text-label text-ink-3" data-testid="craft-release-doi">
      <div className="flex flex-wrap gap-x-2">
        <dt>{craftReleaseLabel(release)}</dt>
        <dd className="kv-citethis-url">
          <TextLink href={release.doiUrl} external>
            {release.doiUrl}
          </TextLink>
        </dd>
      </div>
    </dl>
  );
}
