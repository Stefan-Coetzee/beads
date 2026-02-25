import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for Docker: copies only what's needed into .next/standalone
  output: "standalone",
  // Allow cross-origin requests from Cloudflare tunnel in dev
  allowedDevOrigins: ["*.trycloudflare.com"],
  // Turbopack config (Next.js 16+ default)
  turbopack: {
    resolveAlias: {
      fs: { browser: "./src/lib/empty-module.ts" },
      path: { browser: "./src/lib/empty-module.ts" },
      crypto: { browser: "./src/lib/empty-module.ts" },
    },
  },
  // Ignore these packages from SSR (they need browser APIs)
  serverExternalPackages: ["sql.js", "pyodide"],
  // Proxy API and LTI routes to the FastAPI backend.
  // This lets ngrok expose a single origin (Next.js on :3000)
  // while the backend runs on :8000.
  async rewrites() {
    // LTT_API_URL is a server-only variable (no NEXT_PUBLIC_ prefix) so it is
    // never embedded in the client bundle.  The browser always uses relative
    // URLs (/api/…, /lti/…) which Next.js proxies here to the FastAPI backend.
    // In production the ALB routes those paths directly — no rewrite needed.
    const apiTarget = process.env.LTT_API_URL;
    if (!apiTarget) {
      return [];
    }
    return [
      { source: "/lti/:path*", destination: `${apiTarget}/lti/:path*` },
      { source: "/api/:path*", destination: `${apiTarget}/api/:path*` },
      { source: "/health", destination: `${apiTarget}/health` },
    ];
  },
  async headers() {
    const ltiPlatform =
      process.env.LTI_PLATFORM_URL ||
      "https://imbizo.alx-ai-tools.com https://*.alx-ai-tools.com";
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `frame-ancestors 'self' ${ltiPlatform}`,
          },
        ],
      },
    ];
  },
  // Webpack config for production builds
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Don't resolve 'fs' module on the client
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        crypto: false,
      };
    }
    return config;
  },
};

export default nextConfig;
