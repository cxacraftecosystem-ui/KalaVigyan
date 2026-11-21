import { MonographDocumentPage } from "@/components/monograph/MonographDocumentPage";
import type { MonographPageProps } from "@/components/monograph/MonographFrame";
import { MonographShellPage } from "@/components/monograph/MonographShellPage";

export { deferredRest, railAfterMasthead } from "@/lib/monographDeferred";
export type { MonographPageProps };

export function MonographPage(props: MonographPageProps) {
  return props.document.shell !== null ? <MonographShellPage {...props} /> : <MonographDocumentPage {...props} />;
}
