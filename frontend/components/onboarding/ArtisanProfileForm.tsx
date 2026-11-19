"use client";

import { useEffect, useMemo, useState } from "react";

import { FormAlert } from "@/components/auth/FormAlert";
import { FieldBlock } from "@/components/FormControls";
import { CraftPicker, type PickedCraft } from "@/components/onboarding/CraftPicker";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { SegmentedChoice } from "@/components/ui/SegmentedChoice";
import { apiErrorMessage } from "@/lib/api";
import { answerLanguagesOf, type AnswerLanguage } from "@/lib/answerLanguages";
import { fetchAskConfig } from "@/lib/askConfig";
import {
  CREDIT_LABELS,
  CREDIT_MODES,
  creditPreview,
  fetchDistricts,
  firstName,
  saveArtisanProfile,
  type ArtisanPart,
  type CreditMode,
  type DistrictList,
  type ProfileView
} from "@/lib/profileContract";

const CREDIT_OPTIONS = CREDIT_MODES.map((value) => ({ value, label: CREDIT_LABELS[value] }));
const SAVE_FAILED = "Couldn't save. Try again.";
const FEW_ARTISANS = "Few artisans of some crafts live in one district, so this may still point to you.";

export function ArtisanProfileForm({ current, accountName, action, onSaved }: { current: ArtisanPart | null; accountName: string; action: string; onSaved: (view: ProfileView) => void }) {
  const [crafts, setCrafts] = useState<PickedCraft[]>(current?.crafts.map((craft) => ({ slug: craft.slug, displayName: craft.displayName })) ?? []);
  const [places, setPlaces] = useState<DistrictList | null>(null);
  const [languages, setLanguages] = useState<AnswerLanguage[]>([]);
  const [stateLgd, setStateLgd] = useState(current?.district ? String(current.district.state.lgd) : "");
  const [districtLgd, setDistrictLgd] = useState(current?.district ? String(current.district.lgd) : "");
  const [language, setLanguage] = useState(current?.spokenLanguage ?? "");
  const [adult, setAdult] = useState(Boolean(current));
  const [mode, setMode] = useState<CreditMode>(current?.credit.mode ?? "FIRST_NAME");
  const [name, setName] = useState(current?.credit.name ?? accountName);
  const [shortName, setShortName] = useState(current?.credit.shortName ?? firstName(accountName));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDistricts().then(setPlaces).catch(() => setError("Couldn't load the districts. Reload the page."));
    fetchAskConfig()
      .then((raw) => setLanguages(answerLanguagesOf(raw.languages)))
      .catch(() => setLanguages([]));
  }, []);

  const state = places?.states.find((each) => String(each.lgd) === stateLgd) ?? null;
  const district = state?.districts.find((each) => String(each.lgd) === districtLgd) ?? null;
  const shownDistrict = state && district ? { lgd: district.lgd, name: district.name, state: { lgd: state.lgd, name: state.name } } : null;
  const shownName = mode === "FULL_NAME" ? name : shortName;
  const preview = crafts[0] ? creditPreview(mode, shownName, crafts[0].displayName, shownDistrict) : null;
  const ready = crafts.length > 0 && Boolean(district) && Boolean(language) && adult && (mode === "CRAFT_AND_DISTRICT" || shownName.trim().length > 0);
  const stateOptions = useMemo(() => places?.states.map((each) => ({ value: String(each.lgd), label: each.name })) ?? [], [places]);
  const districtOptions = state?.districts.map((each) => ({ value: String(each.lgd), label: each.name })) ?? [];
  const languageOptions = languages.map((each) => ({ value: each.code, label: each.autonym, hint: each.label }));

  async function save() {
    if (!ready || !district) return;
    setBusy(true);
    setError(null);
    try {
      const credit = { mode, name: mode === "FULL_NAME" ? name : null, shortName: mode === "FIRST_NAME" ? shortName : null };
      onSaved(await saveArtisanProfile({ craftSlugs: crafts.map((craft) => craft.slug), districtLgd: district.lgd, spokenLanguage: language, adultConfirmed: true, credit }));
    } catch (cause) {
      setError(apiErrorMessage(cause, SAVE_FAILED));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5" data-testid="artisan-profile-form">
      <div className="grid gap-1.5">
        <span className="field-label">Which crafts do you practise?</span>
        <CraftPicker picked={crafts} onChange={setCrafts} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldBlock label="State">
          <SearchableSelect value={stateLgd} onChange={(next) => { setStateLgd(next); setDistrictLgd(""); }} options={stateOptions} ariaLabel="State" placeholder="Choose a state" disabled={!places} />
        </FieldBlock>
        <FieldBlock label="District">
          <SearchableSelect value={districtLgd} onChange={setDistrictLgd} options={districtOptions} ariaLabel="District" placeholder="Choose a district" disabled={!state} />
        </FieldBlock>
      </div>
      <FieldBlock label="Which language do you speak?">
        <SearchableSelect value={language} onChange={setLanguage} options={languageOptions} ariaLabel="Which language do you speak?" placeholder="Choose a language" />
      </FieldBlock>
      <label className="flex min-h-target items-center gap-2.5 font-ui text-ui font-normal text-ink-1">
        <input type="checkbox" checked={adult} onChange={(event) => setAdult(event.target.checked)} className="h-4 w-4 shrink-0 accent-indigo" />
        I am 18 or older
      </label>
      <div className="grid gap-2">
        <span className="field-label">How should we credit you?</span>
        <SegmentedChoice label="How should we credit you?" value={mode} options={CREDIT_OPTIONS} onChange={(next) => setMode(next as CreditMode)} />
        {mode === "FULL_NAME" ? <input aria-label="Your full name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} className="kv-input" /> : null}
        {mode === "FIRST_NAME" ? <input aria-label="Your first name" value={shortName} onChange={(event) => setShortName(event.target.value)} maxLength={60} className="kv-input" /> : null}
        {mode === "CRAFT_AND_DISTRICT" ? <p className="font-ui text-label text-ink-2">{FEW_ARTISANS}</p> : null}
        {preview ? (
          <p className="font-ui text-ui font-normal text-ink-1" data-testid="credit-preview">
            <span className="text-ink-3">Shown as:</span> {preview}
          </p>
        ) : null}
      </div>
      {error ? <FormAlert>{error}</FormAlert> : null}
      <ActionGroup fill>
        <Button type="button" variant="primary" disabled={!ready} busy={busy} busyLabel="Saving" onClick={() => void save()}>
          {action}
        </Button>
      </ActionGroup>
    </div>
  );
}
