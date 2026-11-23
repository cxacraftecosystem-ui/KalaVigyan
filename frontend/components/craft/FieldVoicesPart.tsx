import { ArtisanWords } from "@/components/craft/ArtisanWords";
import { WorkshopGallery } from "@/components/craft/WorkshopGallery";
import { hasFieldVoices, type FieldVoicesFirst } from "@/lib/fieldVoicesView";
import { cn } from "@/lib/utils";

export function FieldVoicesPart({ first, className }: { first: FieldVoicesFirst | null; className?: string }) {
  if (!hasFieldVoices(first)) return null;
  return (
    <div className={cn("grid min-w-0 gap-16", className)} data-app="" data-testid="craft-field-voices">
      <ArtisanWords first={first.quotes} />
      <WorkshopGallery first={first.images} />
    </div>
  );
}
