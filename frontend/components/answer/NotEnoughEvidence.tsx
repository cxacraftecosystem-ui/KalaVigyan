import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";

export const RESEARCH_TITLE = "Research this question from the sources";
export const RESEARCH_BODY = "Every answer here is drawn from cited sources. Live research finds and reads new ones for this question.";

export function NotEnoughEvidence({ onResearch }: { onResearch?: () => void }) {
  return (
    <div className="mx-auto w-full max-w-measure" data-testid="not-enough-evidence">
      <EmptyState
        title={RESEARCH_TITLE}
        body={RESEARCH_BODY}
        actions={
          onResearch ? (
            <Button variant="quiet" onClick={onResearch}>
              Research it live
            </Button>
          ) : null
        }
      />
    </div>
  );
}
