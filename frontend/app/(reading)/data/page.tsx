import type { Metadata } from "next";

import { OpenDataScreen } from "@/components/openData/OpenDataScreen";
import { serverOpenData } from "@/lib/server/openDataServer";

export const metadata: Metadata = {
  title: "Open data",
  description: "KalaVigyan's cited knowledge of India's crafts as an open dataset under CC BY 4.0, with a DOI for every release."
};

export default async function OpenDataPage() {
  return <OpenDataScreen initial={await serverOpenData()} />;
}
