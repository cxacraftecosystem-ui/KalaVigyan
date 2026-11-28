import { handleRenew } from "@/lib/server/apiProxy";

export async function POST(request: Request) {
  return handleRenew(request);
}
