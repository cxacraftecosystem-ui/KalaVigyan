"use client";

import { Demo, Grid, Section } from "@/app/design/DesignParts";
import { AJRAK_CLOTH, AJRAK_PRINT, GREEN_TO_BLUE, KASUTI_NAME, NUMBERS, SOURCES_BY_ID } from "@/app/design/fixtures";
import { Cite } from "@/components/editorial/CitationCluster";
import { Masthead } from "@/components/editorial/Masthead";
import { PlatePicture } from "@/components/editorial/Plate";
import { SpecimenLabel } from "@/components/editorial/SpecimenLabel";
import { TextLink } from "@/components/ui/TextLink";
import { pictureSources } from "@/lib/pictureSources";

function Credit({ picture }: { picture: { credit: string; page: string } }) {
  return (
    <>
      Photo: <TextLink href={picture.page} external className="font-normal text-inherit">{`${picture.credit}, via Wikimedia Commons`}</TextLink>
    </>
  );
}

const SENTENCE = (
  <span className="kv-sentence" data-cite-host="">
    Cloth lifted from the indigo vat is bright green at first and turns blue as oxygen meets the dye on the fibres.
    <Cite citations={GREEN_TO_BLUE} numbers={NUMBERS} sourcesById={SOURCES_BY_ID} />
  </span>
);

export function LabelSection() {
  return (
    <Section id="label" title="Specimen label and masthead" lede="Every craft has a label: it names the object, cites one sentence and carries the record. Names in their own script stand at equal size only where a source states them.">
      <Grid>
        <Demo caption="On a photograph">
          <div className="relative flex min-h-[26rem] items-end overflow-hidden rounded-plate p-4">
            <PlatePicture alt={AJRAK_PRINT.alt} sources={pictureSources(AJRAK_PRINT.src, "lead")} className="absolute inset-0 rounded-none" />
            <SpecimenLabel
              variant="landing"
              onPhoto
              kicker="Specimen"
              family="Textiles · Hand block printing"
              name="Kutch Ajrakh"
              sentence={SENTENCE}
              gi="Registered geographical indication, 22 April 2024"
              place="Kachchh, Gujarat"
              credit={<Credit picture={AJRAK_PRINT} />}
              className="w-[min(22.5rem,100%)]"
            />
          </div>
        </Demo>
        <Demo caption="On paper, a craft without a monograph">
          <SpecimenLabel variant="chapter" headingLevel="p" kicker="Craft" family="Paper" name="Kalpi Handmade Paper" place="Uttar Pradesh" provenance="From the KalaVigyan craft list" gi="GI registered" />
        </Demo>
      </Grid>
      <Demo caption="Masthead with its photograph">
        <Masthead
          material="textile"
          picture={{ src: AJRAK_CLOTH.src, alt: AJRAK_CLOTH.alt, caption: "The cloth spread out: the field of repeated roundels and the printed borders.", credit: <Credit picture={AJRAK_CLOTH} />, wide: [0, 0.18, 1, 0.62], narrow: [0.1, 0.05, 0.8, 0.9] }}
          label={{ kicker: "Monograph", family: "Textiles · Hand block printing", name: "Kutch Ajrakh", headingLevel: "p", sentence: SENTENCE, gi: "Registered geographical indication, 22 April 2024", place: "Kachchh, Gujarat", provenance: "Drawn from 20 sources · curated 17 Nov 2026" }}
        />
      </Demo>
      <Demo caption="Masthead without a photograph, the name at equal standing">
        <Masthead
          material="textile"
          plateKicker="Embroidery"
          label={{ kicker: "Craft", family: "Textiles · Embroidery", name: "Kasuti Embroidery", nativeName: KASUTI_NAME, headingLevel: "p", gi: "GI registered", place: "Karnataka", provenance: "From the KalaVigyan craft list · Kannada name: Wikidata, CC0" }}
        />
      </Demo>
    </Section>
  );
}
