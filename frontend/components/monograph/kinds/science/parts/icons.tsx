export function Tick() {
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true">
      <path d="M2.5 7.5 L5.5 10.5 L11.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

export function PlayStagesIcon() {
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true">
      <path d="M3 2 L12 7 L3 12 Z" fill="currentColor" />
    </svg>
  );
}

export function StageTile({ stage, style, viewBox, swatch }: { stage: number; style: string; viewBox: string; swatch?: string }) {
  return (
    <svg className={style} viewBox={viewBox} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect x="-200" y="-200" width="800" height="800" fill={swatch ? `var(${swatch})` : `url(#tile-${stage})`} />
      <rect x="-200" y="-200" width="800" height="800" fill="url(#pt-weave)" />
    </svg>
  );
}

export function PlayIcon() {
  return (
    <svg viewBox="0 0 14 14" aria-hidden="true">
      <path d="M3 1.8 L12 7 L3 12.2 Z" fill="currentColor" />
    </svg>
  );
}
