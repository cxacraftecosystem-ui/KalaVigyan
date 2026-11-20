import { apiFetch } from "@/lib/api";
import { declarationBody, declarationProblems, imageContributionShape, PICTURE_SLOTS, SLOT_LABELS, type ImageContribution, type ImageOrigin, type PictureSlot } from "@/lib/imageContributionContract";
import { list, nullable, object, oneOf, parseShape, text, type Shape } from "@/lib/shape";

export const UPLOAD_LINK_PARAM = "link";
export const UPLOAD_PAGE_PATH = "/contributions/pictures/upload";
export const PICTURES_PATH = "/contributions/pictures";
export const UPLOAD_LINK_MINUTES = 30;
export const UPLOAD_LINK_STATES = ["OPEN", "USED", "EXPIRED"] as const;
export const UPLOAD_LINK_PATH = (token: string) => `/upload-links/${encodeURIComponent(token)}`;
export const UPLOAD_LINK_PICTURE_PATH = (token: string) => `${UPLOAD_LINK_PATH(token)}/picture`;
export const UPLOAD_LINK_RENEW_PATH = (token: string) => `${UPLOAD_LINK_PATH(token)}/renew`;

const TOKEN_PATTERN = /^[A-Za-z0-9_-]{1,200}$/;
const SLOT_FIELDS = ["origin", "generator", "prompt", "caption", "altText", "rightsConfirmed", "termsVersion"];

export type UploadLinkState = (typeof UPLOAD_LINK_STATES)[number];
export type SlotCraft = { slug: string; name: string };
export type SlotStage = { id: string; name: string };
export type SlotMaterial = { id: string; name: string };
export type SlotFact = { id: string; text: string };

export type UploadLinkView = {
  state: UploadLinkState;
  craft: SlotCraft;
  stage: SlotStage | null;
  material: SlotMaterial | null;
  slot: PictureSlot | null;
  taskKey: string | null;
  facts: SlotFact[];
  expiresAt: string;
  contributionId: string | null;
};

export type RenewedLink = { token: string; link: string; expiresAt: string };

export type SlotDeclaration = {
  origin: ImageOrigin;
  generator: string;
  prompt: string;
  caption: string;
  altText: string;
};

export const uploadLinkShape: Shape<UploadLinkView> = object<UploadLinkView>({
  state: oneOf(UPLOAD_LINK_STATES),
  craft: object<SlotCraft>({ slug: text, name: text }),
  stage: nullable(object<SlotStage>({ id: text, name: text })),
  material: nullable(object<SlotMaterial>({ id: text, name: text })),
  slot: nullable(oneOf(PICTURE_SLOTS)),
  taskKey: nullable(text),
  facts: list(object<SlotFact>({ id: text, text }), 1),
  expiresAt: text,
  contributionId: nullable(text)
});

export const renewedLinkShape: Shape<RenewedLink> = object<RenewedLink>({ token: text, link: text, expiresAt: text });

export function uploadLinkToken(value: string | null): string | null {
  return value && TOKEN_PATTERN.test(value) ? value : null;
}

export function uploadPageHref(token: string): string {
  return `${UPLOAD_PAGE_PATH}?${new URLSearchParams({ [UPLOAD_LINK_PARAM]: token }).toString()}`;
}

export function slotDeclarationProblems(view: UploadLinkView, declaration: SlotDeclaration): string[] {
  return declarationProblems({ ...declaration, craftSlug: view.craft.slug, stageId: view.stage?.id ?? null, claimIds: view.facts.map((fact) => fact.id) });
}

export function slotDeclarationBody(declaration: SlotDeclaration): Record<string, unknown> {
  const body = declarationBody({ ...declaration, craftSlug: "", stageId: null, claimIds: [] });
  return Object.fromEntries(Object.entries(body).filter(([field]) => SLOT_FIELDS.includes(field)));
}

export function slotKicker(view: UploadLinkView): string {
  const shown = view.stage?.name ?? view.material?.name ?? (view.slot ? SLOT_LABELS[view.slot] : null);
  return shown ? `${view.craft.name} · ${shown}` : view.craft.name;
}

export function closedLinkTitle(view: UploadLinkView): string {
  return view.state === "USED" ? "This link was used already" : "This link has expired";
}

export function closedLinkLine(view: UploadLinkView): string {
  if (view.state === "USED") return `A picture link takes one picture. Get a new link to give another picture of ${view.craft.name} for the same facts.`;
  return `A picture link works for ${UPLOAD_LINK_MINUTES} minutes. Get a new link for the same craft and facts, valid for another ${UPLOAD_LINK_MINUTES} minutes.`;
}

export async function fetchUploadLink(token: string): Promise<UploadLinkView> {
  return parseShape(uploadLinkShape, await apiFetch<unknown>(UPLOAD_LINK_PATH(token)));
}

export async function renewUploadLink(token: string): Promise<RenewedLink> {
  return parseShape(renewedLinkShape, await apiFetch<unknown>(UPLOAD_LINK_RENEW_PATH(token), { method: "POST" }));
}

export async function giveLinkedPicture(token: string, declaration: SlotDeclaration, file: File): Promise<ImageContribution> {
  const form = new FormData();
  form.append("declaration", new Blob([JSON.stringify(slotDeclarationBody(declaration))], { type: "application/json" }), "declaration.json");
  form.append("picture", file, file.name);
  return parseShape(imageContributionShape, await apiFetch<unknown>(UPLOAD_LINK_PICTURE_PATH(token), { method: "POST", body: form }));
}
