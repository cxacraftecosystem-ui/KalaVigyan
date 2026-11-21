import { AppShell } from "@/components/AppShell";
import { ConfirmProvider } from "@/components/dialogs/ConfirmDialog";
import { UnsavedChangesProvider } from "@/components/UnsavedChangesGuard";
import { SIGNED_OUT_REDIRECT_SCRIPT } from "@/lib/signedOutRedirect";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: SIGNED_OUT_REDIRECT_SCRIPT }} />
      <ConfirmProvider>
        <UnsavedChangesProvider>
          <AppShell>{children}</AppShell>
        </UnsavedChangesProvider>
      </ConfirmProvider>
    </>
  );
}
