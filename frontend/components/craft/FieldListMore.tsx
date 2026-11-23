import type { FieldListView } from "@/components/craft/useFieldList";
import { TextLink } from "@/components/ui/TextLink";
import { SHOW_FEWER, showAllLabel } from "@/lib/fieldVoicesView";

function statusText(list: FieldListView<unknown>, noun: string): string {
  if (list.phase === "reading") return `Reading all ${list.total} ${noun}.`;
  if (list.phase === "failed") return `The ${noun} could not be read. Press ${showAllLabel(list.total)} to try again.`;
  return "";
}

export function FieldListMore({ list, noun, controls }: { list: FieldListView<unknown>; noun: string; controls: string }) {
  if (!list.expandable) return null;
  return (
    <div className="grid gap-1">
      <p>
        <TextLink onClick={list.toggle} expanded={list.open} controls={controls} standalone>
          {list.open ? SHOW_FEWER : showAllLabel(list.total)}
        </TextLink>
      </p>
      <p role="status" className="font-ui text-label text-ink-2" data-testid="field-list-status">
        {statusText(list, noun)}
      </p>
    </div>
  );
}
