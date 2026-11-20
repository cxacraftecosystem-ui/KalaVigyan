import type { Metadata } from "next";

import { ConnectGuide } from "@/components/connect/ConnectGuide";
import { CONNECT_TITLE } from "@/lib/connectClients";
import { connectFacts } from "@/lib/server/mcpGuide";

export const revalidate = 300;

export const metadata: Metadata = { title: CONNECT_TITLE };

export default async function ConnectPage() {
  return <ConnectGuide initial={await connectFacts()} />;
}
