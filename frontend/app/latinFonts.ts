import localFont from "next/font/local";

const newsreader = localFont({
  src: "../fonts/newsreader-latin-var.woff2",
  display: "swap",
  variable: "--font-newsreader",
  weight: "300 600",
  style: "normal",
  adjustFontFallback: "Times New Roman",
  declarations: [
    { prop: "font-family", value: "Newsreader" },
    { prop: "unicode-range", value: "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2212, U+2215, U+FEFF, U+FFFD" }
  ]
});

const newsreaderItalic = localFont({
  src: "../fonts/newsreader-italic-latin-var.woff2",
  display: "swap",
  variable: "--font-newsreader-italic",
  weight: "300 600",
  style: "italic",
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "Newsreader" },
    { prop: "unicode-range", value: "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2212, U+2215, U+FEFF, U+FFFD" }
  ]
});

const newsreaderExtended = localFont({
  src: [
    { path: "../fonts/newsreader-latin-ext-var.woff2", weight: "300 600", style: "normal" },
    { path: "../fonts/newsreader-italic-latin-ext-var.woff2", weight: "300 600", style: "italic" }
  ],
  display: "swap",
  variable: "--font-newsreader-extended",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "Newsreader" },
    { prop: "unicode-range", value: "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0300-036F, U+1D00-1DBF, U+1E00-1EFF, U+2070-209F, U+20A0-20AB, U+20AD-20C0, U+2100-214F, U+2150-218F, U+219A-21FF, U+2200-2211, U+2213-2214, U+2216-22FF, U+2C60-2C7F, U+A720-A7FF, U+FB00-FB06" }
  ]
});

const newsreaderArrows = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-regular-pi.woff2", weight: "300 400", style: "normal" },
    { path: "../fonts/ibm-plex-sans-medium-pi.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-pi.woff2", weight: "600", style: "normal" },
    { path: "../fonts/ibm-plex-sans-italic-pi.woff2", weight: "300 600", style: "italic" }
  ],
  display: "swap",
  variable: "--font-newsreader-arrows",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "Newsreader" },
    { prop: "unicode-range", value: "U+2190-2199" }
  ]
});

const plexSans = localFont({
  src: "../fonts/ibm-plex-sans-regular-latin1.woff2",
  display: "swap",
  variable: "--font-plex-sans",
  weight: "400",
  style: "normal",
  adjustFontFallback: "Arial",
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+02C6, U+02DA, U+02DC, U+2013-2014, U+2018-201A, U+201C-201E, U+2020-2022, U+2026, U+2030, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+FB01-FB02" }
  ]
});

const plexSansWeights = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-medium-latin1.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-latin1.woff2", weight: "600", style: "normal" }
  ],
  display: "swap",
  variable: "--font-plex-sans-weights",
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+02C6, U+02DA, U+02DC, U+2013-2014, U+2018-201A, U+201C-201E, U+2020-2022, U+2026, U+2030, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+FB01-FB02" }
  ]
});

const plexSansItalic = localFont({
  src: "../fonts/ibm-plex-sans-italic-latin1.woff2",
  display: "swap",
  variable: "--font-plex-sans-italic",
  weight: "400",
  style: "italic",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+02C6, U+02DA, U+02DC, U+2013-2014, U+2018-201A, U+201C-201E, U+2020-2022, U+2026, U+2030, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+FB01-FB02" }
  ]
});

const plexSansLatin2 = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-regular-latin2.woff2", weight: "400", style: "normal" },
    { path: "../fonts/ibm-plex-sans-medium-latin2.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-latin2.woff2", weight: "600", style: "normal" },
    { path: "../fonts/ibm-plex-sans-italic-latin2.woff2", weight: "400", style: "italic" }
  ],
  display: "swap",
  variable: "--font-plex-sans-latin2",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0100-0101, U+0104-0130, U+0132-0151, U+0154-017F, U+018F, U+0192, U+01A0-01A1, U+01AF-01B0, U+01FA-01FF, U+0218-021B, U+0237, U+0259, U+1E80-1E85, U+1E9E, U+20A1, U+20A4, U+20A6, U+20A8-20AA, U+20AD-20AE, U+20B1-20B2, U+20B4-20B5, U+20B8-20BA, U+20BD, U+20BF" }
  ]
});

