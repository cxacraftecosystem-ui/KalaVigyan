import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

export const ELEVENLABS_CONNECT_SOURCES = ["wss://livekit.rtc.elevenlabs.io", "https://livekit.rtc.elevenlabs.io"];
export const GOOGLE_IDENTITY_SOURCE = "https://accounts.google.com/gsi/";
export const MEDIA_BUCKET_ORIGIN = "https://kalavigyan-media-626159998512.s3.ap-south-1.amazonaws.com";

export const WEB_PICTURE_SOURCE = "https:";
export const APPROVED_MONOGRAPHS = "/monographs/:path*";
export const IMAGE_SOURCES = ["'self'", "data:", MEDIA_BUCKET_ORIGIN, WEB_PICTURE_SOURCE];
export const TURNSTILE_SOURCE = "https://challenges.cloudflare.com";
export const FRAME_SOURCES = [GOOGLE_IDENTITY_SOURCE, TURNSTILE_SOURCE];

export const CONTENT_SECURITY_POLICY = [
  "frame-ancestors 'none'",
  ["frame-src", ...FRAME_SOURCES].join(" "),
  ["connect-src 'self'", GOOGLE_IDENTITY_SOURCE, ...ELEVENLABS_CONNECT_SOURCES, MEDIA_BUCKET_ORIGIN].join(" "),
  ["img-src", ...IMAGE_SOURCES].join(" "),
  `media-src 'self' ${MEDIA_BUCKET_ORIGIN}`
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: [
      "microphone=(self)",
      "camera=()",
      "geolocation=()",
      "clipboard-write=(self)",
      "autoplay=(self)",
      "accelerometer=()",
      "gyroscope=()",
      "magnetometer=()",
      "payment=()",
      "usb=()",
      "xr-spatial-tracking=()"
    ].join(", ")
  }
];

export const PICTURE_WIDTHS = [330, 500, 960, 1280, 1920];
export const PICTURE_QUALITIES = [80];
export const PICTURE_CACHE_SECONDS = 31_536_000;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    deviceSizes: PICTURE_WIDTHS,
    imageSizes: [],
    qualities: PICTURE_QUALITIES,
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: PICTURE_CACHE_SECONDS
  },
  env: {
    NEXT_PUBLIC_BUILD_NUMBER: process.env.NEXT_PUBLIC_BUILD_NUMBER || process.env.GITHUB_RUN_NUMBER || ""
  },
  experimental: {
    proxyTimeout: 300_000
  },
  turbopack: {
    root: __dirname
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          ...securityHeaders,
          ...(isProduction ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }] : [])
        ]
      },
      { source: APPROVED_MONOGRAPHS, headers: [{ key: "X-Robots-Tag", value: "noindex" }] }
    ];
  }
};

export default nextConfig;
