"use client";

import { Download, Search, X } from "lucide-react";
import { useState } from "react";

import { Demo, FORCED_FOCUS, Grid, Section, State, States } from "@/app/design/DesignParts";
import { PRIEST_KING } from "@/app/design/fixtures";
import { BrandLockup, BrandMark } from "@/components/BrandMark";
import { pictureSources } from "@/lib/pictureSources";
import { ActionGroup } from "@/components/ui/ActionGroup";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/Chip";
import { IconButton } from "@/components/ui/IconButton";
import { TextLink } from "@/components/ui/TextLink";

export function BrandSection() {
  return (
    <Section id="mark" title="The mark" lede="The ajrakh star cut as a block, and the wordmark at equal standing in both scripts. One colour at every size.">
      <Demo caption="Star at 16, 24, 32 and 64 pixels">
        <States className="items-end text-ink-1">
          {[16, 24, 32, 64].map((size) => (
            <State key={size} label={`${size}px`}>
              <span className="block" style={{ width: size, height: size }}>
                <BrandMark className="h-full w-full" />
              </span>
            </State>
          ))}
        </States>
      </Demo>
      <Grid>
        <Demo caption="Lockup">
          <BrandLockup />
        </Demo>
        <Demo caption="Lockup, compact">
          <BrandLockup compact />
        </Demo>
      </Grid>
    </Section>
  );
}

export function ButtonsSection() {
  const [pressed, setPressed] = useState(true);
  return (
    <Section id="buttons" title="Buttons" lede="Indigo fills mark what you can press or have chosen. Quiet buttons carry a 3:1 edge. Danger is madder and goes last.">
      <Demo caption="Primary">
        <States>
          <State label="Rest"><Button variant="primary">Request access</Button></State>
          <State label="Focus"><Button variant="primary" className={FORCED_FOCUS}>Request access</Button></State>
          <State label="Busy, same width"><Button variant="primary" busy busyLabel="Sending">Request access</Button></State>
          <State label="Disabled"><Button variant="primary" disabled>Request access</Button></State>
        </States>
      </Demo>
      <Demo caption="Quiet, danger and text">
        <States>
          <State label="Quiet"><Button variant="quiet">Sign in</Button></State>
          <State label="Pressed"><Button variant="quiet" aria-pressed={pressed} onClick={() => setPressed(!pressed)}>Sign in</Button></State>
          <State label="Small"><Button variant="quiet" size="sm">Show all 97</Button></State>
          <State label="Danger"><Button variant="danger">Remove key</Button></State>
          <State label="Confirming destructive"><Button variant="destroy">Delete lesson</Button></State>
          <State label="Disabled"><Button variant="quiet" disabled>Sign in</Button></State>
          <State label="Text"><Button variant="text">Play again</Button></State>
        </States>
      </Demo>
      <Demo caption="Icon buttons, 44px">
        <States>
          <State label="Plain"><IconButton label="Close" icon={<X />} /></State>
          <State label="With edge"><IconButton label="Download" icon={<Download />} edge /></State>
          <State label="Disabled"><IconButton label="Search" icon={<Search />} edge disabled /></State>
        </States>
      </Demo>
      <Demo caption="On a photograph">
        <div className="kv-photo kv-on-photo relative p-6">
          <img src={pictureSources(PRIEST_KING.src, "plate").src} alt="" referrerPolicy="no-referrer" className="absolute inset-0 h-full w-full object-cover" />
          <span aria-hidden className="kv-scrim-start absolute inset-0" />
          <div className="relative flex flex-wrap gap-3">
            <Button variant="primary" onPhoto>Request access</Button>
            <Button variant="quiet" onPhoto>Sign in</Button>
          </div>
        </div>
      </Demo>
    </Section>
  );
}

export function RowsSection() {
  return (
    <Section id="rows" title="Button rows" lede="Every row is an ActionGroup: one centred, two on one line, three or more stacked on a phone and pills from 640px.">
      <Grid columns={3}>
        <Demo caption="One: centred"><ActionGroup><Button variant="quiet" size="sm">Show all 11 stages</Button></ActionGroup></Demo>
        <Demo caption="Two: one line"><ActionGroup><Button variant="quiet" size="sm">Save</Button><Button variant="quiet" size="sm">Cite this answer</Button></ActionGroup></Demo>
        <Demo caption="Three or more">
          <ActionGroup>
            <Button variant="quiet" size="sm">Download PDF</Button>
            <Button variant="quiet" size="sm">Slides</Button>
            <Button variant="quiet" size="sm">Share link</Button>
            <Button variant="danger" size="sm" data-danger="">Delete lesson</Button>
          </ActionGroup>
        </Demo>
      </Grid>
      <Demo caption="Links and chips">
        <p className="max-w-measure font-reading text-body text-ink-1">
          Ajrakh is told in full in the <TextLink href="#mark">Kutch Ajrakh monograph</TextLink>, and its chemistry in the <TextLink href="#citations">Textiles family monograph</TextLink>.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-6">
          <TextLink href="#rows" standalone>All 97</TextLink>
          <TextLink onClick={() => undefined} standalone expanded={false}>Show all 23</TextLink>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="me-1 font-ui text-label text-ink-3">Try</span>
          <Chip pressed>indigo</Chip>
          <Chip pressed={false}>lost wax</Chip>
          <Chip pressed={false} count={7}>madder</Chip>
          <Chip disabled>alum</Chip>
        </div>
      </Demo>
    </Section>
  );
}
