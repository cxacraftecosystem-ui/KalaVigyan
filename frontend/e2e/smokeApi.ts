import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { join } from "node:path";

import { CRAFT_PAGE_PATH } from "../lib/craftPageContract";
import { MONOGRAPH_DOCUMENT_PATH } from "../lib/monographDocument";

import { fragmentDocumentText, goldenText } from "./monographNative";
import { nativeDocumentPath } from "./monographNativeBrowser";
import { withUnknownFields } from "./unknownFields";

export const FRAGMENT_VERSION = 2;
export const LATER_BACKEND_CRAFT = "Farrukhabad-Prints";
export const LATER_BACKEND_NAME = "Farrukhabad Prints";

const LOCAL_API = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/;
const REGISTER_GOLDEN = join(__dirname, "..", "..", "shared", "craft.page.register.golden.json");
const JSON_HEADERS = { "content-type": "application/json", "content-language": "en" };

type Answer = { status: number; body: string };
type Route = (query: URLSearchParams) => Answer;

export function smokeApiAddress(): URL | null {
  const origin = process.env.API_ORIGIN ?? process.env.NEXT_PUBLIC_API_URL ?? "";
  return LOCAL_API.test(origin) ? new URL(origin) : null;
}

function laterBackendPage(): string {
  return JSON.stringify(withUnknownFields(JSON.parse(readFileSync(REGISTER_GOLDEN, "utf8"))));
}

function answers(): Map<string, Route> {
  const native = goldenText();
  const fragments = fragmentDocumentText(FRAGMENT_VERSION);
  const laterPage = laterBackendPage();
  return new Map<string, Route>([
    [nativeDocumentPath(), (query) => ({ status: 200, body: query.get("version") === String(FRAGMENT_VERSION) ? fragments : native })],
    [`/api${MONOGRAPH_DOCUMENT_PATH(LATER_BACKEND_CRAFT)}`, () => ({ status: 404, body: JSON.stringify({ detail: "No monograph" }) })],
    [`/api${CRAFT_PAGE_PATH(LATER_BACKEND_CRAFT)}`, () => ({ status: 200, body: laterPage })]
  ]);
}

function served(routes: Map<string, Route>) {
  return (request: IncomingMessage, response: ServerResponse) => {
    const [path, query = ""] = (request.url ?? "").split("?");
    const route = request.method === "GET" ? routes.get(path) : undefined;
    if (!route) {
      request.socket.destroy();
      return;
    }
    const answer = route(new URLSearchParams(query));
    response.writeHead(answer.status, JSON_HEADERS);
    response.end(answer.body);
  };
}

export default async function smokeApi(): Promise<(() => Promise<void>) | undefined> {
  const address = smokeApiAddress();
  if (address === null) return undefined;
  const server: Server = createServer(served(answers()));
  await new Promise<void>((resolve, reject) => server.once("error", reject).listen(Number(address.port), address.hostname, resolve));
  return () => new Promise<void>((resolve) => server.close(() => resolve()));
}
