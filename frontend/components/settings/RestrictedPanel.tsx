import { EmptyState } from "@/components/EmptyState";
import { TextLink } from "@/components/ui/TextLink";

export function RestrictedPanel({ title, body }: { title: string; body: string }) {
  return (
    <EmptyState
      title={title}
      body={body}
      actions={
        <TextLink href="/ask" standalone>
          Ask about a craft
        </TextLink>
      }
    />
  );
}
