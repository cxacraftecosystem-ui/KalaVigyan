export function GeneratedCode({ id, html }: { id: string; html: string }) {
  return (
    <pre
      id={id}
      className="max-h-80 min-w-0 max-w-full overflow-auto rounded-plate border border-rule bg-sunk p-3 font-code text-label text-ink-2"
      tabIndex={0}
      aria-label="Code"
      data-testid="generated-code"
    >
      <code>{html}</code>
    </pre>
  );
}
