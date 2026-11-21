import localFont from "next/font/local";

const landingPlexSansWeights = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-medium-latin1.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-latin1.woff2", weight: "600", style: "normal" }
  ],
  display: "swap",
  variable: "--font-landing-plex-sans-weights",
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+02C6, U+02DA, U+02DC, U+2013-2014, U+2018-201A, U+201C-201E, U+2020-2022, U+2026, U+2030, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+FB01-FB02" }
  ]
});

const landingNewsreaderItalic = localFont({
  src: "../fonts/newsreader-italic-latin-var.woff2",
  display: "swap",
  variable: "--font-landing-newsreader-italic",
  weight: "300 600",
  style: "italic",
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "Newsreader" },
    { prop: "unicode-range", value: "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2212, U+2215, U+FEFF, U+FFFD" }
  ]
});

export const LANDING_FONT_VARIABLES = [landingPlexSansWeights, landingNewsreaderItalic].map((font) => font.variable).join(" ");
