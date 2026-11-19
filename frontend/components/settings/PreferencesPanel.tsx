"use client";

import { RecordSection } from "@/components/records/RecordSection";
import {
  CONTRAST_OPTIONS,
  MOTION_OPTIONS,
  TEXT_OPTIONS,
  THEME_OPTIONS,
  contrastLine,
  motionLine,
  textLine,
  themeLine
} from "@/components/settings/preferenceLines";
import { useDeviceMatches } from "@/components/settings/useDeviceMatches";
import { useThemePreferences } from "@/components/ThemeProvider";
import { SegmentedChoice, type SegmentOption } from "@/components/ui/SegmentedChoice";
import { REDUCED_MOTION_QUERY } from "@/lib/motion";
import { contrastChoice, contrastIsHigh, MORE_CONTRAST_MEDIA_QUERY, type ThemeChoice } from "@/lib/preferences";

type RowProps = {
  title: string;
  value: string;
  options: SegmentOption[];
  onChange: (value: string) => void;
  effect: string;
};

function PreferenceRow({ title, value, options, onChange, effect }: RowProps) {
  return (
    <div className="grid gap-3 border-t border-rule py-5 first:border-t-0 first:pt-0 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)] md:gap-8">
      <h3 className="font-ui text-h4 text-ink-1">{title}</h3>
      <div className="grid min-w-0 justify-items-start gap-2">
        <SegmentedChoice label={title} value={value} options={options} onChange={onChange} />
        <p className="font-ui text-label text-ink-2" aria-live="polite">
          {effect}
        </p>
      </div>
    </div>
  );
}

export function PreferencesPanel() {
  const { preferences, resolvedTheme, update, saving, error } = useThemePreferences();
  const moreContrast = useDeviceMatches(MORE_CONTRAST_MEDIA_QUERY);
  const lessMotion = useDeviceMatches(REDUCED_MOTION_QUERY);
  const highNow = contrastIsHigh(preferences.highContrast, moreContrast);

  return (
    <RecordSection
      title="Display"
      description="Theme, contrast, text size and motion. Your choices follow you to every device you sign in on."
      aside={<span data-testid="contrast-in-effect">{highNow ? "High contrast in effect" : "Standard contrast in effect"}</span>}
      testId="display-preferences"
    >
      <div className="grid">
        <PreferenceRow title="Theme" value={preferences.theme} options={THEME_OPTIONS} onChange={(next) => update({ theme: next as ThemeChoice })} effect={themeLine(preferences.theme, resolvedTheme)} />
        <PreferenceRow title="Contrast" value={preferences.highContrast} options={CONTRAST_OPTIONS} onChange={(next) => update({ highContrast: contrastChoice(next) })} effect={contrastLine(preferences.highContrast, moreContrast)} />
        <PreferenceRow title="Text size" value={preferences.largerText ? "larger" : "standard"} options={TEXT_OPTIONS} onChange={(next) => update({ largerText: next === "larger" })} effect={textLine(preferences.largerText)} />
        <PreferenceRow title="Motion" value={preferences.reducedMotion ? "reduced" : "device"} options={MOTION_OPTIONS} onChange={(next) => update({ reducedMotion: next === "reduced" })} effect={motionLine(preferences.reducedMotion, lessMotion)} />
      </div>
      <p role="status" className="font-ui text-label text-ink-3">
        {error ?? (saving ? "Saving your choices" : "")}
      </p>
    </RecordSection>
  );
}
