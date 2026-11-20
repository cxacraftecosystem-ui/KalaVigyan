import { revalidatePath, revalidateTag } from "next/cache";

import { handleRevalidate } from "@/lib/server/revalidation";

const IMMEDIATELY = { expire: 0 };

export async function POST(request: Request) {
  return handleRevalidate(request, {
    env: process.env,
    refreshPath: (path) => revalidatePath(path),
    refreshTag: (tag) => revalidateTag(tag, IMMEDIATELY)
  });
}
