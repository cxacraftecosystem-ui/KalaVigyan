export function HeldReasons({ reasons }: { reasons: readonly string[] }) {
  if (!reasons.length) return null;
  return (
    <div className="grid gap-1 border-s-2 border-madder ps-3" data-testid="held-reasons">
      <p className="text-label font-ui text-ink-1">Held for a person to check</p>
      <ul className="grid gap-1">
        {reasons.map((reason) => (
          <li key={reason} className="text-label font-ui text-ink-2">
            {reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
