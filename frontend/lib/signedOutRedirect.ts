import { INSECURE_SESSION_MARKER_COOKIE, LEGACY_TOKEN_STORAGE_KEY, SESSION_MARKER_COOKIE } from "@/lib/sessionCookie";
import { signInHref } from "@/lib/sessionReturn";

const PROBE_PATH = "/";

export const SIGN_IN_PREFIX = signInHref(PROBE_PATH).slice(0, -encodeURIComponent(PROBE_PATH).length);

const MARKER_PATTERN = `/(?:^|;\\s*)(?:${SESSION_MARKER_COOKIE}|${INSECURE_SESSION_MARKER_COOKIE})=[^;]/`;

export const SIGNED_OUT_REDIRECT_SCRIPT =
  `(function(){try{` +
  `if(${MARKER_PATTERN}.test(document.cookie))return;` +
  `if(window.localStorage.getItem(${JSON.stringify(LEGACY_TOKEN_STORAGE_KEY)}))return;` +
  `window.location.replace(${JSON.stringify(SIGN_IN_PREFIX)}+encodeURIComponent(window.location.pathname+window.location.search));` +
  `}catch(e){}})();`;
