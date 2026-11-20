"use client";

import { useMemo } from "react";

import { FieldBlock } from "@/components/FormControls";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { physicalOptions } from "@/lib/mapPhysical";
import type { MapLayerList } from "@/lib/regionContract";
import { layerOptions } from "@/lib/regionView";

export const CRAFT_PLACES_LABEL = "Craft places";

export function pickerOptions(list: MapLayerList | null): ReturnType<typeof physicalOptions> {
  return [...physicalOptions(), ...(list ? layerOptions(list) : [])];
}

export function LayerPicker({ list, value, onChange }: { list: MapLayerList | null; value: string | null; onChange: (id: string | null) => void }) {
  const options = useMemo(() => pickerOptions(list), [list]);
  return (
    <div className="w-full sm:max-w-sm" data-testid="layer-picker">
      <FieldBlock label="Show on the map">
        <SearchableSelect
          value={value ?? ""}
          options={options}
          noneLabel={CRAFT_PLACES_LABEL}
          onChange={(next) => onChange(next || null)}
          searchable
          advanceOnSelect={false}
        />
      </FieldBlock>
    </div>
  );
}
