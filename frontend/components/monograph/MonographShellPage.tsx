import { AuthoredShell } from "@/components/monograph/AuthoredShell";
import { MonographFrame, type MonographPageProps } from "@/components/monograph/MonographFrame";
import { MonographRail } from "@/components/monograph/MonographRail";
import { deferredRest } from "@/lib/monographDeferred";
import { railChapters } from "@/lib/monographRenderLayout";
import { shownPage } from "@/lib/monographShownPage";

export function MonographShellPage({ document: given, deferred = false }: MonographPageProps) {
  const { document, plan } = shownPage(given);
  const rest = deferredRest(given, plan, deferred);
  return (
    <MonographFrame document={document} given={given} dataDeferred={rest !== null}>
      <MonographRail chapters={railChapters(plan)} />
      <AuthoredShell document={document} shell={document.shell ?? ""} rest={rest} />
    </MonographFrame>
  );
}
