import { apiFetch } from "@/lib/api";
import { MOLECULE_CONFORMER_PATH } from "@/lib/explainerMatter";
import { ShapeError } from "@/lib/shape";

export const CONFORMER_MAX_BYTES = 256 * 1024;
export const MOLFILE_VERSIONS = ["V2000", "V3000"] as const;

const SDF_END = "$$$$";
const THREE_D = "3D";
const DIMENSION_FROM = 20;
const DIMENSION_TO = 22;

export function conformerSdf(value: unknown, pubchemCid: number): string {
  const where = `the 3D conformer of CID ${pubchemCid}`;
  if (typeof value !== "string") throw new ShapeError(where, "an SDF record");
  const bytes = new TextEncoder().encode(value).length;
  if (bytes > CONFORMER_MAX_BYTES) throw new ShapeError(where, `at most ${CONFORMER_MAX_BYTES} bytes`);
  if (bytes !== value.length) throw new ShapeError(where, "ASCII text");
  const lines = value.split("\n");
  if (lines.length < 4 || lines[0].trim() !== String(pubchemCid)) throw new ShapeError(where, `the record of CID ${pubchemCid}`);
  if (lines[1].slice(DIMENSION_FROM, DIMENSION_TO) !== THREE_D) throw new ShapeError(where, "a 3D molfile");
  if (!MOLFILE_VERSIONS.some((version) => lines[3].includes(version))) throw new ShapeError(where, "a V2000 or V3000 molfile");
  if (value.trimEnd().split("\n").at(-1)?.trim() !== SDF_END) throw new ShapeError(where, `a record ending ${SDF_END}`);
  return value;
}

export async function fetchConformer(pubchemCid: number): Promise<string> {
  return conformerSdf(await apiFetch<unknown>(MOLECULE_CONFORMER_PATH(pubchemCid), {}, { revalidateFromHttpCache: true }), pubchemCid);
}
