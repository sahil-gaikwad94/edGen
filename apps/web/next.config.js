/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.EDGEN_API_ORIGIN || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // The Arena preview is served from a sibling *.e2b.app origin in an iframe.
  // Permit only that preview domain for Next's dev assets/websocket requests.
  allowedDevOrigins: ["*.e2b.app"],
  // Browser calls relative /api/* → dev server proxies to FastAPI.
  // The browser never talks to localhost directly (Arena preview requirement).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_ORIGIN}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
