import type { NextConfig } from "next";

const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

// Hosted NIM models (e.g. GLM) often need 45–90s. Next rewrites default to 30s
// and return socket hang up / 500 to the browser before the API finishes.
const proxyTimeoutMs = Number(process.env.API_PROXY_TIMEOUT_MS ?? "120000");

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    proxyTimeout: Number.isFinite(proxyTimeoutMs) && proxyTimeoutMs > 0 ? proxyTimeoutMs : 120_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiProxyTarget}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
