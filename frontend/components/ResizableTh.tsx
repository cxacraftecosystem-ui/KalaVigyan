import type { ThHTMLAttributes } from "react";

import { RECORD_HEAD_CELL } from "@/components/records/recordTable";
import { cn } from "@/lib/utils";

export function ResizableTh({ className, children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th scope="col" {...rest} className={cn(RECORD_HEAD_CELL, "resize-x overflow-hidden", className)}>
      {children}
    </th>
  );
}