const plexSansLatin3 = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-regular-latin3.woff2", weight: "400", style: "normal" },
    { path: "../fonts/ibm-plex-sans-medium-latin3.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-latin3.woff2", weight: "600", style: "normal" },
    { path: "../fonts/ibm-plex-sans-italic-latin3.woff2", weight: "400", style: "italic" }
  ],
  display: "swap",
  variable: "--font-plex-sans-latin3",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0102-0103, U+01CD-01DC, U+1E0C-1E0D, U+1E12-1E13, U+1E24-1E25, U+1E36-1E37, U+1E3C-1E3D, U+1E40-1E47, U+1E4A-1E4B, U+1E62-1E63, U+1E6C-1E6D, U+1E70-1E71, U+1E92-1E93, U+1EA0-1EF9, U+20AB" }
  ]
});

const plexSansSymbols = localFont({
  src: [
    { path: "../fonts/ibm-plex-sans-regular-pi.woff2", weight: "400", style: "normal" },
    { path: "../fonts/ibm-plex-sans-medium-pi.woff2", weight: "500", style: "normal" },
    { path: "../fonts/ibm-plex-sans-semibold-pi.woff2", weight: "600", style: "normal" },
    { path: "../fonts/ibm-plex-sans-italic-pi.woff2", weight: "400", style: "italic" }
  ],
  display: "swap",
  variable: "--font-plex-sans-symbols",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Sans" },
    { prop: "unicode-range", value: "U+0E3F, U+2000-200D, U+2010-2012, U+2015-2016, U+2028-2029, U+202F, U+2032-2033, U+203C-203E, U+2042, U+2047-2049, U+2051, U+2053, U+2056, U+2058-205B, U+205D-205E, U+2070, U+2074-2079, U+2080-2089, U+20BC, U+20BE, U+20C0-20C1, U+20C3-20C4, U+2113, U+2116, U+2126, U+212E, U+2150-2151, U+2153-215E, U+2190-2199, U+21A9-21AA, U+21B0-21B3, U+21B6-21B7, U+21BA-21BB, U+21C4, U+21C6, U+2202, U+2206, U+220F, U+2211, U+2215, U+2219-221A, U+221E, U+222B, U+2236, U+2248, U+2260, U+2264-2265, U+25CA, U+2713, U+274C, U+2B0E-2B11, U+2E3A-2E3B, U+ECE0, U+EFCC, U+FEFF, U+FFFD" }
  ]
});

const plexMono = localFont({
  src: [
    { path: "../fonts/ibm-plex-mono-regular-latin1.woff2", weight: "400", style: "normal" },
    { path: "../fonts/ibm-plex-mono-medium-latin1.woff2", weight: "500", style: "normal" }
  ],
  display: "swap",
  variable: "--font-plex-mono",
  preload: false,
  adjustFontFallback: false,
  declarations: [
    { prop: "font-family", value: "IBM Plex Mono" },
    { prop: "unicode-range", value: "U+0020-007E, U+00A0-00FF, U+0131, U+0152-0153, U+02C6, U+02DA, U+02DC, U+2013-2014, U+2018-201A, U+201C-201E, U+2020-2022, U+2026, U+2030, U+2039-203A, U+2044, U+20AC, U+2122, U+2212, U+FB01-FB02" }
  ]
});

export const LATIN_FONT_VARIABLES = [newsreader, newsreaderItalic, newsreaderExtended, newsreaderArrows, plexSans, plexSansWeights, plexSansItalic, plexSansLatin2, plexSansLatin3, plexSansSymbols, plexMono]
  .map((font) => font.variable)
  .join(" ");
