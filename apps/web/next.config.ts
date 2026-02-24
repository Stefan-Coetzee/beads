import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
    const apiTarget = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/lti/:path*", destination: `${apiTarget}/lti/:path*` },
      { source: "/api/:path*", destination: `${apiTarget}/api/:path*` },
      { source: "/health", destination: `${apiTarget}/health` },
    ];
  },
  async headers() {
    const ltiPlatform =
      process.env.LTI_PLATFORM_URL || "https://imbizo.alx-ai-tools.com";
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
