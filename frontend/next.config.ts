import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    const apiPort = Number(process.env.INTENT_API_PORT || "8000");
    if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535)
      throw new Error("INTENT_API_PORT must be a valid loopback port.");
    return [
      {
        source: "/api/:path*",
        destination: `http://127.0.0.1:${apiPort}/api/:path*`,
      },
    ];
  },
  experimental: { proxyTimeout: 180_000 },
};
export default config;
