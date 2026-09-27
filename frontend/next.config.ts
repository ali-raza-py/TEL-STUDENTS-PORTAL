import type { NextConfig } from "next";

/**
 * The browser only ever talks to its own origin. Requests to `/api/*` are
 * proxied to the Django backend, so the HttpOnly auth cookies stay first-party
 * and no CORS pre-flight is involved in development.
 */
const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
      { source: "/media/:path*", destination: `${backendOrigin}/media/:path*` },
    ];
  },
};

export default nextConfig;
