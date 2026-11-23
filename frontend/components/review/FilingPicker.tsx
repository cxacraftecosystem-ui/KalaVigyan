"use client";

import { useMemo } from "react";

import { FieldBlock } from "@/components/FormControls";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { useCraftCatalogue } from "@/lib/craftCatalogue";
import { filingOptions } from "@/lib/reviewQueueView";

const FILE_UNDER = "File under";

export function FilingPicker({ value, onChange, current }: { value: string; onChange: (next: string) => void; current: string | null }) {
  const { catalogue } = useCraftCatalogue();
  const options = useMemo(() => (catalogue ? filingOptions(catalogue) : []), [catalogue]);
  const hint = current ? `Approve keeps it under ${current} unless you choose a craft or a family's science.` : "Approve keeps it where it is unless you choose a craft or a family's science.";
  return (
    <FieldBlock label={FILE_UNDER} hint={hint}>
      <SearchableSelect
        value={value}
        onChange={onChange}
        options={options}
        ariaLabel={FILE_UNDER}
        placeholder="Where it is now"
        disabled={!catalogue}
        clearable
        clearLabel="Keep it where it is"
      />
    </FieldBlock>
  );
}
