import { scriptJson } from "@/lib/monographRenderKit";

export function DataScript({ id, value }: { id: string; value: unknown }) {
  return <script type="application/json" id={id} dangerouslySetInnerHTML={{ __html: scriptJson(value) }} />;
}
